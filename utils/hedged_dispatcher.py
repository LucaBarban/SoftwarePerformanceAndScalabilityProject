import logging
import os
import signal
import threading
import time
from multiprocessing import Queue

from .hedged_handle import HedgedHandle
from .job import Job


class HedgedDispatcher:
    def __init__(self):
        self.logger = logging.getLogger("logs")
        self.completed = Queue()
        self.working = {}
        self.lock = threading.Lock()
        self.listener = threading.Thread(
            target=self.__completion_listener__, daemon=True
        )
        self.listener.start()

    def choose(self, job: Job, servers: list[HedgedHandle]) -> list[HedgedHandle]:
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
                "chosen": [s.id for s in chosen],
                "decision_time": time.time(),
            }
        )

        with self.lock:
            self.working[job.id] = chosen

        return chosen

    def dispatch(self, job: Job, servers: list[HedgedHandle]) -> HedgedHandle:
        raise Exception("NotImplementedException")

    def __completion_listener__(self):
        while True:
            # Blocks until a completed job is added
            msg = self.completed.get()
            job_id = msg["id"]
            server_done = msg["server"]

            with self.lock:
                if job_id in self.working:
                    # Find all the slower replicas and kill them
                    handles = self.working[job_id]
                    for handle in handles:
                        if handle.id != server_done:
                            try:
                                self.logger.warning(
                                    {
                                        "source": "dispatcher",
                                        "event": "kill",
                                        "job_id": job_id,
                                        "server": handle.id,
                                    }
                                )
                                os.kill(handle.pid, signal.SIGINT)
                            except ProcessLookupError:
                                pass
                    del self.working[job_id]
