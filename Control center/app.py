import time
import socket
import threading
import pandas as pd
import tkinter as tk

from loguru import logger
from tqdm.auto import tqdm
from tkinter import messagebox

logger.add('log/BCI station control center.log', rotation='5 MB')


class ControlCenter:
    host = 'localhost'
    port = 12345
    valid_key = b'12345678'

    def __init__(self, host=None, port=None, valid_key=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if valid_key:
            self.valid_key = valid_key

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = {}
        self.gui = None
        self.echo_data = []
        logger.info(f"Initialized control center {self}")

    def start_server(self):
        """Start the server and begin accepting clients."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logger.info(f"Server started on {self.host}:{self.port}")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        """Accept incoming client connections."""
        while True:
            client_socket, client_address = self.server_socket.accept()
            logger.info(f"Client {client_address} connected")
            threading.Thread(target=self.handle_client, args=(
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
            client_name = client_info[0]
            client_uid = client_info[1]

            # New client is coming.
            # Add into the client_list,
            # Update its status.
            self.clients[client_address] = {
                'address': client_address,
                'socket': client_socket,
                'name': client_name,
                'uid': client_uid,
                'frame': None,
                'latest_message': tk.StringVar(),
                'messages': tk.IntVar()
            }

            self.update_latest_message(
                client_address, f"{client_name} ({client_uid}) connected")

            # Echo package chunk.
            self.send_echo_packages(client_socket, client_address)

            self.update_client_list_tkUI()

            logger.info(f'Client {self.clients[client_address]} comes.')

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

                # The next while loop.
                continue

        except (ConnectionResetError, ConnectionAbortedError, AssertionError):
            pass
        finally:
            client_socket.close()
            del self.clients[client_address]
            self.update_client_list_tkUI()
            self.update_latest_message(
                client_address, f"{client_name} ({client_uid}) disconnected")

    def handle_message(self, message, client_address):
        meaningful_message = False

        # TODO: Handle the message from the client
        if message.startswith("echo"):
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
        elif message.startswith("Info."):
            # Handle info package.
            # ! Not doing anything.
            pass
        else:
            meaningful_message = True
            logger.warning(f'Can not handle message: {message}')

        # Update the latest message.
        self.update_latest_message(
            client_address, message, meaningful_message=True)

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
            netRemoteTime=float(df.iloc[0]['tClient']),
            netLocalTime=float(df.iloc[0]['tServer'])
        )
        self.clients[client_address].update(connection_quality)
        return df

    def send_echo_package(self, client_socket):
        """Send a single echo package to the client."""
        t1 = time.time()
        message = f"echo,{t1}"
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

            if message.startswith("echo"):
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
        client_info = self.clients.get(client_address)
        if client_info:
            # Only update the latest message when it is the meaningful message.
            if meaningful_message:
                client_info['latest_message'].set(message)
            # Ascending the messages count.
            client_info['messages'].set(client_info['messages'].get()+1)

    def update_client_list_tkUI(self):
        """Update the client list in the Tkinter GUI."""

        # Destroy the existing clients.
        for widget in self.client_list_frame.winfo_children():
            widget.destroy()

        # Rebuild the client list into the frame (self.client_list_frame).
        for client_address, client_info in self.clients.items():
            frame = tk.Frame(self.client_list_frame)
            # Basic information.
            tk.Label(frame,
                     text=f"{client_info['name']} ({client_info['uid']}) {client_address}").pack()
            # Network information.
            tk.Label(frame,
                     text=f"Delay: {client_info['netDelay']:.4f} | Offset: {client_info['netRemoteTime'] - client_info['netLocalTime']:.4f}").pack()
            # Latest message.
            tk.Label(frame,
                     textvariable=client_info['latest_message']).pack()
            # Messages.
            tk.Label(frame,
                     textvariable=client_info['messages']).pack()
            frame.pack()
            client_info['frame'] = frame
            logger.debug(f'Updated UI for client {client_address}')

    def start_gui(self):
        """Start the Tkinter GUI."""
        self.gui = tk.Tk()
        self.gui.title("Control Center")
        self.gui.geometry("400x300")
        tk.Label(self.gui, text="Control Center Monitoring").pack()
        self.client_list_frame = tk.Frame(self.gui)
        self.client_list_frame.pack()
        tk.Button(self.gui, text="Exit", command=self.close_server).pack()
        self.gui.protocol("WM_DELETE_WINDOW", self.close_server)
        self.gui.mainloop()

    def close_server(self):
        """Close the server and all client connections."""
        for client_info in tqdm(list(self.clients.values()), 'Closing'):
            client_info['socket'].close()
            logger.info(f'Client {client_info} closed.')
        self.server_socket.close()
        logger.info('Sever socked closed.')
        self.gui.quit()
        logger.info(f'TK gui quit.')

    def run(self):
        """Run the control center."""
        self.start_server()
        self.start_gui()


if __name__ == "__main__":
    # control_center = ControlCenter(host='192.168.137.1')
    control_center = ControlCenter()
    control_center.run()

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
