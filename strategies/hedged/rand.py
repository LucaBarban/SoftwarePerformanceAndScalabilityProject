import random

from utils.hedged_dispatcher import HedgedDispatcher
from utils.hedged_handle import HedgedHandle
from utils.job import Job


class HedgedRand(HedgedDispatcher):
    def __init__(self, k: int = 2):
        super().__init__()
        self.k = k

    def dispatch(self, job: Job, servers: list[HedgedHandle]) -> HedgedHandle:
        k = min(self.k, len(servers))
        return random.sample(servers, k)
