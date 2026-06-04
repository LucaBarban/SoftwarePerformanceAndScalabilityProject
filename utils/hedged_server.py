import logging
import os
import time
from multiprocessing import Process, Queue

from .job import process_job


class HedgedServer(Process):
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
                    "resp_time": time.time() - self.timing.value,
                }
            )

            self.processing.value += time.time() - self.timing.value

            self.timing.value = 0.0
