"""
File: classification-analysis.py
Author: Chuncheng Zhang
Date: 2025-01-09
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Generate stimulus data and make classifier for it.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2025-01-09 ------------------------
# Requirements and constants
import numpy as np

from tqdm.auto import tqdm
from scipy.stats import multivariate_normal

from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report


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


def add_noise(array):
    return array + np.random.normal(0, 0.01, array.shape)



# %% ---- 2025-01-09 ------------------------
# Play ground
if __name__ == '__main__':
    fs_eeg = 1000 # Hz
    fs_sti = 100  # Hz
    channels = 10
    length = 5
    max_time = length - 1

    freqs = np.arange(8, 16, 0.3)

    eeg_data = []
    eeg_data_test = []
    for freq in tqdm(freqs, 'Generating'):
        time_series, times = generate_simulation(freq, length, fs_sti)
        eeg_response, eeg_times, trf_kernel, trf_kernel_times = generate_eeg_response(
            time_series, times, fs_eeg)

        # Crop the time to (0, 4) seconds
        max_time = 4
        valid_indices = times <= max_time
        time_series = time_series[valid_indices]
        times = times[valid_indices]
        valid_indices = eeg_times <= max_time
        eeg_response = eeg_response[valid_indices]
        eeg_times = eeg_times[valid_indices]
        eeg_data.append([add_noise(eeg_response) for _ in range(channels)])
        eeg_data_test.append([add_noise(eeg_response) for _ in range(channels)])
    eeg_data = np.array(eeg_data)
    eeg_data_test = np.array(eeg_data_test)

    # The eeg_data shape is [n_epochs, n_channels, n_times]
    print(eeg_data.shape)

    # 1. Make pickup table for freqs.
    pickup_table = {i: freq for i, freq in enumerate(freqs)}

    # 2. Label eeg_data with freqs idx.
    labels = np.array([i for i in range(len(freqs))])

    # 3. Fit the SVM classifier.
    import pickle
    svm1 = SVC()
    features = eeg_data[:, 0, :].squeeze()
    svm1.fit(features, labels)

    pickle.dump(svm1, open('svm.dump', 'wb'))
    svm = pickle.load(open('svm.dump', 'rb'))

    # 4. Validate the SVM's performance.
    test_features = eeg_data_test[:, 0, :].squeeze()
    predicted_labels = svm.predict(test_features)

    print(predicted_labels)

    # 5. Metric the results.
    accuracy = accuracy_score(labels, predicted_labels)
    report = classification_report(labels, predicted_labels, target_names=[str(f) for f in freqs])

    print(f"Accuracy: {accuracy}")
    print("Classification Report:")
    print(report)

# %% ---- 2025-01-09 ------------------------
# Pending



# %% ---- 2025-01-09 ------------------------
# Pending
