
"""
File: eeg_device_reader_ssvep_simulation.py
Author: Chuncheng Zhang
Date: 2025-1-9
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Stimulus the EEG device reader for SSVEP simulation.

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
import contextlib
import numpy as np

from omegaconf import OmegaConf
from threading import Thread, RLock
from loguru import logger as LOGGER
from scipy.stats import multivariate_normal

# %% ---- 2023-07-24 ------------------------
# Function and class
eeg_config = dict(
    channels=10,  # number of channels
    sample_rate=1000,  # Hz
    package_length=100,  # number of time points per package
    packages_limit=5000,  # number of packages
)

CONF = OmegaConf.create(dict(eeg=eeg_config))


def generate_trf(fs_eeg):
    tmin, tmax = -0.1, 0.4
    delays_samp = np.arange(np.round(tmin * fs_eeg),
                            np.round(tmax * fs_eeg) + 1).astype(int)
    delays_sec = delays_samp / fs_eeg
    grid = np.array(np.meshgrid(delays_sec, 1))
    grid = grid.swapaxes(0, -1).swapaxes(0, 1)

    means_high = [0.1, 1]
    means_low = [0.13, 1]
    means_high2 = [0.2, 1]
    means_low2 = [0.23, 1]
    means_high3 = [0.3, 1]
    means_low3 = [0.33, 1]
    cov = [[0.0002, 0], [0, 500]]  # 5000
    cov2 = [[0.0004, 0], [0, 50000]]  # 5000
    cov3 = [[0.0006, 0], [0, 100000]]  # 5000
    gauss_high = multivariate_normal.pdf(grid, means_high, cov)
    gauss_low = -1 * multivariate_normal.pdf(grid, means_low, cov)
    gauss_high2 = multivariate_normal.pdf(grid, means_high2, cov2)
    gauss_low2 = -1 * multivariate_normal.pdf(grid, means_low2, cov2)
    gauss_high3 = multivariate_normal.pdf(grid, means_high3, cov3)
    gauss_low3 = -1 * multivariate_normal.pdf(grid, means_low3, cov3)
    weights = gauss_high + gauss_low + gauss_high2 + gauss_low2 + \
        gauss_high3 + gauss_low3  # Combine to create the "true" STRF

    # Crop the trf_kernel and trf_kernel_times with trf_kernel_times > 0
    valid_indices = delays_sec >= 0
    weights = weights[valid_indices]
    delays_sec = delays_sec[valid_indices]

    # Normalize the TRF energy to 1
    weights /= np.linalg.norm(weights)

    return weights, delays_sec


def generate_simulation(freq, length, fs_sti):
    '''
    freq: The freq of flipping in sin waveform.
    frame_rate: The frame rate of display.
    length: The total length of simulation in seconds.
    '''
    times = np.arange(0, length, 1/fs_sti)
    time_series = np.sin(2 * np.pi * freq * times)
    return time_series, times


def align_simulation_with_eeg_fs(time_series, times, fs_eeg):
    aligned_times = np.arange(0, times[-1], 1/fs_eeg)
    aligned_time_series = np.interp(aligned_times, times, time_series)
    return aligned_time_series, aligned_times


def generate_eeg_response(time_series, times, fs_eeg):
    aligned_time_series, aligned_times = align_simulation_with_eeg_fs(
        time_series, times, fs_eeg)
    trf_kernel, trf_kernel_times = generate_trf(fs_eeg)

    # Convolve aligned_time_series with weights
    eeg_response = np.convolve(aligned_time_series, trf_kernel, mode='same')
    # Align the response to the head
    eeg_response = eeg_response[:len(aligned_times)]
    eeg_times = aligned_times

    return eeg_response, eeg_times, trf_kernel, trf_kernel_times


def add_noise(array):
    return array + np.random.normal(0, 0.01, array.shape)


def mk_eeg_response(freq):
    '''
    Make the eeg response for the given $freq.

    Args:
        - freq (float): The stimuli frequency.

    Returns:
        - sliced_data: The eeg response, shape is (n_time_points, n_channels).
    '''
    # The display fps.
    fs_sti = 100
    # Generate $length seconds data in total.
    length = 5
    # Crop the time to (0, 4) seconds.
    max_time = 4
    # How many channels of the EEG device.
    channels = CONF['eeg']['channels']
    # The EEG recording frequency.
    fs_eeg = CONF['eeg']['sample_rate']

    # Generate the display time series.
    time_series, times = generate_simulation(freq, length, fs_sti)
    # Generate the EEG data, the length is as the same as the $time_series.
    eeg_response, eeg_times, trf_kernel, trf_kernel_times = generate_eeg_response(
        time_series, times, fs_eeg)

    # Crop into $max_time seconds.
    valid_indices = times <= max_time
    time_series = time_series[valid_indices]
    times = times[valid_indices]
    valid_indices = eeg_times <= max_time
    eeg_response = eeg_response[valid_indices]
    eeg_times = eeg_times[valid_indices]

    # Shape is [n_channels, n_times]
    eeg_data = np.array([add_noise(eeg_response) for _ in range(channels)])

    # Slice the output into array.
    # n_times length array for (n_channels, ) np.array
    sliced_data = [e.squeeze() for e in eeg_data.T]

    return sliced_data


def uint8(x):
    """Convert x into uint8

    Args:
        x (np.array): The array to convert.

    Returns:
        np.uint8 array: The converted array.
    """
    return x.astype(np.uint8)


def interpolate_nan(array_like):
    '''Fill the nan in array_like, using linear interpolation method.'''
    array = array_like.copy()
    nans = np.isnan(array)
    array[nans] = np.interp(
        np.flatnonzero(nans), np.flatnonzero(~nans), array[~nans])
    return array


def convert_data_into_array(input_data: list, package_interval: float, time_resolution: float):
    '''
    Convert the data into well timed array.
    The data is from EEGDeviceReader.peek_latest_data_by_length method.

    Args:
        - input_data: The data to convert, it is the package from EEGDeviceReader.peek_latest_data_by_length.
        - package_interval: The package length. Ideally, the package_interval is the package length.
        - time_resolution: The time resolution of the package's time points.

    Returns:
        - data: The data being converted, the shape is (n_channels, n_data_slices).
        - times: The times for the data slices.
    '''

    # How many data packages.
    n = len(input_data)
    # Compute the $corrected_last_time, it is assumed to be the time of the data's last time point.
    # ! I need the $ts is always larger than $y1, so the nearest point refers the least delayed data point being transferred.
    y1 = np.array(range(n)) * package_interval
    ts = np.array([e[1] for e in input_data])
    d = np.min(ts-y1)
    corrected_last_time = (y1 + d)[-1]

    # Concatenate the data and assign the time points.
    data = np.array(np.concat([e[2].T for e in input_data], axis=0))
    m = len(data)
    times = np.array([corrected_last_time-j*time_resolution for j in range(m)])

    return data, times

    def _mix_time_with_nan(t, n):
        '''
        The output is time series with two ends are marked with times,
        others are nans.
        The package length is package_length.

        |t-package_length ------------------- t|
        |<---------- package_length ---------->|

        Args:
            - t is the package arriving time.
            - n is the length of the package.
        '''
        d = np.zeros(n, )
        d.fill(np.nan)
        d[-1] = t
        d[0] = t - package_interval + time_resolution
        return d

    # The data shape is (n_time_points, n_channels)
    data = np.concatenate([d.T for i, t, d in input_data])
    times = np.concatenate([_mix_time_with_nan(t, d.shape[1])
                           for i, t, d in input_data])

    # Linear interpolate the times array
    times = interpolate_nan(times)

    return data, times


class EEGDeviceReader(object):
    '''
    Request data package from EEG device,
    the package is the shape of (channels x package_length).

    The sample_rate refers the sampling rate of the device.
    '''
    channels = 10  # number of channels
    sample_rate = 1000  # Hz
    package_length = 40  # number of time points per package
    packages_limit = 5000  # number of packages
    package_interval = package_length / sample_rate  # Interval between packages
    # The time resolution of the time points.
    time_resolution = 1 / sample_rate

    rlock = RLock()
    ssvep_chunk_data = []

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

    def start(self):
        if not self.running:
            self.run_forever()
        else:
            LOGGER.error('Can not start, since it is already running')

    def stop(self):
        self.running = False

    @contextlib.contextmanager
    def lock(self):
        self.rlock.acquire()
        try:
            yield
        finally:
            self.rlock.release()

    def fill_ssvep_chunk_data(self, freq):
        d = mk_eeg_response(freq)
        with self.lock():
            self.ssvep_chunk_data = d
        LOGGER.debug(
            f'Make pseudo ssvep chunk data: {len(self.ssvep_chunk_data)}, {self.ssvep_chunk_data[0].shape}')

    def _read_data(self):
        """Simulate the EEG device reading,
        it is called by the self.run_forever() method.
        """

        self.data_buffer = []
        self._read_data_idx = 0

        LOGGER.debug('Read data loop starts.')
        while self.running:
            # Record the loop start time.
            t = time.time()

            # Simulation the incoming signal.
            # The shape is (n_channels, n_time_points).
            incoming = np.zeros((self.channels, self.package_length)) + t
            for j in range(self.package_length):
                incoming[:, j] += j / self.sample_rate
                incoming[:, j] %= 1

            # Use the ssvep_chunk_data if it is available.
            # It overwrites the incoming variable.
            with self.lock():
                for j in range(self.package_length):
                    if len(self.ssvep_chunk_data) > 0:
                        incoming[:, j] = self.ssvep_chunk_data.pop()

            # Push the processed incoming data.
            # ! The format of the data_buffer's element is (i, t, d)
            # ! The shape of d is (n_channels, n_time_points).
            self.data_buffer.append((self._read_data_idx, t, incoming))
            self._read_data_idx += 1

            # Prevent the buffer size from being too large.
            if self.get_data_buffer_size() > self.packages_limit:
                LOGGER.warning(
                    'Data buffer exceeds {} packages.'.format(self.packages_limit))
                self.data_buffer.pop(0)

            # How long is passed since the loop starts.
            delay = time.time() - t

            # Make sure the next loop starts after $self.package_interval seconds.
            time.sleep(max(0.001, self.package_interval - delay))

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
        """Peek the latest data in the self.data_buffer with given length in packages.

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

    def peek_latest_data_by_seconds(self, seconds: float):
        """Peek the latest data in the $self.data_buffer with given length in seconds."""
        # Compute how many packages are required, and peek one more package for safety.
        length = int(seconds / self.package_interval) + 1
        return self.peek_latest_data_by_length(length)

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
