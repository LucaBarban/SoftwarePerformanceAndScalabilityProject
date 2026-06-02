import random

from utils.handle import Handle
from utils.job import Job

from .dispatcher import Dispatcher


class JSQ(Dispatcher):  # join the shortest queue
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        # Find the less value of pending
        pendings = [s.pendings() for s in servers]
        min_pending = min(pendings)

        # server with least pending
        idle_servers = [
            s for (i, s) in enumerate(servers) if pendings[i] == min_pending
        ]

        # choose at random a server
        chosen = random.choice(idle_servers)

        return chosen
