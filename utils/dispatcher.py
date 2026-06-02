import logging
import time

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
                "servers": servers_info,
                "chosen": chosen.id,
                "decision_time": time.time(),
            }
        )

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")

    def hedged_dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")
