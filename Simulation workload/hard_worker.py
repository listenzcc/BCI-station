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

from sync.routine_center.client_base import BaseClientSocket, MailMan

logger.add('log/keyboard hiker.log', rotation='5 MB')


# %% ---- 2025-01-13 ------------------------
# Function and class
mm = MailMan('simulation-workload-1')

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
        letter['_stations'].append((self.path_uid, time.time()))
        Thread(target=self.workload_in_seconds, args=(letter,), daemon=True).start()

    def workload_in_seconds(self, letter):
        mm.insert_pending_letter(letter)
        letter['dst'] = letter['src']
        letter['src'] = self.path_uid
        time.sleep(random.randint(2, 5))
        self.send_message(json.dumps(letter))
        mm.archive_finished_letter(letter)
        mm.remove_pending_letter(letter['uid'])
    



# %% ---- 2025-01-13 ------------------------
# Play ground
if __name__ == '__main__':
    # Socket client
    client = MyClient(host='localhost')
    client.connect()
    input('Press enter to stop.')
    client.close()

# %% ---- 2025-01-13 ------------------------
# Pending



# %% ---- 2025-01-13 ------------------------
# Pending
