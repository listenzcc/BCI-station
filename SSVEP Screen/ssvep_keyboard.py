"""
File: ssvep_keyboard.py
Author: Chuncheng Zhang
Date: 2025-02-08
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    The screen display for SSVEP keyboard.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""

# %% ---- 2025-02-08 ------------------------
# Requirements and constants
import time
from timer import RunningTimer
import sys
import itertools
import numpy as np
from enum import Enum
from loguru import logger
from threading import Thread, RLock

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel
from keyboard_layout import MyKeyboard

# Initialize the QApplication in the first place.
qapp = QApplication(sys.argv)

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
        patch_size = int((ws[1] - ws[0]) * (1-self.paddingRatio))

        layout = [
            dict(patch_idx=patch_idx,
                 patch_size=patch_size,
                 x=int(self.w + d * j + (d - patch_size) / 2),
                 y=int(self.n + d * i + (d - patch_size) / 2),
                 )
            for patch_idx, (i, j) in enumerate(
                itertools.product(range(rows), range(self.columns)))]

        return layout


class QtComponents:
    # Components
    qapp = qapp
    window = QMainWindow()
    pixmap_container = QLabel(window)
    width = None
    height = None

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

        # Only hide window frame
        # self.window.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Fetch the screen size and set the size for the window
        screen = self.qapp.primaryScreen()
        self.width = screen.size().width() // 2
        self.height = screen.size().height()

        # Set the window size
        self.window.resize(self.width, self.height)

        # Put the window to the right
        self.window.move(self.width, 0)

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

    def __init__(self):
        super().__init__()
        self._handle_focus_change()
        logger.info(f'Initialized {self}')

    def reset_img(self):
        '''Reset the image object.'''
        # Generate fully transparent image and its drawer
        mat = np.zeros((self.width, self.height, 4), dtype=np.uint8)
        mat += 100
        self.img = Image.fromarray(mat).convert('RGBA')
        self.img_drawer = ImageDraw.Draw(self.img)

        # Repaint with default img for startup
        self.put_img_into_pixmap_container()

        logger.debug(f'Make img, img_drawer as {self.img}, {self.img_drawer}')
        return

    def put_img_into_pixmap_container(self, img: Image = None):
        '''
        Repaint with the given img.
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

    def main_loop(self):
        ''' Main loop for SSVEP display. '''
        header_height = 400

        # Reset the timer.
        self.rt.reset()

        # Reset the ssvep layout box.
        ssvep_screen_layout = SSVEPScreenLayout()
        ssvep_screen_layout.reset_box(
            0, header_height, self.width, self.height)

        # The flipping rate is slower when the speed_factor is lower.
        speed_factor = 1
        # speed_factor = 0.5
        change_char_step = 6  # seconds
        change_char_next_passed = change_char_step

        layout = ssvep_screen_layout.get_layout()
        num_keys = len(layout)
        fixed_positions = {e['patch_idx']: k for e, k in zip(
            layout[-3:], ['*Back', '*Space', '*Enter'])}
        keys, cue, cue_idx = self.mkb.mk_layout(num_keys, fixed_positions)

        self.reset_img()
        while self.rt.running:
            # Update the timer to the next frame.
            self.rt.step()

            # Get the current time.
            passed = self.rt.get()

            # Modify the passed seconds with speed_factor.
            z = passed * speed_factor

            if z > change_char_next_passed:
                change_char_next_passed += change_char_step
                self.reset_img()

                layout = ssvep_screen_layout.get_layout()
                num_keys = len(layout)
                fixed_positions = {e['patch_idx']: k for e, k in zip(
                    layout[-3:], ['*Back', '*Space', '*Enter'])}
                keys, cue, cue_idx = self.mkb.mk_layout(
                    num_keys, fixed_positions)

            # Compute trial ratio, always in (0, 1)
            tr = 1-(change_char_next_passed - z) / change_char_step
            seconds_in_trial = tr * change_char_step

            with self.rlock:
                # Clear only the text area before drawing new text
                self.img_drawer.rectangle(
                    (0, 0, self.width, header_height), fill=(0, 0, 0, 0))

                self.img_drawer.text(
                    (0, header_height/2), f'{z:.2f} | {seconds_in_trial:.2f}', font=large_font, anchor='lt')

                # Draw the progressing bar.
                self.img_drawer.rectangle((0, header_height-2, self.width, header_height),
                                          fill=(150, 150, 150, 0))
                self.img_drawer.rectangle((0, header_height-2, (1-tr)*self.width, header_height),
                                          fill=(150, 150, 150, 150))

                # Draw the patch.
                for patch in layout:
                    x = patch['x']
                    y = patch['y']
                    sz = patch['patch_size']
                    idx = patch['patch_idx']

                    # Draw the patch.
                    # Compute omega and phase.
                    omega, phase = self.get_omega_phase(idx)
                    c = 0.5 + 0.5 * \
                        np.cos(seconds_in_trial*omega*2*np.pi + phase)
                    c = int(c*255)

                    # print(patch, c)
                    self.img_drawer.rectangle((x, y, x+sz, y+sz),
                                              fill=(c, c, c, c))
                    # Draw the idx.
                    self.img_drawer.text((x, y), f'{idx}', font=small_font)

                    # Draw the char.
                    _char = keys[idx]
                    _font = large_font if len(_char) == 1 else small_font
                    self.img_drawer.text(
                        (x+sz/2, y+sz/2), _char, font=_font, anchor='mm')

                    # Draw the cue hinter.
                    if idx == cue_idx:
                        self.img_drawer.rectangle(
                            (x+sz*0.8, y, x+sz, y+sz*0.2), fill=(150, 0, 0, 255))

            # Blink on the right top corner in 50x50 pixels size if not focused
            if not self.flag_has_focus:
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


# %% ---- 2025-02-08 ------------------------
# Play ground


# %% ---- 2025-02-08 ------------------------
# Pending


# %% ---- 2025-02-08 ------------------------
# Pending
