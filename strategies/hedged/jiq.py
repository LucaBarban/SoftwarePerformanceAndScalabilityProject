import random

from utils.hedged_dispatcher import HedgedDispatcher
from utils.hedged_handle import HedgedHandle
from utils.job import Job


class HedgedJIQ(HedgedDispatcher):
    def __init__(self, k: int = 2):
        super().__init__()
        self.k = k

    def dispatch(self, job: Job, servers: list[HedgedHandle]) -> HedgedHandle:
        k = min(self.k, len(servers))
        idle_servers = [s for s in servers if s.pendings() == 0]

        if len(idle_servers) >= k:
            return random.sample(idle_servers, k)
        else:
            # Take all idle servers, then randomly sample the remainder from the busy ones
            chosen = list(idle_servers)
            busy_servers = [s for s in servers if s not in chosen]
            needed = k - len(chosen)
            chosen.extend(random.sample(busy_servers, needed))
            return chosen
