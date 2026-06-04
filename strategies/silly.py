from utils.dispatcher import Dispatcher


class Silly(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job, servers):
        return servers[0]
