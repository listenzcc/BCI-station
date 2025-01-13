import time
import socket
import contextlib
import tkinter as tk
from tkinter import ttk  # Import ttk from tkinter
from threading import Thread, RLock


class MailMan(object):
    # Initialize some bags.
    bag_await_response = {}
    bag_finished = {}
    bag_expired = {}
    bag_pending = {}

    # Initialize mailman with the session name.
    session_name = f'{time.time()}'

    # Initialize letter index as 0, it naturally grows to idx every letters.
    letter_idx = 0

    # Lock for the bag operation.
    bag_lock = RLock()

    def __init__(self, session_name: str = None):
        if session_name:
            self.session_name = session_name
        self.ui_update_needed = False
        self.init_ui()

    @contextlib.contextmanager
    def lock_bag(self):
        '''Lock the bag for operations.'''
        self.bag_lock.acquire()
        try:
            yield
        finally:
            self.bag_lock.release()

    def insert_pending_letter(self, letter):
        with self.lock_bag():
            self.bag_pending[letter['uid']] = letter
            self.ui_update_needed = True

    def remove_pending_letter(self, uid):
        with self.lock_bag():
            if uid in self.bag_pending:
                letter = self.bag_pending.pop(uid)
                self.ui_update_needed = True
                return letter


    def retrieve_letter_in_waiting(self, uid):
        '''
        Checkout the letter with the $uid.

        Args:
            uid (str): The unique identifier for the letter.
        '''
        with self.lock_bag():
            if uid in self.bag_await_response:
                letter = self.bag_await_response.pop(uid)
                self.ui_update_needed = True
                return letter
            else:
                return None

    def archive_await_letter(self, letter):
        '''
        Save the $letter as the awaiting letter.

        Args:
            letter (dict): A dictionary for the letter.
        '''
        with self.lock_bag():
            self.bag_await_response[letter['uid']] = letter
            self.ui_update_needed = True

    def archive_finished_letter(self, letter):
        '''
        Save the $letter as the finished letter.

        Args:
            letter (dict): A dictionary for the letter.
        '''
        with self.lock_bag():
            self.bag_finished[letter['uid']] = letter
            self.ui_update_needed = True
    
    def mark_expired_letter_with_uid(self, uid):
        '''
        Mark the letter of $uid as the expired letter.

        Args:
            uid (str): The uid of the expired letter.
        '''
        letter = self.retrieve_letter_in_waiting(uid)
        if letter:
            with self.lock_bag():
                self.bag_expired[uid] = letter
                self.ui_update_needed = True
            return letter
        else:
            return None

    def mk_letter(self, src: str, dst: str, content: str, timestamp: float=None):
        if not timestamp:
            timestamp = time.time()

        # Make the uid for the letter
        uid = f'{self.session_name}-{self.letter_idx}-{timestamp}'
        self.letter_idx += 1
        # The letter body
        letter = dict(
            # -- Required --
            # Content.
            content=content,
            # Routine info.
            src=src,
            dst=dst,
            # -- Automatic --
            uid=uid,
            # Prefix with _ refers the value is changed dynamically.
            # Appended at every node.
            _stations=[('origin', time.time())],
            # Translate into local times by the control center.
            _timestamp=timestamp)
        return letter

    def recv_letter(self, letter:dict, path_uid:str):
        t = time.time()
        letter['_stations'].append((path_uid, t))
        return letter

    def init_ui(self):
        '''Initialize the Tkinter UI.'''
        self.root = tk.Tk()
        self.root.geometry('600x400')  # Update width to 600 pixels
        self.root.title(f"MailMan Explorer - {self.session_name}")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(expand=1, fill="both")

        self.await_response_frame = tk.Frame(self.tabs)
        self.finished_frame = tk.Frame(self.tabs)
        self.expired_frame = tk.Frame(self.tabs)
        self.pending_frame = tk.Frame(self.tabs)

        self.tabs.add(self.await_response_frame, text="Await Response")
        self.tabs.add(self.finished_frame, text="Finished")
        self.tabs.add(self.expired_frame, text="Expired")
        self.tabs.add(self.pending_frame, text="Pending")

        self.await_response_listbox = tk.Listbox(self.await_response_frame)
        self.finished_listbox = tk.Listbox(self.finished_frame)
        self.expired_listbox = tk.Listbox(self.expired_frame)
        self.pending_listbox = tk.Listbox(self.pending_frame)

        self.await_response_scrollbar = tk.Scrollbar(self.await_response_frame, orient="vertical", command=self.await_response_listbox.yview)
        self.finished_scrollbar = tk.Scrollbar(self.finished_frame, orient="vertical", command=self.finished_listbox.yview)
        self.expired_scrollbar = tk.Scrollbar(self.expired_frame, orient="vertical", command=self.expired_listbox.yview)
        self.pending_scrollbar = tk.Scrollbar(self.pending_frame, orient="vertical", command=self.pending_listbox.yview)

        self.await_response_listbox.config(yscrollcommand=self.await_response_scrollbar.set)
        self.finished_listbox.config(yscrollcommand=self.finished_scrollbar.set)
        self.expired_listbox.config(yscrollcommand=self.expired_scrollbar.set)
        self.pending_listbox.config(yscrollcommand=self.pending_scrollbar.set)

        self.await_response_listbox.pack(side="left", expand=1, fill="both")
        self.await_response_scrollbar.pack(side="right", fill="y")
        self.finished_listbox.pack(side="left", expand=1, fill="both")
        self.finished_scrollbar.pack(side="right", fill="y")
        self.expired_listbox.pack(side="left", expand=1, fill="both")
        self.expired_scrollbar.pack(side="right", fill="y")
        self.pending_listbox.pack(side="left", expand=1, fill="both")
        self.pending_scrollbar.pack(side="right", fill="y")

        self.update_ui()
        self.schedule_ui_update()
        Thread(target=self.root.mainloop, daemon=True).start()

    def schedule_ui_update(self):
        '''Schedule periodic UI updates.'''
        self.update_ui()
        self.root.after(1000, self.schedule_ui_update)  # Update every second

    def update_ui(self):
        '''Update the UI with the current state of the bags.'''
        if self.ui_update_needed:
            self.await_response_listbox.delete(0, tk.END)
            self.finished_listbox.delete(0, tk.END)
            self.expired_listbox.delete(0, tk.END)
            self.pending_listbox.delete(0, tk.END)

            with self.lock_bag():
                for uid, letter in self.bag_await_response.items():
                    self.await_response_listbox.insert(tk.END, f"{uid}: {letter}")
                for uid, letter in self.bag_finished.items():
                    self.finished_listbox.insert(tk.END, f"{uid}: {letter}")
                for uid, letter in self.bag_expired.items():
                    self.expired_listbox.insert(tk.END, f"{uid}: {letter}")
                for uid, letter in self.bag_pending.items():
                    self.pending_listbox.insert(tk.END, f"{uid}: {letter}")

            self.ui_update_needed = False


class BaseClientSocket:
    # Client setup, may be overridden by subclasses.
    path = '/client/baseClient'
    uid = 'bc-0'
    key_code = b'12345678'

    # Use urlparse it derives:
    # ParseResult(scheme='', netloc='', path=path, params='', query=uid, fragment='')
    # See __init__ for detail.
    path_uid = None

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

        # Use urlparse it derives:
        # ParseResult(scheme='', netloc='', path=path, params='', query=uid, fragment='')
        self.path_uid = f'{self.path}?{self.uid}'

        # Establish the socket connection.
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(self.timeout)

    def keep_alive(self, interval:float=5):
        '''
        Send keep-alive request every [interval] seconds.

        Args:
            - interval (float), send keep-alive request every [interval] seconds, defaults to 5 seconds.
        '''
        def _keep_alive():
            while True:
                try:
                    self.send_message(f'Keep-Alive, {time.time()}')
                    time.sleep(interval)
                except (ConnectionAbortedError, ConnectionResetError, socket.timeout):
                    break
        Thread(target=_keep_alive, daemon=True).start()

    def keep_receiving(self):
        '''
        Keep receiving messages.
        '''
        def _receive_message():
            while True:
                try:
                    # The message output refers the message is processed well.
                    message = self.receive_message()
                except (ConnectionAbortedError, ConnectionResetError, socket.timeout) as err:
                    print(f'Known error occurred: {err}.')
                    break
        Thread(target=_receive_message, daemon=True).start()

    def send_initial_info(self):
        '''Send initial info, tell the server who am I.'''
        initial_message = f"{self.path},{self.uid}"
        # Attach the key to authorization purpose.
        self.send_message(initial_message, include_key=True)

    def send_message(self, message, include_key=False):
        '''
        Send the [message] to the server.
        The wrapped message format is 
            - If include_key, "8 bytes length" + "message bytes".
            - Else, "key bytes" + "8 bytes length" + "message bytes".

        Args:
            message (str): The message to send.
            include_key (bool): Whether to include the authorization key, defaults to False.
        '''
        message_bytes = message.encode()
        message_length = len(message_bytes).to_bytes(8, byteorder='big')
        if include_key:
            self.client_socket.sendall(
                self.key_code + message_length + message_bytes)
        else:
            self.client_socket.sendall(message_length + message_bytes)
        print(f"Sent message: {message}")

    def connect(self):
        '''Connect to the self.host:self.port.'''
        self.client_socket.connect((self.host, self.port))
        print(f"Connected to server at {self.host}:{self.port}")
        self.send_initial_info()
        self.keep_receiving()
        self.keep_alive()

    def close(self):
        '''Close the socket.'''
        self.client_socket.close()
        print("Connection closed")

    def receive_message(self):
        # Read the length of the incoming message (8 bytes for larger messages).
        message_length = self.client_socket.recv(8)
        if not message_length:
            return None
        message_length = int.from_bytes(message_length, byteorder='big')

        # Read the actual message based on the length.
        message = b""
        while len(message) < message_length:
            chunk = self.client_socket.recv(
                min(message_length - len(message), 1024))
            if not chunk:
                break
            message += chunk

        # Return None if the message is empty.
        if not message:
            return None

        # Decode the message into str format.
        message = message.decode()
        print(f"Received message: {message}")
        self.handle_incoming_message(message)
        return message


    def handle_incoming_message(self, message:str):
        '''
        Handle the receiving [message].
        '''
        # Handle the inner packages.
        if message.startswith("Echo"):
            # Handle the epoch package.
            parts = message.split(',')
            t1 = float(parts[1])
            t2 = time.time()
            response_message = f"Echo,{t1},{t2}"
            self.send_message(response_message)
        else:
            self.handle_message(message)
            pass

    def handle_message(self, message:str):
        '''
        Handle the receiving [message].
        ! The method should be overridden for customized usage.

        Args:
            message (str): Message to be handled.
        '''
        print(f"!!! Got message: {message}")


if __name__ == "__main__":
    # client = BaseClientSocket(host='192.168.137.1')
    client = BaseClientSocket()
    client.connect()
    input('Press enter to stop.')
    client.close()
