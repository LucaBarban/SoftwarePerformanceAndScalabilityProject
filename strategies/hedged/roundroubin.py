from utils.hedged_dispatcher import HedgedDispatcher


class HedgedRoundRobin(HedgedDispatcher):
    def __init__(self, k: int = 2):
        super().__init__()
        self.idx = 0
        self.k = k

    def dispatch(self, job, servers):
        # Sliding window approach, take k servers in rotation
        k = min(self.k, len(servers))
        chosen = []
        for _ in range(k):
            chosen.append(servers[self.idx])
            self.idx = (self.idx + 1) % len(servers)

        return chosen
