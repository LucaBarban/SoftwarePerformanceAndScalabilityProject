import logging
import os
import time
from multiprocessing import Process, Queue

from .job import process_job


class Server(Process):
    def __init__(self, id: int, queue: Queue, timing, processing):
        super().__init__()

        self.id = id
        self.queue = queue
        self.timing = timing
        self.processing = processing

        self.logger = logging.getLogger("logs")

    def run(self):
        os.sched_setaffinity(0, {self.id})

        while True:
            job = self.queue.get()

            if job is None:
                return

            self.timing.value = time.time()

            self.logger.warning(
                {
                    "source": "server",
                    "event": "start",
                    "server_id": self.id,
                    "job_id": job.id,
                    "multiplier": job.multiplier,
                    "start_time": time.time(),
                }
            )

            process_job(job)

            self.logger.warning(
                {
                    "source": "server",
                    "event": "end",
                    "server_id": self.id,
                    "job_id": job.id,
                    "start_time": self.timing.value,
                    "multiplier": job.multiplier,
                    "end_time": time.time(),
                }
            )

            self.processing.value += time.time() - self.timing.value

            self.timing.value = 0.0
