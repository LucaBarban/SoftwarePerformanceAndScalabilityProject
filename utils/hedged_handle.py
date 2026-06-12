import time
from multiprocessing import Queue, Value
from typing import Optional

from .hedged_server import HedgedServer
from .job import Job


class HedgedHandle:
    def __init__(self, id: int, completed: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value("d", 0.0)
        self.processing_time = Value("d", 0.0)
        self.server = HedgedServer(
            id, self.queue, completed, self.timing, self.processing_time
        )
        self.server.start()

    def dispatch(self, job: Optional[Job]):
        self.queue.put(job)

    def pendings(self):
        return self.queue.qsize()

    @property
    def pid(self) -> int:
        return self.server.pid

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value
