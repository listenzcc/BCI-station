"""
File: timer.py
Author: Chuncheng Zhang
Date: 2024-08-07
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Amazing things

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2024-08-07 ------------------------
# Requirements and constants
import time
from loguru import logger


# %% ---- 2024-08-07 ------------------------
# Function and class
class RunningTimer(object):
    tic = time.time()
    frames = 0  # How many frames
    passed = 0  # seconds since reset
    auto_report_step = 5  # seconds between each auto report
    auto_report_passed = 0  # seconds on the next auto report
    running = False  # whether the timer is running
    name = 'zccTimer'

    def __init__(self, name=None):
        if name:
            self.name = name
        pass

    def step(self):
        '''
        Update the timer to the next frame.

        Returns:
            - frames: How many frames are passed.
            - frame_rate: The frame rate of all the frames.
        '''
        self.frames += 1
        passed = self.get()
        frame_rate = self.frames / passed if passed > 0 else 0

        if passed > self.auto_report_passed:
            self.auto_report_passed += self.auto_report_step
            logger.debug(
                f'{self.name}: Frame rate: {frame_rate:0.2f}, Passed: {passed:0.2f} seconds')

        return self.frames, frame_rate

    def get(self):
        '''
        Get the passed time in seconds.

        Returns:
            - seconds: The seconds passed.
        '''
        return time.time() - self.tic

    def reset(self):
        '''
        Reset the timer and start the timer *IMMEDIATELY*.
        '''
        self.tic = time.time()
        self.frames = 0  # How many frames
        self.passed = 0  # seconds since reset
        self.auto_report_passed = self.auto_report_step  # seconds on the next auto report
        self.running = True  # whether the timer is running
        logger.info(f'Finished reset')


# %% ---- 2024-08-07 ------------------------
# Play ground


# %% ---- 2024-08-07 ------------------------
# Pending


# %% ---- 2024-08-07 ------------------------
# Pending
