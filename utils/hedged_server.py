import logging
import os
import signal
import time
from multiprocessing import Process, Queue

from .job import process_job


class HedgedServer(Process):
    def __init__(self, id: int, queue: Queue, completed: Queue, timing, processing):
        super().__init__()

        self.id = id
        self.queue = queue
        self.timing = timing
        self.processing = processing
        self.completed = completed
        self.logger = logging.getLogger("logs")

    def run(self):
        os.sched_setaffinity(0, {self.id})

        while True:
            try:
                # Ignoring the signal when we try to listen
                signal.signal(signal.SIGINT, signal.SIG_IGN)
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
                # We can restore the signal to discard work
                signal.signal(signal.SIGINT, signal.default_int_handler)
                process_job(job)

                # Ignoring kills for logging
                signal.signal(signal.SIGINT, signal.SIG_IGN)

                end_time = time.time()

                self.completed.put({"id": job.id, "server": self.id})
                self.logger.warning(
                    {
                        "source": "server",
                        "event": "end",
                        "server_id": self.id,
                        "job_id": job.id,
                        "start_time": self.timing.value,
                        "resp_time": end_time - self.timing.value,
                        "multiplier": job.multiplier,
                        "end_time": end_time,
                    }
                )

                self.processing.value += end_time - self.timing.value

                self.timing.value = 0.0

                # Restoring initial
                signal.signal(signal.SIGINT, signal.default_int_handler)
            except KeyboardInterrupt:  # SIGINT in python is coded as this
                self.timing.value = 0.0
