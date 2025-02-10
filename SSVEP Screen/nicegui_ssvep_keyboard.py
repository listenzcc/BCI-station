"""
File: nicegui_ssvep_keyboard.py
Author: Chuncheng Zhang
Date: 2025-02-10
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    The NiceGUI for SSVEP keyboard.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2025-02-10 ------------------------
# Requirements and constants
import json
import socket
from nicegui import ui
from omegaconf import OmegaConf

# Socket connection details
CONFIG = OmegaConf.load('config.yaml')


# %% ---- 2025-02-10 ------------------------
# Function and class
def send_command(command):
    host = CONFIG.SSVEPScreen.host  # 'localhost'
    port = CONFIG.SSVEPScreen.port  # 36501
    encoding = CONFIG.SSVEPScreen.encoding  # 'utf-8'
    '''Send a command to the SSVEP keyboard socket server and return the response.'''
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(len(command).to_bytes(
            4, byteorder='big') + command.encode(encoding))
        raw_msglen = s.recv(4)
        if not raw_msglen:
            return None
        msglen = int.from_bytes(raw_msglen, byteorder='big')
        response = s.recv(msglen)
        return response.decode(encoding)


def set_num_columns(num_columns):
    '''Set the number of columns on the SSVEP keyboard.'''
    command = json.dumps(
        {'action': 'set_num_columns', 'num_columns': num_columns})
    response = send_command(command)
    ui.notify(f'Set num_columns response: {response}')


def get_input_buffer():
    '''Get the input buffer from the SSVEP keyboard.'''
    command = json.dumps({'action': 'get_input_buffer'})
    response = send_command(command)
    ui.notify(f'Input buffer: {response}')


def append_cue_sequence(cues):
    '''Append a cue sequence to the SSVEP keyboard.'''
    command = json.dumps({'action': 'append_cue_sequence', 'cues': cues})
    response = send_command(command)
    ui.notify(f'Append cue sequence response: {response}')


# %% ---- 2025-02-10 ------------------------
# Play ground
# NiceGUI UI

with ui.card():
    ui.label('SSVEP Keyboard Control Panel')

    ui.number(label='Number of Columns', value=6, min=3, max=10,
              on_change=lambda e: set_num_columns(e.value))

    cue_input = ui.input(label='Cue Sequence')
    ui.button('Append Cue Sequence',
              on_click=lambda: append_cue_sequence(cue_input.value))


class DetailCard:
    card = ui.card()
    with card:
        input_buffer_label = ui.label('Input Buffer: ')
        cue_sequence_label = ui.label('Cue Sequence: ')
        current_cue_label = ui.label('Current Cue: ')
        ui.separator()
        current_layout_label = ui.label(
            'Current Layout: ').style('white-space: pre-wrap;')

    def update_status(self):
        # Update the input buffer segment.
        command = json.dumps({'action': 'get_input_buffer'})
        response = json.loads(send_command(command))
        self.input_buffer_label.set_text(f'Input Buffer: {response}')

        # Update the current_cue segment.
        command = json.dumps({'action': 'get_current_cue'})
        response = json.loads(send_command(command))
        self.current_cue_label.set_text(f'Current Cue: {response}')

        # Update the cue sequence segment.
        command = json.dumps({'action': 'get_cue_sequence'})
        response = json.loads(send_command(command))
        self.cue_sequence_label.set_text(f'Cue Sequence: {response}')

        # Update the current layout segment, it is a list, so make the lines.
        command = json.dumps({'action': 'get_current_layout'})
        response = send_command(command)
        layout_list = json.loads(response).get('current_layout', [])
        layout_text = '\n'.join([str(item) for item in layout_list])
        self.current_layout_label.set_text(f'Current Layout:\n{layout_text}')


dc = DetailCard()


ui.timer(interval=1.0, callback=dc.update_status)

ui.run(port=CONFIG.NiceGUI.port)


# %% ---- 2025-02-10 ------------------------
# Pending


# %% ---- 2025-02-10 ------------------------
# Pending
