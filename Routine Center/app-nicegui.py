# %%
import time
import json
import socket
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

logger.add('log/BCI station control center.log', rotation='5 MB')

# %%


class ClientStatus(Enum):
    Connecting = 1
    Connected = 2
    Disconnected = 3


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
    status: ClientStatus = ClientStatus.Connecting
    # Message queue
    queue: Queue = Queue(1000)

    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            self.__setattr__(k, v)


class ControlCenter:
    host = 'localhost'
    port = 12345
    valid_key = b'12345678'
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    incoming_clients = {}
    echo_data = []
    message_queue = Queue(100)

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
        try:
            # Receive the hello message from the client.
            # Read the advanced key code (8 bytes) for identifying the legal client.
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
            self.incoming_clients[client_address] = ic

            ic.status = ClientStatus.Connecting

            # Echo package chunk.
            self.send_echo_packages(client_socket, client_address)

            ic.status = ClientStatus.Connected

            self.update_gui()

            logger.info(
                f'Client {self.incoming_clients[client_address]} comes.')

            # Keep listening for the messages from the client.
            while True:
                # Receive the header
                # The header is message length
                message_length = client_socket.recv(8)
                # Break out if message_length is null
                if not message_length:
                    break
                message_length = int.from_bytes(
                    message_length, byteorder='big')

                # Receive the message body on message_length.
                message = b""
                while len(message) < message_length:
                    chunk = client_socket.recv(
                        min(message_length - len(message), 1024))
                    if not chunk:
                        break
                    message += chunk

                # Not allow the empty message body.
                assert message, "Empty message is not allowed."

                message = message.decode()
                logger.debug(
                    f"Received message: {message[:20]} ({len(message)} bytes)")

                self.handle_message(message, client_address)

                try:
                    ic.queue.put_nowait(message)
                except queue.Full:
                    logger.warning('Message queue is full.')

                # The next while loop.
                continue

        except (ConnectionResetError, ConnectionAbortedError, AssertionError) as err:
            logger.error(f'Occurred: {err}')

        finally:
            client_socket.close()
            self.incoming_clients[client_address].status = ClientStatus.Disconnected
            self.update_gui()
            self.update_latest_message(
                client_address, f"{client_path} ({client_uid}) disconnected")

    def handle_message(self, message, client_address):
        sic: IncomingClient = self.incoming_clients[client_address]

        # TODO: Handle the message from the client
        if message.startswith("Echo"):
            # Handle echo package
            # Handle the echo package AFTER the connection has been established.
            # It is used to sync the client during the workflow.
            parts = message.split(',')
            t1 = float(parts[1])
            t2 = float(parts[2])
            t3 = time.time()
            self.echo_data.append({'t1': t1, 't2': t2, 't3': t3})
            logger.debug('Received echo message.')
        elif message.startswith("Keep-Alive"):
            # Handle keep-alive package.
            # Not doing anything.
            pass
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
                    self.send_message(dic['socket'], json.dumps(letter))
                    logger.info(f'Translated {letter} to {dic.address}')
                    count += 1

            # If the letter is not delivered, log the warning.
            if count == 0:
                logger.warning(f'Received {raw_letter}, but did not deliver.')
        else:
            logger.warning(f'Can not handle message: {message}')

        # Update the latest message.
        self.update_latest_message(client_address, message)

        return message

    def send_echo_packages(self, client_socket, client_address):
        """
        Send and receive a chunk of echo packages.

        Attention, this methods duplicates 20 talks to prevent random delay occasionally.
        There are 10 ms gaps between talks, so it costs about 0.2 seconds to finish.
        """
        echo_data = []
        for _ in tqdm(range(20), 'Echo'):
            self.send_echo_package(client_socket)
            self.receive_echo_response(client_socket, echo_data)
            time.sleep(0.01)
        df = pd.DataFrame(echo_data)
        df['delay'] = df['t3'] - df['t1']
        df['tServer'] = (df['t3'] + df['t1']) / 2
        df['tClient'] = df['t2']
        df = df.sort_values(by='delay', ascending=True)

        connection_quality = dict(
            netDelay=float(df.iloc[0]['delay']),
            netRemoteTime=float(df.iloc[0]['tClient']) +
            float(df.iloc[0]['delay'])/2,
            netLocalTime=float(df.iloc[0]['tServer'])
        )
        self.incoming_clients[client_address].update(**connection_quality)
        return df

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
        message_bytes = message.encode()
        message_length = len(message_bytes).to_bytes(8, byteorder='big')
        client_socket.sendall(message_length + message_bytes)
        logger.debug(f"Sent message: {message[:20]} ({len(message)} bytes)")

    def update_latest_message(self, client_address, message: str, meaningful_message: bool = True):
        """Update the latest message of the client."""
        client_info = self.incoming_clients.get(client_address)

    def update_gui(self):
        pass

    def close_server(self):
        """Close the server and all client connections."""
        for client_info in tqdm(list(self.incoming_clients.values()), 'Closing'):
            client_info['socket'].close()
            logger.info(f'Client {client_info} closed.')
        self.server_socket.close()
        logger.info('Sever socked closed.')
        self.gui.quit()
        logger.info(f'TK gui quit.')

    def run(self):
        """Run the control center."""
        self.start_server()


# %%
homepage = ui.card()

# control_center = ControlCenter(host='192.168.137.1')
control_center = ControlCenter()


class NiceGuiManager(object):
    pages: dict = defaultdict(dict)
    tabs = ui.tabs().classes('w-full')
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
        print('')
        print(f'Timer callback at {time.time()}')
        # print('clients', self.cc.incoming_clients)
        # print('pages', self.pages)
        for _, ic in self.cc.incoming_clients.items():
            ic: IncomingClient = ic
            thread_name = ic.address

            if ic.status is ClientStatus.Disconnected and thread_name in self.thread_book:
                self.thread_book.pop(ic.address)

            # If already has the page.
            # TODO: Update the page.
            if ic.address in self.pages:
                dct = self.pages[ic.address]
                dct['status_label'].text = f'Status: {ic.status}'
                dct['quality_label'].text = f"Delay: {ic.netDelay:.4f} | Offset: {
                    ic.netRemoteTime - ic.netLocalTime:.4f}"

                if ic.status is ClientStatus.Disconnected:
                    dct['spinner'].set_visibility(False)

                continue

            # Create the new page.
            # TODO: Create the decent page.
            # Append new card.
            with self.tabs:
                page = ui.tab(f'{ic.path} | {ic.uid} | {ic.address}')

            with ui.tab_panels(self.tabs, value=page).classes('w-full'):
                with ui.tab_panel(page):
                    info_card = ui.card()
                    quality_card = ui.card()
                    message_log = ui.log(max_lines=10)

            with info_card:
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

            self.pages[ic.address].update(
                page=page,
                spinner=spinner,
                status_label=status_label,
                quality_label=quality_label,
                message_log=message_log)

            # Register the log rolling thread, if the thread is not started.
            if thread_name not in self.thread_book:
                self.thread_book[thread_name] = 'started'
                Thread(target=self.log_rolling_thread,
                       args=(message_log, ic.queue, thread_name), daemon=True).start()

        ui.update()
        return


# %%

if __name__ in ("__main__", "__mp_main__"):
    print(f'Running in {__name__} mode.')

    ngm = NiceGuiManager()
    if __name__ == "__mp_main__":
        Thread(target=ngm.cc.run, daemon=True).start()

    ui.timer(1, ngm.timer_callback)
    ui.run(title='BCI station')

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
