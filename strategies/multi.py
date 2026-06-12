import random

from utils import Dispatcher


#    ┌─ λ / n
# λ ─┤
#    ┊
#    └─ λ / n
class MultiDispatcher(Dispatcher):
    def __init__(self, *dispatchers: Dispatcher):
        super().__init__()

        self.dispatchers = dispatchers

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

        return output
