import random

from strategies.hedged.roundroubin import HedgedRoundRobin
from utils.hedged_dispatcher import HedgedDispatcher


class HedgedSharedRoundRobin(HedgedDispatcher):
    def __init__(self, k: int = 2):
        super().__init__()
        self.dispatchers = [HedgedRoundRobin(k), HedgedRoundRobin(k)]

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
