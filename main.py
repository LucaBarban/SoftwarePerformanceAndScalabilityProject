import logging
import os
import random
import time

from scipy.stats import pareto

from strategies import *
from utils import *


def simulate(dispatcher, load, SERVERS: int = 3, ALPHA: float = 1.0, jobs=100):
    os.sched_setaffinity(0, {0})
    random.seed(42)

    init_logging(f"simulations/{type(dispatcher).__name__}-{load}.txt")
    logger = logging.getLogger("logs")

    interarrivals = [random.expovariate(load) / 10 for _ in range(jobs)]
    multipliers = [random.paretovariate(ALPHA) for _ in range(jobs)]

    servers = [Handle(i + 1) for i in range(SERVERS)]

    start = time.time()

    for id, interarrival in enumerate(interarrivals):
        time.sleep(interarrival)

        req = Job(id, multipliers[id], 40)
        server = dispatcher.choose(req, servers)
        server.dispatch(req)

    # This is necessary to stop an infinite loop.
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


def hedged_simulate(
    dispatcher: HedgedDispatcher, load, SERVERS: int = 3, ALPHA: float = 1.0, jobs=100
):
    os.sched_setaffinity(0, {0})
    random.seed(42)
    init_logging(f"simulations/hedged/{type(dispatcher).__name__}-{load}.txt")
    logger = logging.getLogger("logs")

    servers = [HedgedHandle(i + 1, dispatcher.completed) for i in range(SERVERS)]
    interarrivals = [random.expovariate(load) / 10 for _ in range(jobs)]
    multipliers = [random.paretovariate(ALPHA) for _ in range(jobs)]
    start = time.time()

    for id, interarrival in enumerate(interarrivals):
        time.sleep(interarrival)
        req = Job(id, multipliers[id], 40)

        # Dispatching the request to all servers, if we edit the for-loop
        # we can choose a subset.
        chosen_servers = dispatcher.choose(req, servers)
        for server in chosen_servers:
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

    # for load in [0.2, 0.5, 0.8]:
    #     for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(Rand(), Rand()), SharedRoundRobin()]:
    #         simulate(dispatcher, load, SERVERS, ALPHA)

    # for load in [0.2, 0.5, 0.8]:
    #     for dispatcher in [
    #         Rand(),
    #         JSQ(),
    #         JIQ(),
    #         Silly(),
    #         CheapLAS(dist),
    #         RoundRobin(),
    #         MultiDispatcher(Rand(), Rand()),
    #         SharedRoundRobin(),
    #     ]:
    #         simulate(dispatcher, load, SERVERS, ALPHA)

    K = 3
    for load in [0.2, 0.5, 0.8]:
        for dispatcher in [
            HedgedRand(K),
            HedgedJSQ(K),
            HedgedJIQ(K),
            HedgedSilly(K),
            HedgedCheapLAS(dist, K),
            HedgedRoundRobin(K),
            HedgedMultiDispatcher(HedgedRand(K), HedgedRand(K)),
            HedgedSharedRoundRobin(K),
        ]:
            hedged_simulate(dispatcher, load, SERVERS, ALPHA)

    # for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(), SharedRoundRobin()]:
    #     simulate(dispatcher, 0.5, SERVERS, 2)
