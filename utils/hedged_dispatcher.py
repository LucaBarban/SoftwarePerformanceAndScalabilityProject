import logging
import time

from .hedged_handle import HedgedHandle
from .job import Job


class HedgedDispatcher:
    def __init__(self):
        self.logger = logging.getLogger("logs")

    def choose(self, job: Job, servers: list[HedgedHandle]) -> HedgedHandle:
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

    def dispatch(self, job: Job, servers: list[HedgedHandle]) -> HedgedHandle:
        raise Exception("NotImplementedException")
