from typing import Optional, Any
import logging
import os
import time
from multiprocessing import Process, Queue, queues
from multiprocessing.managers import ListProxy, ValueProxy

from .job import process_job, Job


class Server(Process):
    def __init__(
        self,
        id: int,
        jobs: ListProxy[Optional[Job]],
        ping: queues.Queue[None],
        output: queues.Queue[Optional[Job]],
        timing: ValueProxy[float],
        processing_time: ValueProxy[float],
    ):
        super().__init__()

        self.id = id
        self.jobs = jobs
        self.ping = ping
        self.output = output
        self.timing = timing
        self.processing_time = processing_time

        self.logger = logging.getLogger("logs")

    def run(self):
        os.sched_setaffinity(0, {self.id})

        while True:
            _ = self.ping.get()
            job = self.jobs.pop(0)

            if job is None:
                self.output.put(None)
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

            self.processing_time.value += time.time() - self.timing.value
            self.timing.value = 0.0

            self.output.put(job)
