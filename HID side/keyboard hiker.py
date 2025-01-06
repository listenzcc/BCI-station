"""
File: keyboard hiker.py
Author: Chuncheng Zhang
Date: 2025-1-16
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Hike keyboard events.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2024-11-15 ------------------------
# Requirements and constants
import tkinter
from tkinter import ttk

import sys
import keyboard
import argparse

from loguru import logger
from rich import print, inspect

from .sync.control_center.client_base import SocketClientBase

logger.add('log/keyboard hiker.log', rotation='5 MB')

# %% ---- 2024-11-15 ------------------------
# Function and class


class SocketClient(SocketClientBase):
    path = '/client/keyboardHiker'
    uid = 'keyboard-hiker-1'

    def __init__(self, host=None, port=None, timeout=None):
        super().__init__(**dict(host=host, port=port, timeout=timeout))
        pass


# Socket client
client = SocketClient(host='localhost')


class GUI(tkinter.Tk):
    label = None
    detail = None
    font_family = 'Courier'  # 'Helvetica'

    def __init__(self):
        super().__init__()
        self.geometry('300x400')
        frm = ttk.Frame(self, padding=20)
        frm.pack()
        title = ttk.Label(
            frm, text='Latest key event', font=self.font_family + ' 12 bold')
        title.pack()

        label = ttk.Label(
            frm, text='[...]', font=self.font_family+' 8 bold', justify='center',
            relief=tkinter.GROOVE
        )
        label.pack(pady=20, padx=20)

        var = tkinter.StringVar()
        var.set(dir(tkinter))
        detail = tkinter.Listbox(frm, listvariable=var, selectmode='browse')
        detail.pack()

        self.label = label
        self.detail = detail
        logger.debug('Initialized')


class KeyboardHiker(object):
    # Flags
    verbose: bool = False
    suppress: bool = False
    no_gui: bool = False

    # Variables
    arguments = None
    escape_key_name: str = None
    gui: GUI = None
    count: int = 0

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
            logger.debug(f'Set {k} as {v}')
        logger.info('Initialized')

    def wait_until_escape(self):
        # Setup the escape key name.
        escape_key_name = self.escape_key_name
        logger.info(f'Waiting for escape key: {escape_key_name}')
        if not escape_key_name:
            logger.warning('No escape key is provided.')

        # Wait until the escape key is pressed,
        # the block is executed by keyboard.wait method
        if self.no_gui:
            keyboard.wait(escape_key_name, suppress=self.suppress)

        # the block is executed by gui.mainloop method
        else:
            self.gui = GUI()
            if escape_key_name:
                keyboard.on_press_key(
                    escape_key_name, lambda x: self.gui.destroy(), suppress=self.suppress)

            # Make the content of the list box
            lst = [f'{e[0]}: {e[1]}' for e in self.arguments._get_kwargs()]
            if self.suppress and self.escape_key_name is not None:
                lst.append(
                    'Warning: escape key will be ignored since it is suppressed.')

            # Make the string var
            var = tkinter.StringVar()
            var.set(lst)

            # Update the detail listbox
            self.gui.detail.config(listvariable=var)

            # Run the mainloop
            self.gui.mainloop()

        logger.info(f'Escape key pressed: {escape_key_name}')
        return 0

    def bind_on_press(self):
        keyboard.on_press(self.callback, suppress=self.suppress)
        logger.debug(f'Bound with onPress event, suppress={self.suppress}')

    def callback(self, event):
        self.count += 1

        if self.verbose:
            inspect(event)

        if self.gui:
            self.gui.label.config(
                text=f'{event}\n{event.time}\nCount: {self.count}')

        logger.debug(f'Got key press: {event}, {event.time}')


# %% ---- 2024-11-15 ------------------------
# Play ground
if __name__ == "__main__":
    # Arguments
    parser = argparse.ArgumentParser(description='Keyboard hiker application')
    parser.add_argument('-e', '--escape-key-name',
                        help='Escape from the app if the given key is pressed')
    parser.add_argument('-v', '--verbose',
                        help='Verbose key press', action='store_true')
    parser.add_argument('-s', '--suppress',
                        help='Suppress the key press', action='store_true')
    parser.add_argument('-n', '--no-gui',
                        help='Not using the GUI', action='store_true')
    arguments = parser.parse_args()
    print(arguments)

    # Keyboard hiker
    kwargs = dict(
        namespace=arguments,
        suppress=arguments.suppress,
        verbose=arguments.verbose,
        no_gui=arguments.no_gui,
        escape_key_name=arguments.escape_key_name,
    )
    kr = KeyboardHiker(**kwargs)
    kr.bind_on_press()
    sys.exit(kr.wait_until_escape())


# %% ---- 2024-11-15 ------------------------
# Pending


# %% ---- 2024-11-15 ------------------------
# Pending
