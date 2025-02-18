import cv2
import time
import json
import pickle
import pyaudio
import numpy as np

from threading import Thread
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

from sync.routine_center.client_base import BaseClientSocket
from eeg_device_reader_ssvep_simulation import EEGDeviceReader, convert_data_into_array

# Init the plt with bmh
plt.style.use('bmh')

# Init and start the eeg device reader.
eeg_device_reader = EEGDeviceReader()
eeg_device_reader.start()
channels = eeg_device_reader.channels


class Decoder(object):
    # Load pretrained decoding model.
    svm = pickle.load(open('svm.dump', 'rb'))

    # Setup lookup table.
    # It should aligned with pretrained svm.
    freqs = np.arange(8, 16, 0.3)

    def predict(self, data):
        # Data shape is (n_time_points, n_channels).
        # Convert into (1, 4001) features.
        features = data[:4001, 0][np.newaxis, :]
        predicted_labels = self.svm.predict(features)
        return [self.freqs[e] for e in predicted_labels]


decoder = Decoder()


class SocketClient(BaseClientSocket):
    path = '/eeg/monitor'
    uid = 'eeg-device-monitor-1'
    use_ssvep_simulation_reader = True

    def __init__(self, host=None, port=None, timeout=None):
        super().__init__(**dict(host=host, port=port, timeout=timeout))

    def handle_message(self, message):
        super().handle_message(message)
        # Recover the letter.
        letter = json.loads(message)

        # Deal with content
        content = json.loads(letter['content'])
        action = content.get('action')
        cue = content.get('cue')
        cueOmega = content.get('cueOmega')

        # Only response with the SSVEP trial starts. action.
        if action == 'SSVEP trial starts.':
            # I am processing the letter.
            self.mm.bag_pending.insert_letter(letter)
            onstart_time = letter['_timestamp']

            # If using simulation device, insert the chunk for SSVEP simulation
            if self.use_ssvep_simulation_reader and cueOmega is not None:
                eeg_device_reader.fill_ssvep_chunk_data(cueOmega)

            # Wait a while for decoding
            Thread(target=self.wait_for_data,
                   args=(onstart_time, cueOmega, letter), daemon=True).start()

        # Mark the letter as failure.
        else:
            letter.update({'_fail_reason': 'Unknown action'})
            self.mm.bag_failed.insert(letter)

        return

    def wait_for_data(self, onstart_time, cueOmega, letter):
        try:
            # Decoding setup.
            data_length_required = 4  # seconds
            package_interval = eeg_device_reader.package_interval
            time_resolution = eeg_device_reader.time_resolution

            # Get data after required length seconds.
            time.sleep(data_length_required)
            while True:
                data = eeg_device_reader.peek_latest_data_by_seconds(
                    data_length_required)

                # Break if already got enough data.
                # If failed, sleep until the next package arrival.
                t = data[-1][1]
                if t > onstart_time + data_length_required + package_interval:
                    break
                else:
                    time.sleep(package_interval)

            # Deal with the data
            data, times = convert_data_into_array(
                data, package_interval, time_resolution)

            data = data[times >= onstart_time]
            times = times[times >= onstart_time]

            pred_freq = decoder.predict(data)
            pred_freq = float(pred_freq[0])

            print(pred_freq, cueOmega)

            # Send back the decoding result.
            letter['dst'] = letter['src']
            letter['src'] = self.path_uid
            content = json.loads(letter['content'])

            # ! I am pretending process the decoding.
            # Here, I am just adding a random omega for demonstration if the cueOmega is not given.
            # In real-world scenario, you should replace this with your decoding process.
            content.update({'decodedOmega': np.random.uniform(5, 30)})
            if omega := content.get('cueOmega'):
                content.update({'decodedOmega': omega})
            else:
                available_omega = np.linspace(5, 30, 26)
                np.random.shuffle(available_omega)
                content.update({'decodedOmega': available_omega[0]})
            letter['content'] = json.dumps(content)

            self.send_message(json.dumps(letter))

            # Mark the letter as finished.
            if lt := self.mm.bag_pending.fetch_letter(letter['uid']):
                self.mm.bag_finished.insert_letter(lt)
                self.mm.bag_finished.insert_letter(letter)
        except Exception as err:
            if lt := self.mm.bag_pending.fetch_letter(letter['uid']):
                lt.update({'_fail_reason': f'{type(err)}({err})'})
                self.mm.bag_failed.insert_letter(lt)
        return


client = SocketClient()
client.connect()


class AudioStream:
    SAMPLESIZE = 4096  # number of data points to read at a time
    SAMPLERATE = 44100  # time resolution of the recording device (Hz)

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_available = False
        self.init_audio()

    def init_audio(self):
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLERATE,
                input=True,  # use default input device to open audio stream
                frames_per_buffer=self.SAMPLESIZE)

            self.audio_available = True
            print(self.stream)
            print(np.frombuffer(self.stream.read(self.SAMPLESIZE), dtype=np.int16))
        except Exception as e:
            print(f"Audio device error: {e}")
            self.audio_available = False

    def read_audio(self):
        if self.audio_available:
            try:
                return np.frombuffer(self.stream.read(self.SAMPLESIZE), dtype=np.int16)
            except Exception as e:
                print(f"Audio read error: {e}")
                return
        return

    def close(self):
        if self.audio_available:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()


class CameraStream:
    def __init__(self):
        self.camera_available = False
        self.init_thread = Thread(target=self.init_camera)
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


class FPSCounter:
    def __init__(self):
        self.start_time = time.time()
        self.frame_count = 0

    def update(self):
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        fps = self.frame_count / elapsed_time
        return fps


if __name__ == "__main__":
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
    ax2.set_xlim(0, audio_stream.SAMPLESIZE-1)
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
    ax_large.set_ylim(-1, channels+1)

    channel_lines = [ax_large.plot([], [], lw=1) for _ in range(channels)]
    # line2, = ax_large.plot([], [], lw=1)

    # x axis data points
    x = np.linspace(0, audio_stream.SAMPLESIZE-1, audio_stream.SAMPLESIZE)

    # Initialize FPS counter
    fps_counter = FPSCounter()

    def init():
        line.set_data([], [])
        return line,

    def animate(i_frame):
        e = eeg_device_reader.peek_latest_data_by_length(50)
        first = e[0]
        last = e[-1]

        if i_frame % 200 == 0:
            client.send_message(f'Info. Display {i_frame} frame.')
            print(
                first[0], last[0], first[1], last[1],
                last[1]-first[1], first[2].shape, len(e))

        y2 = np.concatenate([d[2] for d in e], axis=1)
        x2 = np.linspace(0, 1, y2.shape[1])
        for i in range(channels):
            channel_lines[i][0].set_data(x2, y2[i]+i)
        ax_large.set_xlim((x2[0], x2[-1]))

        # Update audio plot
        y = audio_stream.read_audio()
        if y is not None:
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
                        frames=200, interval=20, blit=False)

    # def check_plot_closed():
    #     if not plt.fignum_exists(fig.number):
    #         # stop and close the audio and camera streams
    #         audio_stream.close()
    #         camera_stream.close()
    #         eeg_device_reader.stop()
    #         client.close()
    #         return
    #     mm.root.after(100, check_plot_closed)

    # mm.root.after(100, check_plot_closed)
    plt.show(block=True)
    print('--')

    audio_stream.close()
    camera_stream.close()
    eeg_device_reader.stop()
    client.close()
