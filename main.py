import logging
import os
import random
import time

from scipy.stats import pareto

from strategies import *
from utils import *
from utils.randval_generators import gen_interarrivals, gen_multipliers


def simulate(dispatcher, load, SERVERS: int = 3, ALPHA: float = 1.0, jobs=100):
    os.sched_setaffinity(0, {0})
    random.seed(42)

    init_logging(f"simulations/{type(dispatcher).__name__}-{load}.txt")
    logger = logging.getLogger("logs")

    interarrivals = gen_interarrivals(load, jobs)
    multipliers = gen_multipliers(ALPHA, jobs)

    servers = [Handle(i + 1) for i in range(SERVERS)]

    start = time.time()

    for id, (interarrival, multiplier) in enumerate(zip(interarrivals, multipliers)):
        time.sleep(interarrival)

        req = Job(id, ALPHA, 40, multiplier)
        server = dispatcher.choose(req, servers)
        server.dispatch(req)

    for handle in servers:
        handle.dispatch(None)

    for handle in servers:
        handle.server.join()

    diff = time.time() - start
    logger.warning({"source": "dispatcher", "event": "summary", "processing": diff})

    for handle in servers:
        logger.warning(
            {
                "source": "server",
                "event": "summary",
                "server_id": handle.id,
                "processing": handle.processing_time.value,
            }
        )

    stop_logging()


if __name__ == "__main__":
    SERVERS = 3
    ALPHA = 1.3  # Alpha parameter for job size extraction (pareto distribution)

    dist = pareto(b=ALPHA, scale=1)
    # dist = randint(low=40, high=41)  # keep aligned with the fixed size set for the jobs

    for load in [0.2, 0.5, 0.8]:
        for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(Rand(), Rand()), SharedRoundRobin()]:
            simulate(dispatcher, load, SERVERS, ALPHA)

    # for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(), SharedRoundRobin()]:
    #     simulate(dispatcher, 0.5, SERVERS, 2)
