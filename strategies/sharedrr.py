import random

from utils import Dispatcher
from strategies.roundroubin import RoundRobin


class SharedRoundRobin(Dispatcher):
    def __init__(self):
        super().__init__()
        self.dispatchers = [RoundRobin(), RoundRobin()]

    def dispatch(self, job, servers):
        idx = random.randint(0, len(self.dispatchers) - 1)
        dispatcher = self.dispatchers[idx]

        self.logger.warning(
            {
                "source": "multi",
                "event": "dispatching",
                "job_id": job.id,
                "dispatcher": idx,
            }
        )

        output = dispatcher.dispatch(job, servers)

        for i, disp in enumerate(self.dispatchers):
            if i != idx:
                disp.idx = dispatcher.idx

        return output
