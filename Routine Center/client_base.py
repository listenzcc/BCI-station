import time
import json
import socket
import random
import contextlib

from queue import Queue
from threading import Thread, RLock


class MyBag(dict):
    _rlock = RLock()

    def __init__(self):
        super().__init__()

    @contextlib.contextmanager
    def freeze_bag(self):
        '''Lock the bag for operations.'''
        self._rlock.acquire()
        try:
            yield
        finally:
            self._rlock.release()

    def dumps(self):
        with self.freeze_bag():
            return json.dumps(self)

    def insert_letter(self, letter):
        '''
        Insert a letter into the bag.
        Automatically generate the list for repeated uid.

        :param letter: The letter to insert.
        '''
        # Make sure the letter is unchanged.
        letter = letter.copy()
        with self.freeze_bag():
            uid = letter.get('uid')
            # Already have the letter of uid.
            if uid in self:
                # Already the list, append.
                if isinstance(self[uid], list):
                    self[uid].append(letter)
                # Not the list, create the list and append the two.
                if isinstance(self[uid], dict):
                    self[uid] = [self[uid], letter]
            # Not have the letter uid.
            else:
                self.update({uid: letter})

    def fetch_letter(self, uid):
        '''
        Fetch a letter from the bag by its uid.

        :param uid: The uid of the letter to fetch.

        :return: The letter if exists, otherwise None.
        '''
        with self.freeze_bag():
            if uid in self:
                letter = self.pop(uid)
                return letter


class MailMan:
    '''
    The mail man for the communication letters.
    '''
    # Initialize bags.
    # Good letters.
    bag_finished = MyBag()
    # Pending letters.
    bag_pending = MyBag()
    # Bad letters.
    bag_failed = MyBag()
    # Normal log.
    bag_history = MyBag()

    bags = {
        'Bag-Finished': bag_finished,
        'Bag-Pending': bag_pending,
        'Bag-Failed': bag_failed,
        'Bag-History': bag_history
    }

    # Initialize mailman with the session name.
    # The name is unique.
    session_name = f'{time.time()}-{random.random()}'

    # Initialize letter index as 0, it naturally grows to idx every letters.
    letter_idx = 0

    def __init__(self, session_name: str = None):
        if session_name is None:
            self.session_name = f'{time.time()}-{random.random()}'
        else:
            self.session_name = session_name

    def mk_letter(self, src: str, dst: str, content: str, timestamp: float = None):
        '''
        Make the letter with the given content.

        :param src: Source of the letter.
        :param dst: Destination of the letter.
        :param content: Content of the letter.
        :param timestamp: Timestamp of the letter.
        '''
        if not timestamp:
            timestamp = time.time()

        # Make the uid for the letter
        uid = f'{self.session_name}-{self.letter_idx}'
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
        self.bag_history.insert_letter(letter)
        return letter

    def pass_letter(self, letter: dict, path_uid: str):
        '''
        Pass the letter.
        The path_uid is recorded in the _stations array in the letter.

        :param letter: The letter to be passed.
        :param path_uid: The path is passed with.

        :return: The letter after passed.
        '''
        t = time.time()
        letter['_stations'].append((path_uid, t))
        return letter


class MailMan_Deprecated(object):
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

    def mk_letter(self, src: str, dst: str, content: str, timestamp: float = None):
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

    def recv_letter(self, letter: dict, path_uid: str):
        t = time.time()
        letter['_stations'].append((path_uid, t))
        return letter


class BaseClientSocket:
    '''
    Base client talks to the routing center.
    During the connecting, the connection quality is measured.
    It blocks the connection process until it receives 'YouAreGoodToGo' message.
    '''
    # Client setup, may be overridden by subclasses.
    path = '/client/baseClient'
    uid = 'bc-0'
    key_code = b'12345678'

    # Use urlparse it derives:
    # ParseResult(scheme='', netloc='', path=path, params='', query=uid, fragment='')
    # See __init__ for detail.
    path_uid = f'{path}?{uid}'
    mm = MailMan(f'{path}?{uid}?{time.time()}')

    # Socket setup, may be overridden by subclass and __init__ method.
    host = 'localhost'
    port = 12345
    timeout = 1000

    # Good to go stuff
    good_to_go_queue = Queue(10)

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

    def keep_alive(self, interval: float = 5):
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
                    print(f'Connection is broken : {err}')
                    break
                except Exception as err:
                    print(f'Got exception: {err}')
                    raise err
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
        # print(f"Sent message: {message}")
        return message

    def connect(self):
        '''Connect to the self.host:self.port.'''
        self.client_socket.connect((self.host, self.port))
        print(f"Connecting to server at {self.host}:{self.port}")
        self.send_initial_info()
        self.keep_receiving()
        self.keep_alive()
        # Block until the connection is fully set.
        _ = self.good_to_go_queue.get()
        print(f"Connected to server at {self.host}:{self.port}")

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
        self.handle_incoming_message(message)
        return message

    def handle_incoming_message(self, message: str):
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

        # Handle acquire bag messages.
        elif message.startswith('AcquireBags'):
            for name, bag in self.mm.bags.items():
                if name in message:
                    # print(f'Acquired bag: {name}')
                    self.send_message(name + ':' + bag.dumps())

        # Handle good to go message.
        # Release the blocking status.
        elif message.startswith('YouAreGoodToGo'):
            self.good_to_go_queue.put_nowait(message)

        # Handle other messages.
        else:
            self.handle_message(message)
        return

    def handle_message(self, message: str):
        '''
        Handle the receiving [message].
        ! The method should be overridden for customized usage.

        Args:
            message (str): Message to be handled.
        '''
        # print(f"!!! Got message: {message}")
        return


if __name__ == "__main__":
    # client = BaseClientSocket(host='192.168.137.1')
    client = BaseClientSocket()
    client.connect()
    input('Press enter to stop.')
    client.close()
