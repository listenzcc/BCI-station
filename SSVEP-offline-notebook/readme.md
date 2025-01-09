# Simulation Overlook

## Overview

This application simulates EEG signals and visualizes the results using Streamlit.

It shows the relationship between screen simulation time series and its possible EEG signal.

The Streamlit app provides an interactive interface to:

- Adjust simulation parameters such as frequency and amplitude.
- Visualize the simulated EEG signals in real-time.
- Analyze the frequency spectrum of the signals.
- Compare different simulation settings side-by-side.

## Requirements

- Python 3.x
- Streamlit
- NumPy
- Matplotlib
- SciPy
- Seaborn

## Installation

1. Install the required Python packages:

    ```sh
    pip install streamlit numpy matplotlib scipy seaborn
    ```

## Running the Application

1. Open a terminal or PowerShell.
2. Navigate to the directory containing the `simulation-overlook.py` file.
3. Run the following command to start the Streamlit application:

    ```sh
    streamlit run simulation-overlook.py
    ```

Alternatively, you can use the provided PowerShell script to start the application:

1. Open a terminal or PowerShell.
2. Navigate to the directory containing the `start_streamlit.ps1` file.
3. Run the following command:

    ```sh
    ./start_streamlit.ps1
    ```

## Usage

1. Open your web browser and go to `http://localhost:8501`.
2. Use the sidebar to adjust the simulation parameters and sampling frequencies.
3. View the simulation results, EEG signal, and their spectrum in the main panel.