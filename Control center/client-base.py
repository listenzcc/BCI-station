import socket


class ClientBase:
    name = 'Base client'
    uid = 'bc-0'
    key_code = b'12345678'

    def __init__(self, host='localhost', port=12345, timeout=10):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(timeout)

    def connect(self):
        self.client_socket.connect((self.host, self.port))
        print(f"Connected to server at {self.host}:{self.port}")
        self.send_initial_info()

    def send_initial_info(self):
        initial_message = f"{self.name},{self.uid}"
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
            return message
        except (ConnectionResetError, socket.timeout):
            return None

    def close(self):
        self.client_socket.close()
        print("Connection closed")


if __name__ == "__main__":
    client = ClientBase()
    client.connect()
    client.send_message("Hello, Server!")
    response = client.receive_message()
    if response:
        print(f"Server response: {response}")
    client.close()
