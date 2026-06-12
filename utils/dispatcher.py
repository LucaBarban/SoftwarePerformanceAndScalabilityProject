import logging
import time
import random

from .handle import Handle
from .job import Job


class Dispatcher:
    def __init__(self):
        self.logger = logging.getLogger("logs")

    def choose(self, job: Job, servers: list[Handle]) -> Handle:
        servers_info = [
            {"id": s.id, "pendings": s.pendings(), "age": s.current_age()}
            for s in servers
        ]

        chosen = self.dispatch(job, servers)

        self.logger.warning(
            {
                "source": "dispatcher",
                "event": "dispatching",
                "job_id": job.id,
                "multiplier": job.multiplier,
                "servers": servers_info,
                "chosen": chosen.id,
                "decision_time": time.time(),
            }
        )

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")

    def hedge(
        self, job: Job, servers: list[Handle], concurrency: int = 2
    ) -> list[Handle]:
        chosen = self.choose(job, servers)
        others = [s for s in servers if s != chosen]

        extras = random.sample(others, concurrency - 1)

        self.logger.warning(
            {
                "source": "dispatcher",
                "event": "hedge",
                "job_id": job.id,
                "others": [o.id for o in extras],
            }
        )

        return [chosen, *extras]
