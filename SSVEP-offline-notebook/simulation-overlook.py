"""
File: simulation overlook.py
Author: Chuncheng Zhang
Date: 2025-01-09
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    What does simulation look like? And simulation for the EEG signal.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2025-01-09 ------------------------
# Requirements and constants

import seaborn as sns
import streamlit as st
from scipy.stats import multivariate_normal
import matplotlib.pyplot as plt
import numpy as np


# Set seaborn style
sns.set(style="whitegrid")

# %% ---- 2025-01-09 ------------------------
# Function and class


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

# %% ---- 2025-01-09 ------------------------
# Play ground


if __name__ == '__main__':
    # Check if the script is being run directly
    fs_eeg = 250  # Hz
    fs_sti = 100  # Hz

    # Streamlit application
    st.title("Simulation Overlook")

    st.sidebar.header("Input Parameters")

    # Group 1: Other parameters
    st.sidebar.subheader("Group 1: Simulation Parameters")
    freq = st.sidebar.slider("Simulation Frequency (Hz)",
                             min_value=1, max_value=50, value=5)
    length = st.sidebar.slider(
        "Simulation Length (s)", min_value=1, max_value=10, value=1)

    # Group 2: Sampling frequency options
    st.sidebar.subheader("Group 2: Sampling Frequencies")
    fs_eeg = st.sidebar.slider(
        "EEG Sampling Frequency (Hz)", min_value=100, max_value=1000, value=fs_eeg)
    fs_sti = st.sidebar.slider(
        "Stimulus Sampling Frequency (Hz)", min_value=50, max_value=500, value=fs_sti)

    time_series, times = generate_simulation(freq, length, fs_sti)
    eeg_response, eeg_times, trf_kernel, trf_kernel_times = generate_eeg_response(
        time_series, times, fs_eeg)

    # Crop the time to (0, max-trf length)
    max_time = times[-1] - trf_kernel_times[-1]
    valid_indices = times <= max_time
    time_series = time_series[valid_indices]
    times = times[valid_indices]
    valid_indices = eeg_times <= max_time
    eeg_response = eeg_response[valid_indices]
    eeg_times = eeg_times[valid_indices]

    # 1. The simulation time_series and EEG signal in one graph.
    st.subheader("Simulation and EEG Signal")
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()
    sns.lineplot(x=times, y=time_series,
                 label='Simulation Signal', color='blue', ax=ax1)
    sns.lineplot(x=eeg_times, y=eeg_response,
                 label='EEG Signal', color='red', ax=ax2)
    ax1.set_title("Simulation and EEG Signal")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Simulation Signal Amplitude", color='blue')
    ax2.set_ylabel("EEG Signal Amplitude", color='red')
    ax2.grid(False)  # Disable grid for the right y-axis
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    st.pyplot(fig)

    # 2. The spectrum of the EEG signal.
    st.subheader("EEG Signal Spectrum")
    fig3, ax3 = plt.subplots(figsize=(10, 4))
    freqs = np.fft.rfftfreq(len(eeg_response), 1/fs_eeg)
    spectrum = 20 * np.log10(np.abs(np.fft.rfft(eeg_response)))
    sns.lineplot(x=freqs, y=spectrum, color='red', ax=ax3)
    ax3.set_title("EEG Signal Spectrum")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Amplitude (dB)")
    st.pyplot(fig3)

    # 3. The TRF kernel waveform.
    st.subheader("TRF Kernel Waveform")
    fig4, ax4 = plt.subplots(figsize=(10, 4))
    sns.lineplot(x=trf_kernel_times, y=trf_kernel, color='purple', ax=ax4)
    ax4.set_title("TRF Kernel Waveform")
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Amplitude")
    st.pyplot(fig4)

# %% ---- 2025-01-09 ------------------------
# Pending


# %% ---- 2025-01-09 ------------------------
# Pending
