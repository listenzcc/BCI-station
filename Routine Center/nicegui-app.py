# %%
import time
import json
import socket
import contextlib
import pandas as pd

from enum import Enum
from nicegui import ui
from threading import Thread
from collections import defaultdict

import queue
from queue import Queue

from loguru import logger
from tqdm.auto import tqdm
from dataclasses import dataclass
from urllib.parse import urlparse

from client_base import MailMan

logger.add('log/BCI station control center.log', rotation='5 MB')

# %%

mm = MailMan()


class ClientStatus(Enum):
    Initialized = 'Initialized, but not used.'
    Connecting = 'Connecting, time correction is processing.'
    Connected = 'Established, everything is fine.'
    Disconnected = 'Has been disconnected.'


@dataclass(slots=False)
class IncomingClient:
    # Basic information
    address: str = 'Client address'
    path: str = 'Path of the client'
    uid: str = 'UID of the client'
    # Connection and its quality
    socket = None
    netDelay: float = 0
    netRemoteTime: float = 0
    netLocalTime: float = 0
    # Status of the client
    status: ClientStatus = None  # ClientStatus.Initialized
    # Message queue
    message_queue: Queue = None  # Queue(1000)
    # Echo data
    echo_data: list = None  # []
    # Bags
    bags: dict = None  # {k: None for k in mm.bags}

    def __init__(self):
        self.bags = {k: None for k in mm.bags}
        self.message_queue = Queue(1000)
        self.status = ClientStatus.Initialized
        self.echo_data = []

    def update(self, **kwargs):
        '''
        Update the attributes of the client.

        :param kwargs: The dictionary of the key/value pairs.

        :return: The IncomingClient object.
        '''
        for k, v in kwargs.items():
            self.__setattr__(k, v)
        return self

    def estimate_connection_quality(self):
        '''
        Estimate connection quality.

        The echo_data or connection quality table has 3 columns:

        1. t1, the local sending time.
        2. t2, the remote time.
        3. t3, the local receiving time.

        The connection quality attributes of netDelay, netRemoteTime and netLocalTime are updated according to the table.

        :return: Connection quality table.
        '''
        df = pd.DataFrame(self.echo_data)
        df['delay'] = df['t3'] - df['t1']
        df['tServer'] = (df['t3'] + df['t1']) / 2
        df['tClient'] = df['t2']
        df = df.sort_values(by='delay', ascending=True)

        # Update the connection quality attributes by the lowest delay record.
        connection_quality = dict(
            netDelay=float(df.iloc[0]['delay']),
            netRemoteTime=float(df.iloc[0]['tClient']) +
            float(df.iloc[0]['delay'])/2,
            netLocalTime=float(df.iloc[0]['tServer'])
        )
        self.update(**connection_quality)
        return df


class ControlCenter:
    '''
    The control center for incoming clients.
    When the client comes, its connection quality is measured immediately at connecting.
    During the measurement, the time lag and offset is measured.
    In the end, 'YouAreGoodToGo' message is sent.
    It means the connection is fully ready.
    '''
    host = 'localhost'
    port = 12345
    valid_key = b'12345678'
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    incoming_clients = {}

    def __init__(self, host=None, port=None, valid_key=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if valid_key:
            self.valid_key = valid_key
        logger.info(f"Initialized control center {self}")

    def start_server(self):
        """Start the server and begin accepting clients."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logger.info(f"Server started on {self.host}:{self.port}")
        Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        """Accept incoming client connections."""
        while True:
            client_socket, client_address = self.server_socket.accept()
            logger.info(f"Client {client_address} connected")
            Thread(target=self.handle_client, args=(
                client_socket, client_address)).start()

    def handle_client(self, client_socket, client_address):
        """Handle communication with a connected client."""
        # Receive the hello message from the client.
        # Read the advanced key code (8 bytes) for identifying the legal client.
        try:
            key_code = client_socket.recv(8)
            if key_code != self.valid_key:
                logger.warning(
                    f"Client {client_address} provided invalid key. Disconnecting.")
                client_socket.close()
                return

            # Read the length of the initial message (8 bytes for larger messages)
            message_length = client_socket.recv(8)
            if not message_length:
                return
            message_length = int.from_bytes(message_length, byteorder='big')

            # Read the actual message based on the length
            message = b""
            while len(message) < message_length:
                chunk = client_socket.recv(
                    min(message_length - len(message), 1024))
                if not chunk:
                    return
                message += chunk

            # Not allow the empty message body.
            assert message, "Empty message is not allowed."

            # The message body contains the identity.
            message = message.decode()
            logger.debug(
                f"Received message: {message[:20]} ({len(message)} bytes)")
            client_info = message.split(',')
            client_path = client_info[0]
            client_uid = client_info[1]

            # Make the client object
            ic = IncomingClient()
            ic.update(**{
                # Basic information of the socket.
                'address': client_address,
                'socket': client_socket,
                'path': client_path,
                'uid': client_uid,
            })

            ic.status = ClientStatus.Connecting

            # Echo package chunk.
            self.exchange_echo_packages(ic)

            ic.status = ClientStatus.Connected

            self.incoming_clients[client_address] = ic
            logger.info(f'Client comes: {ic}')
        except Exception as err:
            logger.error('Error occurred during connecting.')
            raise err

        # Now I have the legal IncomingClient.
        try:
            self.send_message(ic.socket, 'YouAreGoodToGo')
            self._handle_client_message_loop(ic)
        except (ConnectionResetError, ConnectionAbortedError, AssertionError) as err:
            logger.error(f'Occurred: {err}')
        finally:
            client_socket.close()
            ic.status = ClientStatus.Disconnected
        return

    def _handle_client_message_loop(self, ic: IncomingClient):
        # Keep listening for the messages from the client.
        while True:
            # Receive the header
            # The header is message length
            message_length = ic.socket.recv(8)
            # Break out if message_length is null
            if not message_length:
                break
            message_length = int.from_bytes(
                message_length, byteorder='big')

            # Receive the message body on message_length.
            message = b""
            while len(message) < message_length:
                chunk = ic.socket.recv(
                    min(message_length - len(message), 1024))
                if not chunk:
                    break
                message += chunk

            # Not allow the empty message body.
            assert message, "Empty message is not allowed."

            message = message.decode()
            logger.debug(
                f"Received message: {message[:20]} ({len(message)} bytes)")

            self.handle_message(message, ic)

            try:
                ic.message_queue.put_nowait(message)
            except queue.Full:
                logger.warning('Message queue is full.')

            # The next while loop.
            continue

    def handle_message(self, message: str, sic: IncomingClient):
        # TODO: Handle the message from the client
        # Handle the bags message.
        # It aligns with the MailMan's bag.
        for bag_name in sic.bags.keys():
            if message.startswith(bag_name):
                content = message
                # content = message.split(':', 1)[1]
                # content = json.loads(content)
                sic.bags.update(
                    {bag_name: f'{sic.address}-{sic.path}-{sic.uid}'+content})
                return message

        # Handle echo package.
        if message.startswith("Echo"):
            # Handle the echo package AFTER the connection has been established.
            # It is used to sync the client during the workflow.
            parts = message.split(',')
            t1 = float(parts[1])
            t2 = float(parts[2])
            t3 = time.time()
            sic.echo_data.append({'t1': t1, 't2': t2, 't3': t3})
            logger.debug('Received echo message.')

        # Handle keep-alive package.
        elif message.startswith("Keep-Alive"):
            # Request bag information.
            for key in mm.bags.keys():
                self.send_message(sic.socket, f'AcquireBags-{key}')
            # Not doing anything.
            pass

        # Handle other json package.
        elif message.startswith("{"):
            # The incoming message is the json object
            raw_letter = json.loads(message)

            url = urlparse(raw_letter['dst'])
            path = url.path
            uid = url.query

            raw_letter['_stations'].append(('ControlCenter', time.time()))

            # Transfer it to the client with dst path
            count = 0
            for _, v in self.incoming_clients.items():
                dic: IncomingClient = v
                if dic.status is not ClientStatus.Connected:
                    continue
                # Check if the dst_client matches with the letter's dst.
                if dic.path == path and any((dic.uid == uid, len(uid) == 0)):
                    # Make the new letter.
                    letter = raw_letter.copy()
                    # Translate the timestamp into dst's timestamp.
                    t = letter['_timestamp']
                    # Translate src time into local time
                    t = t - sic.netRemoteTime + sic.netLocalTime
                    # Translate local time into dst time
                    t = t - dic.netLocalTime + dic.netRemoteTime
                    letter['_timestamp'] = t
                    self.send_message(dic.socket, json.dumps(letter))
                    logger.info(f'Translated {letter} to {dic.address}')
                    count += 1

            # If the letter is not delivered, log the warning.
            if count == 0:
                logger.warning(f'Received {raw_letter}, but did not deliver.')
        else:
            logger.error(f'Can not handle message: {message}')

        # Update the latest message.
        self.update_latest_message(sic, message)

        return message

    def exchange_echo_packages(self, ic: IncomingClient):
        """
        Send and receive a chunk of echo packages.

        Attention, this methods duplicates 20 talks to prevent random delay occasionally.
        There are 10 ms gaps between talks, so it costs about 0.2 seconds to finish.
        """
        for _ in tqdm(range(20), 'Echo'):
            self.send_echo_package(ic.socket)
            self.receive_echo_response(ic.socket, ic.echo_data)
            time.sleep(0.01)
        return ic.estimate_connection_quality()

    def send_echo_package(self, client_socket):
        """
        Send a single echo package to the client.
        The package is finished in 3 steps:
            1. t1, the local sending time.
            2. t2, the remote time.
            3. t3, the local receiving time.
        The t3 - t1 is the package delay.
        And the (t1+t3)/2 in remote time zone should be of the same time with the t2 in local time zone.
        """
        t1 = time.time()
        message = f"Echo,{t1}"
        self.send_message(client_socket, message)

    def receive_echo_response(self, client_socket, echo_data: list):
        """
        Handle the received echo response from the client.
        The [echo_data] is the list storing the echo response,
        which is appended in-place.
        """
        try:
            message_length = client_socket.recv(8)
            if not message_length:
                return
            message_length = int.from_bytes(message_length, byteorder='big')

            message = b""
            while len(message) < message_length:
                chunk = client_socket.recv(
                    min(message_length - len(message), 1024))
                if not chunk:
                    break
                message += chunk

            if not message:
                return

            message = message.decode()
            logger.debug(
                f"Received message: {message[:20]} ({len(message)} bytes)")

            if message.startswith("Echo"):
                parts = message.split(',')
                t1 = float(parts[1])
                t2 = float(parts[2])
                t3 = time.time()
                echo_data.append({'t1': t1, 't2': t2, 't3': t3})

        except (ConnectionResetError, socket.timeout):
            pass
        return

    def send_message(self, client_socket, message: str):
        """Send a message to the client."""
        if client_socket is None:
            return
        message_bytes = message.encode()
        message_length = len(message_bytes).to_bytes(8, byteorder='big')
        client_socket.sendall(message_length + message_bytes)
        logger.debug(f"Sent message: {message[:20]} ({len(message)} bytes)")
        return

    def update_latest_message(self, ic: IncomingClient, message: str):
        """Update the latest message of the client."""
        pass

    def close_server(self):
        """Close the server and all client connections."""
        for client_info in tqdm(list(self.incoming_clients.values()), 'Closing'):
            client_info['socket'].close()
            logger.info(f'Client {client_info} closed.')
        self.server_socket.close()
        logger.info('Sever socked closed.')

    def run(self):
        """Run the control center."""
        self.start_server()


# %%
homepage = ui.card()
with homepage:
    ui.label('Hello there!')
    ui.label('I am the Routine Center.')

# control_center = ControlCenter(host='192.168.137.1')
control_center = ControlCenter()


class NiceGuiManager(object):
    pages_container: dict = defaultdict(dict)
    # Initialize the tabs, tab_panels, where the tab_panels contains the tabs object.
    tabs = ui.tabs().classes('w-full')
    tab_panels = ui.tab_panels(tabs).classes('w-full')
    cc = control_center
    thread_book = {}

    def log_rolling_thread(self, message_log: ui.log, message_queue: Queue, thread_name: str):
        '''
        Log rolling thread for the message log.

        :params message_log (ui.log): the message log widget.
        :params message_queue (Queue): The queue to get the message.
        :params thread_name (str): The name of the thread.
        '''
        while thread_name in self.thread_book:
            # Set the timeout to avoid blocking forever.
            # And handle the empty exception in case of empty queue situation.
            try:
                message_log.push(message_queue.get(timeout=1))
            except queue.Empty:
                continue
        message_log.push('Log rolling thread stopped.')

    def timer_callback(self):
        '''
        Timer callback, running for every 1 second.
        Update the page.
        '''
        # print('')
        # print(f'Timer callback at {time.time()}')
        for _, ic in self.cc.incoming_clients.items():
            ic: IncomingClient = ic

            # On the ic is disconnected.
            # 1. remove it from the thread_book, stop update info.
            # 2. Remove the page and panel.
            # 3. Remove from pages_container.
            if ic.status is ClientStatus.Disconnected:
                with contextlib.suppress(Exception):
                    self.thread_book.pop(ic.address)

                if pc := self.pages_container[ic.address]:
                    page = pc['page']
                    tab_panel = pc['tab_panel']
                    self.tabs.remove(page)
                    self.tabs.remove(tab_panel)

                with contextlib.suppress(Exception):
                    self.pages_container.pop(ic.address)

                continue

            # If already has the page.
            # TODO: Update the page.
            if dct := self.pages_container.get(ic.address):
                dct['path_label'].text = f'Path: {ic.path}?{ic.uid} {time.ctime()}'
                dct['status_label'].text = f'Status: {ic.status}'
                offset = ic.netRemoteTime - ic.netLocalTime
                dct['quality_label'].text = f"Delay: {ic.netDelay:.4f} | Offset: {offset:.4f}"

                # Alive spinner.
                if ic.status is ClientStatus.Disconnected:
                    dct['spinner'].set_visibility(False)

                # Update bags.
                for k, v in ic.bags.items():
                    dct['bags'][k].value = v

                continue

            # Create the new page.
            # Append new card.
            with self.tabs:
                page = ui.tab(f'{ic.path} | {ic.uid} | {ic.address}')

            # Append the panel to the page.
            # Set the current tab with the latest added page.
            self.tab_panels.set_value(page)
            # Work with the current page.
            with self.tab_panels:
                tab_panel = ui.tab_panel(page)
                with tab_panel:
                    with ui.row():
                        info_card = ui.card()
                        quality_card = ui.card()
                    message_log = ui.log(max_lines=10)
                    with ui.row():
                        # The bags should be aligned with the mm's bags
                        bags = {
                            k: ui.textarea(label=k).style('width: 600px')
                            for k in mm.bags.keys()}

            with info_card:
                path_label = ui.label(f'Path: {ic.path} ({ic.uid})')
                with ui.list().props('dense separator'):
                    ui.item(f"Client: {ic.path} ({ic.uid})")
                    ui.item(f"Address: {ic.address}")

            with quality_card:
                with ui.row():
                    spinner = ui.spinner('audio', size='lg')
                    with ui.column():
                        quality_label = ui.label(
                            f"Delay: {ic.netDelay:.4f} | Offset: {ic.netRemoteTime - ic.netLocalTime:.4f}")
                        status_label = ui.label(f'Status: {ic.status}')

            self.pages_container[ic.address].update(
                # Container, panel -> page.
                page=page,
                tab_panel=tab_panel,
                # Info label.
                path_label=path_label,
                status_label=status_label,
                quality_label=quality_label,
                spinner=spinner,
                # Message log area.
                message_log=message_log,
                # Bag textarea.
                bags=bags
            )

            # Register the log rolling thread, if the thread is not started.
            if ic.address not in self.thread_book:
                self.thread_book[ic.address] = 'started'
                Thread(target=self.log_rolling_thread,
                       args=(message_log, ic.message_queue, ic.address), daemon=True).start()

        ui.update()
        return


# %%
ngm = NiceGuiManager()
Thread(target=ngm.cc.run, daemon=True).start()

ui.timer(1, ngm.timer_callback)
ui.run(title='BCI station', reload=False)

# Client developer instructions:
# To send a message, first send the advanced key code as an 8-byte value.
# Then send the length of the message as an 8-byte integer in big-endian order.
# Finally, send the actual message bytes.
# Example:
# key_code = b'12345678'
# message = "ClientName,ClientUID"
# message_bytes = message.encode()
# message_length = len(message_bytes).to_bytes(8, byteorder='big')
# client_socket.sendall(key_code + message_length + message_bytes)
