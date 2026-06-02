import time
from multiprocessing import Queue, Value
from typing import Optional

from .job import Job
from .server import Server


class Handle:
    def __init__(self, id: int):
        self.queue = Queue()
        self.id = id
        self.timing = Value("d", 0.0)
        self.processing_time = Value("d", 0.0)

        self.server = Server(id, self.queue, self.timing, self.processing_time)
        self.server.start()

    def dispatch(self, job: Optional[Job]):
        self.queue.put(job)

    def pendings(self):
        return self.queue.qsize()

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value
