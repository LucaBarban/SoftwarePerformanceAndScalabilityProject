from utils.hedged_dispatcher import HedgedDispatcher


class Silly(HedgedDispatcher):
    def __init__(self, k: int = 2):
        super().__init__()
        self.k = k

    def dispatch(self, job, servers):
        k = min(self.k, len(servers))
        return servers[:k]
