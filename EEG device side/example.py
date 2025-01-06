import os
import sys
import pyaudio
import numpy as np
import cv2
import threading
import time
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from eeg_device_reader_simulation import EEGDeviceReader

from sync.control_center.client_base import SocketClientBase


plt.style.use('bmh')

# client = SocketClientBase('192.168.137.1')
client = SocketClientBase()
client.connect()

SAMPLESIZE = 4096  # number of data points to read at a time
SAMPLERATE = 44100  # time resolution of the recording device (Hz)

eeg_device_reader = EEGDeviceReader()
eeg_device_reader.start()


class AudioStream:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_available = False
        self.init_audio()

    def init_audio(self):
        try:
            self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLERATE, input=True,
                                      frames_per_buffer=SAMPLESIZE)  # use default input device to open audio stream
            self.audio_available = True
            print(self.stream)
            print(np.frombuffer(self.stream.read(SAMPLESIZE), dtype=np.int16))
        except Exception as e:
            print(f"Audio device error: {e}")
            self.audio_available = False

    def read_audio(self):
        if self.audio_available:
            try:
                return np.frombuffer(self.stream.read(SAMPLESIZE), dtype=np.int16)
            except Exception as e:
                print(f"Audio read error: {e}")
                return np.zeros(SAMPLESIZE)
        return np.zeros(SAMPLESIZE)

    def close(self):
        if self.audio_available:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()


class CameraStream:
    def __init__(self):
        self.camera_available = False
        self.init_thread = threading.Thread(target=self.init_camera)
        self.init_thread.start()

    def init_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Camera device not available")
            self.camera_available = False
        else:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # Reduce resolution
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            self.camera_available = True

    def read_frame(self):
        if self.camera_available:
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def close(self):
        if self.camera_available:
            self.cap.release()


# Initialize audio and camera streams
audio_stream = AudioStream()
camera_stream = CameraStream()

# set up plotting
fig, axs = plt.subplots(2, 2,
                        gridspec_kw={
                            'height_ratios': [2, 1],
                            'width_ratios': [2, 1]},
                        figsize=(10, 10))
(ax1, ax2), (ax3, ax4) = axs
ax2.set_xlim(0, SAMPLESIZE-1)
ax2.set_ylim(-9999, 9999)
line, = ax2.plot([], [], lw=1)

# Assign titles to the axes
ax2.set_title('Audio Signal')
ax4.set_title('Camera Feed')

# Combine ax1 and ax3 into a larger graph
ax1.remove()
ax3.remove()
ax_large = fig.add_subplot(2, 2, (1, 3))
ax_large.set_title('Larger Graph')
ax_large.set_ylim(-1, 66)

channels = 65
channel_lines = [ax_large.plot([], [], lw=1) for _ in range(channels)]
# line2, = ax_large.plot([], [], lw=1)

# x axis data points
x = np.linspace(0, SAMPLESIZE-1, SAMPLESIZE)


class FPSCounter:
    def __init__(self):
        self.start_time = time.time()
        self.frame_count = 0

    def update(self):
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        fps = self.frame_count / elapsed_time
        return fps


# Initialize FPS counter
fps_counter = FPSCounter()


def init():
    line.set_data([], [])
    return line,


def animate(i_frame):
    client.send_message(f'Info. Display {i_frame} frame.')

    e = eeg_device_reader.peek_latest_data_by_length(50)
    first = e[0]
    last = e[-1]
    print(first[0], last[0], first[1], last[1],
          last[1]-first[1], first[2].shape, len(e))

    y2 = np.concatenate([d[2] for d in e], axis=1)
    x2 = np.linspace(0, 1, y2.shape[1])
    for i in range(65):
        channel_lines[i][0].set_data(x2, y2[i]+i)
    ax_large.set_xlim((x2[0], x2[-1]))

    # Update audio plot
    y = audio_stream.read_audio()
    line.set_data(x, y)

    # Update camera feed
    frame = camera_stream.read_frame()
    if frame is not None:
        ax4.clear()
        ax4.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ax4.axis('off')  # Hide axes for the camera feed
        ax4.set_aspect('auto')  # Set aspect ratio to auto

    # Calculate and update FPS in title
    fps = fps_counter.update()
    fig.suptitle(f'FPS: {fps:.2f}')

    return line,


ani = FuncAnimation(fig, animate, init_func=init,
                    frames=20, interval=20, blit=False)

plt.show()
print('--')

# stop and close the audio and camera streams
audio_stream.close()
camera_stream.close()
eeg_device_reader.stop()
client.close()
