import time
from multiprocessing import Queue, Manager, queues
from multiprocessing.managers import ListProxy
from typing import Optional
import logging

from .job import Job
from .server import Server


class Handle:
    def __init__(self, id: int, output: queues.Queue[Optional[Job]]):
        self.id = id

        self.manager = Manager()

        self.jobs: ListProxy[Optional[Job]] = self.manager.list()
        self.ping = self.manager.Queue()
        self.timing = self.manager.Value("d", 0.0)
        self.processing_time = self.manager.Value("d", 0.0)

        self.logger = logging.getLogger("logs")

        self.server = Server(
            id,
            self.jobs,
            self.ping,  # type: ignore # dumb type
            output,
            self.timing,
            self.processing_time,
        )
        self.server.start()

    def dispatch(self, job: Optional[Job]):
        self.jobs.append(job)
        self.ping.put(None)

    def remove(self, job: Job):
        ids = [j.id for j in self.jobs if j is not None]
        self.logger.warning(
            {
                "source": "server",
                "event": "removing",
                "server_id": self.id,
                "job_id": job.id,
                "awaiting_ids": ids,
            }
        )

        if job.id in ids:
            idx = ids.index(job.id)
            self.jobs.pop(idx)
            self.ping.get_nowait()

            self.logger.warning(
                {
                    "source": "server",
                    "event": "remove",
                    "server_id": self.id,
                    "job_id": job.id,
                }
            )

    def pendings(self):
        return len(self.jobs)

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value
