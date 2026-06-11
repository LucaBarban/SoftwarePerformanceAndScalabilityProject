from typing import Optional
import logging
import os
import random
import time

from scipy.stats import pareto
from multiprocessing import Queue, Process
from select import select

from strategies import *
from utils import *


def spawn_jobs(interarrivals: list[float], multipliers: list[float], queue: Queue):
    os.sched_setaffinity(0, {4})

    for id, interarrival in enumerate(interarrivals):
        time.sleep(interarrival)

        job = Job(id, multipliers[id], 40)
        queue.put(job)

    queue.put(None)


def simulate(
        dispatcher: Dispatcher,
        load: float,
        SERVERS: int = 3,
        ALPHA: float = 1.0,
        hedge: bool = False,
        jobs=100
    ):
    os.sched_setaffinity(0, {0})
    random.seed(42)

    init_logging(f"simulations/{type(dispatcher).__name__}-{load}.txt")
    logger = logging.getLogger("logs")

    interarrivals = [random.expovariate(load) / 10 for _ in range(jobs)]
    multipliers = [random.paretovariate(ALPHA) for _ in range(jobs)]

    input: Queue[Optional[Job]] = Queue()  # job spawn
    output: Queue[Optional[Job]] = Queue() # job completed

    producer = Process(target=spawn_jobs, args=(interarrivals, multipliers, input))
    servers = [Handle(i + 1, output) for i in range(SERVERS)]

    start = time.time()
    producer.start()

    queues = [input, output]
    fds = [q._reader for q in queues]
    done = 0

    while done < SERVERS:
        ready, _, _ = select(fds, [], [])
        for fd in ready:
            idx = fds.index(fd)
            job = queues[idx].get()

            if idx == 0: # input queue -> dispatcher
                if job is None:
                    # close all servers
                    for server in servers:
                        server.dispatch(None)
                elif hedge:
                    chosen = dispatcher.hedge(job, servers)
                    for server in chosen:
                        server.dispatch(job)
                else:
                    server = dispatcher.choose(job, servers)
                    server.dispatch(job)

            elif idx == 1:
                if job is None:
                    done += 1
                    continue

                if hedge:
                    for server in servers:
                        server.remove(job)

                
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

    simulate(Silly(), 0.5, SERVERS, ALPHA)
    # for load in [0.2, 0.5, 0.8]:
    #     for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(Rand(), Rand()), SharedRoundRobin()]:
    #         simulate(dispatcher, load, SERVERS, ALPHA)

    # for dispatcher in [Rand(), JSQ(), JIQ(), Silly(), CheapLAS(dist), RoundRobin(), MultiDispatcher(), SharedRoundRobin()]:
    #     simulate(dispatcher, 0.5, SERVERS, 2)
