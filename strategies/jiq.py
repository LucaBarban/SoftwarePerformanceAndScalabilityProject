import random

from utils.handle import Handle
from utils.job import Job

from .dispatcher import Dispatcher


class JIQ(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        idle_servers = []
        for s in servers:
            if s.pendings() == 0:
                idle_servers.append(s)

        if len(idle_servers) > 0:
            choose = random.choice(idle_servers)
        else:
            choose = random.choice(servers)

        return choose
