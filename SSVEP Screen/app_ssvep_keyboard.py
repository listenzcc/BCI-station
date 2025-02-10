"""
File: app_ssvep_keyboard.py
Author: Chuncheng Zhang
Date: 2025-02-08
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    The SSVEP keyboard application.

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
from loguru import logger
from PyQt6.QtCore import Qt, QTimer
from ssvep_keyboard import SSVEPScreenPainter, SSVEPScreenPainterWithSocket

# ssp = SSVEPScreenPainter()
ssp = SSVEPScreenPainterWithSocket()

# %% ---- 2025-02-08 ------------------------
# Function and class


def _about_to_quit():
    '''
    Safely quit the demo
    '''
    # Stop the screen painter
    ssp.stop()
    logger.debug('Stopped DisplayEngine')
    return


def _on_key_pressed(event):
    '''
    Handle the key pressed event.

    Args:
        - event: The pressed event.
    '''

    try:
        key = event.key()
        enum = Qt.Key(key)
        logger.debug(f'Key pressed: {key}, {enum.name}')

        # If esc is pressed, quit the app
        if enum.name == 'Key_Escape':
            ssp.qapp.quit()

    except Exception as err:
        logger.error(f'Key pressed but I got an error: {err}')


def start_display():
    '''
    Start the SSVEP display
    '''

    # Show the window
    ssp.show_window()

    # Set the painting method

    def _on_timeout():
        if img := ssp.get_img_safety():
            ssp.repaint(img)

    timer = QTimer()
    timer.timeout.connect(_on_timeout)
    timer.start()

    # Start the display main loop
    ssp.start()
    sys.exit(ssp.qapp.exec())


# %% ---- 2025-02-08 ------------------------
# Play ground
if __name__ == '__main__':
    # Bind the _about_to_quit and _on_key_pressed methods
    ssp.qapp.aboutToQuit.connect(_about_to_quit)
    ssp.window.keyPressEvent = _on_key_pressed
    ssp.start_socket_server()

    start_display()

# %% ---- 2025-02-08 ------------------------
# Pending


# %% ---- 2025-02-08 ------------------------
# Pending
