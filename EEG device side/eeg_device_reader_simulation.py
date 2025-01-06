"""
File: eeg_device_reader_simulation.py
Author: Chuncheng Zhang
Date: 2023-07-24
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


# %% ---- 2023-07-24 ------------------------
# Requirements and constants
import time

import numpy as np
import matplotlib.pyplot as plt

from threading import Thread
from datetime import datetime

from omegaconf import OmegaConf
from loguru import logger as LOGGER

# %%

# %% ---- 2023-07-24 ------------------------
# Function and class
eeg_config = dict(
    channels=65,  # number of channels
    sample_rate=1000,  # Hz
    package_length=100,  # number of time points per package
    packages_limit=5000,  # number of packages
    display_window_length=5,  # seconds
    display_inch_width=4,  # inch
    display_inch_height=8,  # inch
    display_dpi=100,  # DPI
    host='192.168.1.103',
    port=4455,
    not_exist='Not exist option',
)

CONF = OmegaConf.create(dict(eeg=eeg_config))


def uint8(x):
    """Convert x into uint8

    Args:
        x (np.array): The array to convert.

    Returns:
        np.uint8 array: The converted array.
    """
    return x.astype(np.uint8)


class EEGDeviceReader(object):
    '''
    Request data package from EEG device,
    the package is the shape of (channels x package_length).

    The sample_rate refers the sampling rate of the device.
    '''
    channels = 64  # number of channels
    sample_rate = 1000  # Hz
    package_length = 40  # number of time points per package
    packages_limit = 5000  # number of packages
    display_window_length = 2  # seconds
    display_inch_width = 4  # inch
    display_inch_height = 3  # inch
    display_dpi = 100  # DPI
    package_interval = package_length / sample_rate  # Interval between packages

    def __init__(self):
        self.conf_override()
        self.running = False

        LOGGER.debug(
            'Initialize {} with {}'.format(self.__class__, self.__dict__))
        pass

    def conf_override(self):
        for key, value in CONF['eeg'].items():
            if not (hasattr(self, key)):
                LOGGER.warning('Invalid key: {} in CONF'.format(key))
                continue
            setattr(self, key, value)

        self.package_interval = self.package_length / \
            self.sample_rate  # Interval between packages

        LOGGER.debug('Override the options with CONF')

    def placeholder_image(self):
        return uint8(np.zeros((self.display_inch_height*self.display_dpi,
                               self.display_inch_width*self.display_dpi,
                               3)))

    def start(self):
        if not self.running:
            self.run_forever()
        else:
            LOGGER.error('Can not start, since it is already running')

    def stop(self):
        self.running = False

    def _read_data(self):
        """Simulate the EEG device reading,
        it is called by the self.run_forever() method.
        """

        self.data_buffer = []
        self._read_data_idx = 0

        LOGGER.debug('Read data loop starts.')
        while self.running:
            t = time.time()
            incoming = np.zeros((self.channels, self.package_length)) + t

            for j in range(self.package_length):
                incoming[:, j] += j / self.sample_rate
                incoming[:, j] %= 1

            self.data_buffer.append((self._read_data_idx, t, incoming))
            self._read_data_idx += 1

            if self.get_data_buffer_size() > self.packages_limit:
                LOGGER.warning(
                    'Data buffer exceeds {} packages.'.format(self.packages_limit))
                self.data_buffer.pop(0)

            time.sleep(self.package_interval)

        LOGGER.debug('Read data loop stops.')

    def add_offset(self, data):
        """Add offset to the channels of the array for display purposes
        The operation is in-place.

        Args:
            data (2d array): The data of EEG data, the shape is (channels x times)

        Returns:
            2d array: The data with offset
        """
        for j, d in enumerate(data):
            d += j
        return data

    def get_data_buffer_size(self):
        """Get the current buffer size for the data_buffer

        Returns:
            int: The buffer size.
        """
        return len(self.data_buffer)

    def peek_latest_data_by_length(self, length=50):
        """Peek the latest data in the self.data_buffer with given length.

        If there is no data available, return None.

        Args:
            length (int, optional): How many packages are required, the length in seconds are length x self.package_interval. Defaults to 50.

        Returns:
            list: The data being fetched. The elements of the list are (idx, timestamp, data of (self.channels x self.package_length)).
            None if there is no data available.
        """
        if self.get_data_buffer_size() < 1:
            return None

        output = [e for e in self.data_buffer[-length:]]

        return output

    def run_forever(self):
        """Run the loops forever.
        """
        self.running = True
        Thread(target=self._read_data, daemon=True).start()
        pass


# %% ---- 2023-07-24 ------------------------
# Play ground


# %% ---- 2023-07-24 ------------------------
# Pending


# %% ---- 2023-07-24 ------------------------
# Pending
