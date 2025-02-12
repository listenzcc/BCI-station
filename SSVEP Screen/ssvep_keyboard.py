"""
File: ssvep_keyboard.py
Author: Chuncheng Zhang
Date: 2025-02-08
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    The screen display for SSVEP keyboard.

Decoding process and communication:

    1. The SSVEP trial starts.
    2. Write the decoding request as 
        content = json.dumps({
            'action': 'SSVEP trial starts.',
            'cue': cue_patch['_char'],
            'cueOmega': cue_patch['_omega']
        })
    3. Wrap the content into letter.
        3.1. Send the letter.
        3.2. Insert the letter to the pending bag.
    4. Wait for decoding in 5 seconds.
        4.1 If received decoding results on time,
            mark the decoding result into SSVEP patches,
            and archive the letter and result letter into finish bag.
        4.2 If not received decoding results on time,
            and archive the letter into failed bag.

    The received letter's content should have 'decodedOmega' attribute.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""

# %% ---- 2025-02-08 ------------------------
# Requirements and constants
import sys
import json
import time
import socket
import itertools
import numpy as np

from enum import Enum
from queue import Queue
from loguru import logger
from timer import RunningTimer
from omegaconf import OmegaConf
from threading import Thread, RLock

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel

from keyboard_layout import MyKeyboard
from sync.routine_center.client_base import BaseClientSocket


# Initialize the QApplication in the first place.
qapp = QApplication(sys.argv)

CONFIG = OmegaConf.load('config.yaml')

small_font = ImageFont.truetype("arial.ttf", 24)
large_font = ImageFont.truetype("arial.ttf", 64)
small_font = ImageFont.truetype("c:\\windows\\fonts\\msyhl.ttc", 24)
large_font = ImageFont.truetype("c:\\windows\\fonts\\msyhl.ttc", 64)
small_font = ImageFont.truetype("c:\\windows\\fonts\\simhei.ttf", 24)
large_font = ImageFont.truetype("c:\\windows\\fonts\\simhei.ttf", 64)
# %% ---- 2025-02-08 ------------------------
# Function and class


class SSVEPInputState(Enum):
    freedomInput = '自由输入'
    cuedInput = '指定输入'
    outputSelection = '输出选择'


class MyClient(BaseClientSocket):
    path = '/client/ssvepKeyboard'
    uid = 'ssvep-keyboard-1'
    queue = Queue(10)

    def __init__(self, host=None, port=None, timeout=None):
        super().__init__(**dict(host=host, port=port, timeout=timeout))
        logger.info(f'Initializing client: {self.path_uid}')
        pass

    def handle_message(self, message):
        super().handle_message(message)
        letter = json.loads(message)
        # Stamp the letter
        letter['_stations'].append((self.path_uid, time.time()))

        # Wait for the receiving letter which I have sent.
        if lt := self.mm.bag_pending.fetch_letter(letter['uid']):
            lt.update({'_finished_at': time.time()})
            c2 = json.loads(letter['content'])
            self.queue.put_nowait(c2['decodedOmega'])
            self.mm.bag_finished.insert_letter(letter)
            self.mm.bag_finished.insert_letter(lt)


# Socket client
client = MyClient()
client.connect()


class SSVEPFrequency:
    omegas = np.linspace(5, 30, 26)
    phases = np.linspace(0, 2*np.pi, 8)

    def get_omega_phase(self, idx):
        phase = self.phases[idx // len(self.omegas)]
        omega = self.omegas[idx % len(self.omegas)]
        return omega, phase


class SSVEPScreenLayout:
    w = 0  # left bound
    e = 100  # right bound
    n = 0  # top bound
    s = 100  # bottom bound
    columns: int = 6  # number of columns
    paddingRatio = 0.2

    def reset_box(self, w, n, e, s):
        self.w = w
        self.e = e
        self.n = n
        self.s = s

    def reset_columns(self, columns: int):
        self.columns = columns
        return columns

    def get_layout(self):
        '''
        Get the layout of the empty key patches.

        layout = [
            dict(patch_idx=patch_idx,
                 patch_size=patch_size,
                 x=int(self.w + d * j + (d - patch_size) / 2),
                 y=int(self.n + d * i + (d - patch_size) / 2),
                 )
            for patch_idx, (i, j) in enumerate(
                itertools.product(range(rows), range(self.columns)))]

        :return: the layout.

        Patch layout:
                    n
            1, 2, 3, ............ 
            c+1, c+2, c+3, ......
            2c+1, 2c+2, 2c+3, ...
        w   .....................    e
            .....................
            .....................
            rc+1, rc+2, rc+3, ...
                    s

        Patch size:
        +------- d -------+
        |                 |
        |  (x, y)-----+   |
        |    |        |   |
        |    |        |   |
        |    +--size--+   |
        |                 |
        +-----------------+

        '''
        ws = np.linspace(self.w, self.e, self.columns+1)[:-1]
        d = int(ws[1] - ws[0])
        rows = int((self.s - self.n) / d)
        patch_size = int(d * (1-self.paddingRatio))

        layout = [
            dict(patch_idx=patch_idx,
                 patch_size=patch_size,
                 x=int(self.w + d * j + (d - patch_size) / 2),
                 y=int(self.n + d * i + (d - patch_size) / 2),
                 )
            for patch_idx, (i, j) in enumerate(
                itertools.product(range(rows), range(self.columns)))]

        return layout


class CustomizedQMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

    def has_frame(self):
        ''' Tell if the window has a frame.

        :return: True if the window has a frame, False otherwise.
        '''
        if self.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return False
        return True


class QtComponents:
    # Components
    qapp = qapp
    window = CustomizedQMainWindow()  # QMainWindow()
    pixmap_container = QLabel(window)
    width = CONFIG.SSVEPScreen.width  # None
    height = CONFIG.SSVEPScreen.height  # None

    def __init__(self):
        self.prepare_window()

    def show_window(self):
        ''' Show the window '''
        self.window.show()
        logger.debug('Shown window')
        return

    def prepare_window(self):
        '''
        Prepare the window,
        - Set its size, position and transparency.
        - Set the self.pixmap_container geometry accordingly.
        '''
        # Translucent image by its RGBA A channel
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Disable frame and keep the window on the top layer
        # It is necessary to set the FramelessWindowHint for the WA_TranslucentBackground works
        self.window.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                                   Qt.WindowType.WindowStaysOnTopHint)

        # Set overall opacity.
        overall_opacity = 1.0
        self.window.setWindowOpacity(overall_opacity)

        # Fetch the screen size and set the size for the window
        screen = self.qapp.primaryScreen()
        screen_width = screen.size().width()
        screen_height = screen.size().height()
        # self.width = screen.size().width() // 2
        # self.height = screen.size().height()

        # Set the window size
        self.window.resize(self.width, self.height)

        # Put the window to the right
        self.window.move(screen_width-self.width, 0)

        # Set the pixmap_container accordingly,
        # and it is within the window bounds
        self.pixmap_container.setGeometry(0, 0, self.width, self.height)

        logger.debug(
            f'Reset window size to {self.width}, {self.width}, and reset other stuff')
        return


class AdditionalFunctions(QtComponents):
    flag_has_focus: bool = True

    def _handle_focus_change(self):
        '''
        Handle the focus change event.
        '''
        def focus_changed(e):
            self.flag_has_focus = e is not None
            logger.debug(f'Focus changed to {self.flag_has_focus}')
        self.qapp.focusWindowChanged.connect(focus_changed)
        logger.debug(f'Handled focus changed with {focus_changed}')
        return


class SSVEPScreenPainter(AdditionalFunctions, SSVEPFrequency):
    # Timer
    rt = RunningTimer('SSVEPBackendTimer')

    # MyKeyboard
    mkb = MyKeyboard()

    # Parameters in dynamic
    img: Image = None
    img_drawer: ImageDraw = None
    pixmap: QPixmap = None
    on_going_thread: Thread = None
    rlock = RLock()

    # Keyboard layout parameters
    header_height: int = CONFIG.SSVEPScreen.headerHeight  # 200
    num_columns: int = 6
    current_layout: list = []
    current_cue: tuple = None

    def __init__(self):
        super().__init__()
        self._handle_focus_change()
        logger.info(f'Initialized {self}')

    def reset_img(self):
        '''Reset the image object.'''
        # Generate fully transparent image and its drawer
        mat = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        mat += 100
        self.img = Image.fromarray(mat).convert('RGBA')
        self.img_drawer = ImageDraw.Draw(self.img)

        # Repaint with default img for startup
        self.repaint()

        logger.debug(f'Make img, img_drawer as {self.img}, {self.img_drawer}')
        return

    def repaint(self, img: Image = None):
        '''
        Repaint with the given img.
        It puts img into pixmap_container
        If it is None, using self.img as default.

        The pipeline is
        img -> pixmap -> pixmap_container

        Args:
            - img: Image object, default is None.
        '''

        # Use self.img if nothing is provided
        if img is None:
            img = self.img

        # img -> pixmap
        self.pixmap = QPixmap.fromImage(ImageQt(img))

        # pixmap -> pixmap_container
        self.pixmap_container.setPixmap(self.pixmap)

        return

    def start(self):
        ''' Start the main_loop '''
        # Prevent the mainloop from starting repeatedly.
        if self.on_going_thread:
            logger.error(
                f'Failed to start the main_loop since one is already running, {self.on_going_thread}.')
            return

        self.on_going_thread = Thread(target=self.main_loop, daemon=True)
        self.on_going_thread.start()
        return

    def stop(self):
        ''' Stop the running main loop '''
        if not self.on_going_thread:
            logger.error(
                'Failed to stop the main_loop since it is not running.')
            return

        # Tell the main_loop to stop.
        self.rt.running = False

        # Wait until the main_loop stops.
        logger.debug('Waiting for main_loop to stop.')
        self.on_going_thread.join()
        logger.debug('Stopped the main_loop.')

        # Reset the self.on_going_thread to None
        self.on_going_thread = None

        return

    def get_img_safety(self):
        with self.rlock:
            return self.img

    def wait_for_decoding(self, letter: dict):
        # Wait for 5 seconds at most.
        # If not received, mark as expired failing.
        try:
            decoded_omega = client.queue.get(timeout=5)
        except Exception as err:
            if lt := client.mm.bag_pending.fetch_letter(letter['uid']):
                lt.update({'_fail_reason': f'{type(err)}({err})'})
                client.mm.bag_failed.insert_letter(lt)
            return

        # Got results, write it into every patch.
        for patch in self.current_layout:
            patch['__decoded_omega'] = decoded_omega
        return

    def main_loop(self):
        ''' Main loop for SSVEP display. '''

        # Reset the timer.
        self.rt.reset()

        # Reset the ssvep layout box.
        ssvep_screen_layout = SSVEPScreenLayout()
        ssvep_screen_layout.reset_box(
            0, self.header_height, self.width, self.height)

        # The flipping rate is slower when the speed_factor is lower.
        speed_factor = 1
        # speed_factor = 0.5
        change_char_step = 7  # seconds
        change_char_next_passed = change_char_step

        def setup_trial():
            # Acquire the layout.
            ssvep_screen_layout.reset_columns(self.num_columns)
            layout = ssvep_screen_layout.get_layout()

            # Generate keys.
            # It also generates cue and cue_idx.
            num_keys = len(layout)
            fixed_positions = {e['patch_idx']: k for e, k in zip(
                layout[-3:], ['*Back', '*Space', '*Enter'])}
            keys, cue, cue_idx = self.mkb.mk_layout(num_keys, fixed_positions)

            # Fill the keys, cue, and cue_idx into layout.
            for i, v in enumerate(layout):
                omega, phase = self.get_omega_phase(i)
                v.update({
                    '_char': keys[i],
                    '_cue_flag': i == cue_idx,
                    '_omega': omega,
                    '_phase': phase,
                    '__decoded_omega': None
                })

            self.current_layout = layout
            self.current_cue = (cue, cue_idx)

            content = {
                'action': 'SSVEP trial starts.',
                'cue': None,
                'cueOmega': None
            }
            if cue_idx:
                cue_patch = layout[cue_idx]
                content.update({
                    'cue': cue_patch['_char'],
                    'cueOmega': cue_patch['_omega']
                })
            content = json.dumps(content)
            letter = client.mm.mk_letter(
                src=client.path_uid, dst='/eeg/monitor', content=content)
            print(json.loads(content))
            client.send_message(json.dumps(letter))
            client.mm.bag_pending.insert_letter(letter)
            Thread(target=self.wait_for_decoding,
                   args=(letter,), daemon=True).start()

            return layout, cue, cue_idx

        # Make the first trial
        layout, cue, cue_idx = setup_trial()

        self.reset_img()
        while self.rt.running:
            # Update the timer to the next frame.
            self.rt.step()

            # Get the current time.
            passed = self.rt.get()

            # Modify the passed seconds with speed_factor.
            z = passed * speed_factor

            # It is time to process the latest trial.
            if z > change_char_next_passed:
                # If has cue
                cue, cue_idx = self.current_cue
                if cue:
                    # it is corrected decoded, append into the input_buffer.
                    if self.current_layout[cue_idx]['__decoded'] == self.current_layout[cue_idx]['_omega']:
                        self.mkb.append_input_buffer(cue)
                    # it is not corrected decoded, push it back into the cue_sequence
                    else:
                        self.mkb.push_cue_sequence(cue)

                # Get the layout of the next trial.
                layout, cue, cue_idx = setup_trial()

                # Reset the image.
                self.reset_img()

                # Reset the next judgement time.
                change_char_next_passed += change_char_step

            # Compute trial ratio, always in (0, 1)
            tr = 1-(change_char_next_passed - z) / change_char_step
            seconds_in_trial = tr * change_char_step

            with self.rlock:
                # Clear only the text area before drawing new text.
                self.img_drawer.rectangle(
                    (0, 0, self.width, self.header_height), fill=(0, 0, 0, 0))

                # Draw the time issue.
                self.img_drawer.text(
                    (self.width, 0), f'{z:.2f} | {seconds_in_trial:.2f}',
                    font=small_font, anchor='rt')

                # Draw the current input.
                self.img_drawer.text(
                    (0, self.header_height//2), ''.join(self.mkb.input_buffer),
                    font=large_font, anchor='lt')

                # Draw the progressing bar.
                self.img_drawer.rectangle((0, self.header_height-2, self.width, self.header_height),
                                          fill=(150, 150, 150, 0))
                self.img_drawer.rectangle((0, self.header_height-2, (1-tr) * self.width, self.header_height),
                                          fill=(150, 150, 150, 150))

                # Draw the patch.
                for patch in self.current_layout:
                    x = patch['x']
                    y = patch['y']
                    sz = patch['patch_size']
                    idx = patch['patch_idx']
                    _char = patch['_char']
                    omega = patch['_omega']
                    phase = patch['_phase']
                    cue_flag = patch['_cue_flag']
                    decoded_omega = patch['__decoded_omega']

                    # Draw the patch.
                    # Compute omega and phase.
                    c = 0.5 + 0.5 * \
                        np.cos(seconds_in_trial*omega*2*np.pi + phase)
                    c = int(c*255)

                    # Draw the patch.
                    self.img_drawer.rectangle((x, y, x+sz, y+sz),
                                              fill=(c, c, c, c))
                    # Draw the idx.
                    self.img_drawer.text((x, y), f'{idx}', font=small_font)

                    # Draw the char.
                    _font = large_font if len(_char) == 1 else small_font
                    self.img_drawer.text(
                        (x+sz/2, y+sz/2), _char, font=_font, anchor='mm')

                    # Draw the cue hinter.
                    if cue_flag:
                        self.img_drawer.rectangle(
                            (x+sz*0.8, y, x+sz, y+sz*0.2), fill=(150, 0, 0, 255))
                        patch['__decoded'] = omega

                    # Draw the decoded frame.
                    if omega == decoded_omega:
                        self.img_drawer.rectangle(
                            (x-1, y-1, x+sz+1, y+sz+1), outline='green', width=7)

            # Blink on the right top corner in 50x50 pixels size if not focused
            if False and not self.flag_has_focus:
                c = tuple(np.random.randint(0, 256, 3))
                self.img_drawer.rectangle(
                    (self.width-50, 0, self.width, 50), fill=c)

            # Paint
            self._on_paint_subsystem()

            # Continue after sleep awhile.
            time.sleep(0.001)

        logger.debug('Main loop stopped')
        return

    def _on_paint_subsystem(self):
        '''Subsystem requires rewrite'''
        return


class ResponseStatus(Enum):
    '''Response to the NiceGUI'''
    # Everything is fine.
    OK = 'OK'
    # Message is good, but can not operate properly.
    FAIL = 'FAIL'
    # Message is bad.
    ERROR = 'ERROR'


RS = ResponseStatus


def dumps(dct):
    '''
    Dumps the dictionary with json.
    It converts the Enum into the value.

    :param dct: input dictionary.
    '''

    return json.dumps({e: v.value if isinstance(v, Enum) else v for e, v in dct.items()})


class SSVEPScreenPainterWithSocket(SSVEPScreenPainter):
    host = CONFIG.SSVEPScreen.host  # 'localhost'
    port = CONFIG.SSVEPScreen.port  # 36501
    encoding = CONFIG.SSVEPScreen.encoding  # 'utf-8'
    socket_is_running = False

    def __init__(self):
        super().__init__()

    def start_socket_server(self):
        Thread(target=self.serve_forever, daemon=True).start()

    def stop_socket_server(self):
        self.socket_is_running = False

    def serve_forever(self):
        ''' Establish the socket server to handle client requests. '''
        if self.socket_is_running:
            logger.warning(
                f'Socket server is already running {self.host}:{self.port}')
            return

        self.socket_is_running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            logger.info(f'Socket server listening on {self.host}:{self.port}')

            while self.socket_is_running:
                client_socket, addr = server_socket.accept()
                with client_socket:
                    # logger.info(f'Connected by {addr}')
                    while True:
                        # Read message length header
                        raw_msglen = self._recv_all(client_socket, 4)
                        if not raw_msglen:
                            break
                        msglen = int.from_bytes(raw_msglen, byteorder='big')
                        # Read the message data
                        data = self._recv_all(client_socket, msglen)
                        if not data:
                            break
                        response = self.handle_message(
                            data.decode(self.encoding))
                        response_bytes = response.encode(self.encoding)
                        # Send response with length header
                        client_socket.sendall(len(response_bytes).to_bytes(
                            4, byteorder='big') + response_bytes)

            # logger.info('Socket connection stopped')
            return

    def _recv_all(self, sock, n):
        ''' Helper function to receive n bytes or return None if EOF is hit '''
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def handle_message(self, message):
        ''' Handle message from client. '''
        try:
            command = json.loads(message)
            action = command.get('action')

            # Set num columns.
            if action == 'set_num_columns':
                if n := command.get('num_columns'):
                    self.num_columns = int(n)
                    return dumps({'status': RS.OK})
                return dumps({'status': RS.FAIL})

            # Get input buffer.
            elif action == 'get_input_buffer':
                return dumps({'status': RS.OK, 'input_buffer': self.mkb.input_buffer})

            # Get cue sequence.
            elif action == 'get_cue_sequence':
                return dumps({'status': RS.OK, 'cue_sequence': self.mkb.cue_sequence})

            # Get current cue.
            elif action == 'get_current_cue':
                if i := self.current_cue[1]:
                    return dumps({'status': RS.OK, 'current_cue': self.current_layout[i]})
                return dumps({'status': RS.FAIL, 'message': 'Not cue.'})

            # Get current layout.
            elif action == 'get_current_layout':
                return dumps({'status': RS.OK, 'current_layout': self.current_layout})

            # Append cue sequence.
            elif action == 'append_cue_sequence':
                if cues := command.get('cues'):
                    cues = [e for e in cues]
                    print(cues)
                    self.mkb.extend_cue_sequence(cues)
                    print(self.mkb.cue_sequence)
                    return dumps({'status': RS.OK})
                return dumps({'status': RS.FAIL})

            # Shouldn't happen.
            assert False, 'Invalid message'

        except Exception as e:
            logger.error(f'Error handling message: {e}')
            return dumps({'status': RS.ERROR, 'exception': str(e)})

        finally:
            # logger.debug(f'Received: {message}...')
            pass


# %% ---- 2025-02-08 ------------------------
# Play ground


# %% ---- 2025-02-08 ------------------------
# Pending


# %% ---- 2025-02-08 ------------------------
# Pending
