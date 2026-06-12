from utils.dispatcher import Dispatcher


class RoundRobin(Dispatcher):
    def __init__(self):
        super().__init__()
        self.idx = 0

    def dispatch(self, job, servers):
        out = servers[self.idx]
        self.idx = (self.idx + 1) % len(servers)

        return out
