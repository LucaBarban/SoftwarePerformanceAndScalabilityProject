from utils.handle import Handle
from utils.hedged_dispatcher import HedgedDispatcher
from utils.job import Job


class HedgedJSQ(HedgedDispatcher):  # join the shortest queue
    def __init__(self, k: int = 2):
        super().__init__()
        self.k = k

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        # Take the k least shortest queues
        k = min(self.k, len(servers))
        sorted_servers = sorted(servers, key=lambda s: s.pendings())
        return sorted_servers[:k]
