import time
import socket
from threading import Thread


class SocketClientBase:
    # Client setup, may be overridden by subclasses.
    path = '/client/baseClient'
    uid = 'bc-0'
    key_code = b'12345678'

    # Socket setup, may be overridden by subclass and __init__ method.
    host = 'localhost'
    port = 12345
    timeout = 1000

    def __init__(self, host=None, port=None, timeout=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout:
            self.timeout = timeout

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(self.timeout)

    def keep_alive(self):
        def _keep_alive():
            while True:
                try:
                    self.send_message(f'Keep-Alive, {time.time()}')
                    time.sleep(5)
                except (ConnectionAbortedError, ConnectionResetError, socket.timeout):
                    break
        Thread(target=_keep_alive, daemon=True).start()

    def keep_receiving(self):
        def _receive_message():
            while True:
                try:
                    message = self.receive_message()
                except (ConnectionAbortedError, ConnectionResetError, socket.timeout):
                    break
        Thread(target=_receive_message, daemon=True).start()

    def connect(self):
        self.client_socket.connect((self.host, self.port))
        print(f"Connected to server at {self.host}:{self.port}")
        self.send_initial_info()
        self.keep_receiving()
        self.keep_alive()

    def send_initial_info(self):
        initial_message = f"{self.path},{self.uid}"
        self.send_message(initial_message, include_key=True)

    def send_message(self, message, include_key=False):
        message_bytes = message.encode()
        message_length = len(message_bytes).to_bytes(8, byteorder='big')
        if include_key:
            self.client_socket.sendall(
                self.key_code + message_length + message_bytes)
        else:
            self.client_socket.sendall(message_length + message_bytes)
        print(f"Sent message: {message}")

    def receive_message(self):
        try:
            # Read the length of the incoming message (8 bytes for larger messages)
            message_length = self.client_socket.recv(8)
            if not message_length:
                return None
            message_length = int.from_bytes(message_length, byteorder='big')

            # Read the actual message based on the length
            message = b""
            while len(message) < message_length:
                chunk = self.client_socket.recv(
                    min(message_length - len(message), 1024))
                if not chunk:
                    break
                message += chunk

            if not message:
                return None

            message = message.decode()
            print(f"Received message: {message}")
            self.default_handle_message(message)
            return message
        except ConnectionResetError:
            print("Connection reset")
            raise ConnectionResetError
        except socket.timeout:
            print("Timeout occurred")
            raise socket.timeout

        return None

    def close(self):
        self.client_socket.close()
        print("Connection closed")

    def default_handle_message(self, message):
        if message.startswith("echo"):
            parts = message.split(',')
            t1 = float(parts[1])
            t2 = time.time()
            response_message = f"echo,{t1},{t2}"
            self.send_message(response_message)
        else:
            self.handle_message(message)
            pass

    def handle_message(self, message):
        print(f"!!! Got message: {message}")


if __name__ == "__main__":
    # client = SocketClientBase(host='192.168.137.1')
    client = SocketClientBase()
    client.connect()

    input('Press enter to stop.')
    # while True:
    #     response = client.receive_message()
    #     if response:
    #         print(f"Server response: {response}")
    #     else:
    #         break

    client.close()
