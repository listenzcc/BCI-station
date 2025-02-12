"""
File: hard_worker.py
Author: Chuncheng Zhang
Date: 2025-01-13
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    The simulation workload with client_base communication.

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2025-01-13 ------------------------
# Requirements and constants
import time
import json
import random
from threading import Thread

from loguru import logger
from rich import print, inspect

from sync.routine_center.client_base import BaseClientSocket

logger.add('log/keyboard hiker.log', rotation='5 MB')


# %% ---- 2025-01-13 ------------------------
# Function and class

class MyClient(BaseClientSocket):
    path = '/client/simulationWorkload'
    uid = 'simulation-workload-1'

    def __init__(self, host=None, port=None, timeout=None):
        super().__init__(**dict(host=host, port=port, timeout=timeout))
        logger.info(f'Initializing client: {self.path_uid}')
        pass

    def handle_message(self, message):
        super().handle_message(message)
        letter = json.loads(message)
        # Stamp the letter.
        letter['_stations'].append((self.path_uid, time.time()))
        # Save the bag into the bag_pending.
        self.mm.bag_pending.insert_letter(letter)
        Thread(target=self.workload_in_seconds,
               args=(letter,), daemon=True).start()

    def workload_in_seconds(self, letter):
        # Ready to send it back.
        letter['dst'] = letter['src']
        letter['src'] = self.path_uid
        # Work for a few seconds.
        time.sleep(random.randint(2, 5))
        # Send the letter back.
        self.send_message(json.dumps(letter))
        # Mark the letter as finished.
        if lt := self.mm.bag_pending.fetch_letter(letter['uid']):
            self.mm.bag_finished.insert_letter(lt)
        self.mm.bag_finished.insert_letter(lt)


# %% ---- 2025-01-13 ------------------------
# Play ground
if __name__ == '__main__':
    # Socket client
    client = MyClient()
    client.connect()
    input('Press enter to stop.')
    client.close()

# %% ---- 2025-01-13 ------------------------
# Pending


# %% ---- 2025-01-13 ------------------------
# Pending
