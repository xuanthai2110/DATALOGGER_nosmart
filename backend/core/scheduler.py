import time

class Scheduler:
    def __init__(self, interval):
        self.interval = interval

    def wait(self):
        time.sleep(self.interval)