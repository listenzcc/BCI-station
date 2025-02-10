"""
File: keyboard_layout.py
Author: Chuncheng Zhang
Date: 2025-02-08
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Dynamically layout as the keyboard.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2025-02-08 ------------------------
# Requirements and constants
import random
from loguru import logger
from collections.abc import Iterable


# %% ---- 2025-02-08 ------------------------
# Function and class
class CueSystem:
    cue_sequence: list = list('指定输入序列')

    def pop_cue_in_fifo(self):
        try:
            cue = self.cue_sequence.pop(0)
        except IndexError:
            cue = None
        return cue

    def push_cue_sequence(self, s: str, idx: int = 0):
        '''
        Push into the cue sequence.

        :param s: the string to push.
        :param idx: the index to push into.

        :return: the updated cue sequence.
        '''

        self.cue_sequence.insert(idx, s)
        logger.debug(f'Pushed cue sequence in {idx}: {self.cue_sequence}')
        return self.cue_sequence

    def extend_cue_sequence(self, lst: Iterable):
        '''
        Extend the cue sequence.

        :param lst: the iterable to extend.

        :return: the updated cue sequence.
        '''
        self.cue_sequence.extend(lst)
        logger.debug(f'Extended cue sequence {self.cue_sequence}')
        return self.cue_sequence

    def clear_cue_sequence(self):
        self.cue_sequence = []
        logger.debug('Cleared cue sequence')
        return


class KeyboardLayout(CueSystem):
    num_keys: int = 12
    fixed_positions: dict = {10: '*Back', 11: '*Space', 12: '*Enter'}
    default_keys: list = list('abcdefghijklmnopqrstuvwxyz1234567890')

    def __init__(self):
        super().__init__()

    def mk_layout(self, num_keys: int = None, fixed_position_keys: dict = None, cue_idx: int = None):
        '''
        Make the layout for the given information.

        The output keys is dict as {i: key}

        :param num_keys int: number of keys.
        :param fixed_position_keys dict: the fixed position keys.
        :param cue_idx int: where to put the cue key.

        :return: if the cue is available, the layout, the cue, and the cue_idx.
                 if the cue is not available, return the layout, cue as None and cue_idx as None.
        :rtype: dict, str, int
        '''
        # Use default if not specified.
        if num_keys is None:
            num_keys = self.num_keys

        if fixed_position_keys is None:
            fixed_position_keys = self.fixed_positions

        random.shuffle(self.default_keys)
        keys = {i: self.default_keys[i % len(
            self.default_keys)] for i in range(num_keys)}
        keys.update(fixed_position_keys)

        # Set cue if provided.
        if cue := self.pop_cue_in_fifo():
            if cue_idx is None:
                cue_idx = random.choice(
                    [e for e in keys if e not in fixed_position_keys])
            keys[cue_idx] = cue
            if cue_idx in fixed_position_keys:
                logger.warning(
                    f'The cue_idx override the fixed_position_keys {cue_idx}, {fixed_position_keys}')
            return keys, cue, cue_idx
        else:
            return keys, None, None


class InputSystem:
    input_buffer: list = []

    @property
    def input_buffer_size(self):
        return len(self.input_buffer)

    def clear_input_buffer(self):
        output = [e for e in self.input_buffer]
        self.input_buffer = []
        return output

    def append_input_buffer(self, inp):
        '''
        Append input buffer.
        It allows iterating input.
        It also converts the input into string format. 

        :param inp: the input objs.
        :return: input_buffer after appending input.
        '''
        if any((isinstance(inp, T) for T in [str, bytes])):
            self.input_buffer.append(str(inp))
        elif isinstance(inp, Iterable):
            [self.append_input_buffer(e) for e in inp]
        else:
            self.input_buffer.append(str(inp))
        logger.debug(f'Appended input_buffer {inp}')
        return self.input_buffer


class MyKeyboard(KeyboardLayout, InputSystem):
    def __init__(self):
        super().__init__()
        logger.info(f'Initialized {self}')


# %% ---- 2025-02-08 ------------------------
# Play ground
if __name__ == '__main__':
    from rich import print
    mk = MyKeyboard()
    print(mk.append_input_buffer('a'))
    print(mk.append_input_buffer(['a', b'b', [1, 2]]))
    for _ in range(10):
        print(mk.mk_layout())

# %% ---- 2025-02-08 ------------------------
# Pending

# %% ---- 2025-02-08 ------------------------
# Pending
