from utils.hedged_dispatcher import HedgedDispatcher


# Yeah it's useless adding the hedged policy here.
class HedgedSilly(HedgedDispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job, servers):
        return servers[0]
