import socket
import threading
import tkinter as tk
from tkinter import messagebox

# ...existing code...


class ControlCenter:
    def __init__(self, host='localhost', port=12345, valid_key=b'12345678'):
        self.host = host
        self.port = port
        self.valid_key = valid_key
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = {}
        self.gui = None
        self.latest_message = None

    def start_server(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")
        threading.Thread(target=self.accept_clients).start()

    def accept_clients(self):
        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Client {client_address} connected")
            threading.Thread(target=self.handle_client, args=(
                client_socket, client_address)).start()

    def handle_client(self, client_socket, client_address):
        try:
            # Read the advanced key code (8 bytes)
            key_code = client_socket.recv(8)
            if key_code != self.valid_key:
                print(
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

            if not message:
                return

            message = message.decode()
            print(f"Received message: {message}")
            client_info = message.split(',')
            client_name = client_info[0]
            client_uid = client_info[1]
            self.clients[client_address] = (
                client_socket, client_name, client_uid)
            self.update_client_list()
            self.update_latest_message(
                f"{client_name} ({client_uid}) connected")

            while True:
                message_length = client_socket.recv(8)
                if not message_length:
                    break
                message_length = int.from_bytes(
                    message_length, byteorder='big')

                message = b""
                while len(message) < message_length:
                    chunk = client_socket.recv(
                        min(message_length - len(message), 1024))
                    if not chunk:
                        break
                    message += chunk

                if not message:
                    break

                message = message.decode()
                print(f"Received message: {message}")
                self.update_latest_message(message)
                # Handle the message from the client
        except ConnectionResetError:
            pass
        finally:
            client_socket.close()
            del self.clients[client_address]
            self.update_client_list()
            self.update_latest_message(
                f"{client_name} ({client_uid}) disconnected")

    def update_latest_message(self, message):
        self.latest_message.set(message)

    def update_client_list(self):
        for widget in self.client_list_frame.winfo_children():
            widget.destroy()
        for client_address, (client_socket, client_name, client_uid) in self.clients.items():
            tk.Label(self.client_list_frame,
                     text=f"{client_name} ({client_uid})").pack()

    def start_gui(self):
        self.gui = tk.Tk()
        self.latest_message = tk.StringVar()
        self.gui.title("Control Center")
        self.gui.geometry("400x300")
        tk.Label(self.gui, text="Control Center Monitoring").pack()
        tk.Label(self.gui, textvariable=self.latest_message).pack()
        self.client_list_frame = tk.Frame(self.gui)
        self.client_list_frame.pack()
        tk.Button(self.gui, text="Exit", command=self.close_server).pack()
        self.gui.protocol("WM_DELETE_WINDOW", self.close_server)
        self.gui.mainloop()

    def close_server(self):
        for client_socket, _, _ in self.clients.values():
            client_socket.close()
        self.server_socket.close()
        self.gui.quit()

    def run(self):
        self.start_server()
        self.start_gui()


if __name__ == "__main__":
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
