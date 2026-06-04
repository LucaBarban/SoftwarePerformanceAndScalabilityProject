import random

from utils.handle import Handle
from utils.hedged_dispatcher import HedgedDispatcher
from utils.job import Job


# Same as Silly dispatcher, useless.
class HedgedRand(HedgedDispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]
