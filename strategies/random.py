import random

from utils.handle import Handle
from utils.job import Job

from .dispatcher import Dispatcher


class Random(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]
