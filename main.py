import logging
from multiprocessing import Process, Queue, Value
from typing import Optional
from scipy.stats import pareto, randint
import math
import random
import time
import os


class JsonLogger(logging.Formatter):
    def format(self, record):
        return record.getMessage().replace("'", '"')


def init_logging(filename):
    logger = logging.getLogger("logs")
    logger.setLevel(logging.INFO)

    for handler in list(logger.handlers): # remove old handlers
        handler.close()
        logger.removeHandler(handler)

    fmt = JsonLogger()

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(filename, "w")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    
    return logger

def stop_logging():
    logger = logging.getLogger("logs")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


class Job:
    def __init__(self, id: int, alpha: float, size: int):
        self.id = id
        self.alpha = alpha
        self.size = size


class Server(Process):
    def __init__(self, id: int, queue: Queue, timing, processing):
        super().__init__()

        self.id = id
        self.queue = queue
        self.timing = timing
        self.processing = processing

        self.logger = logging.getLogger("logs")

    def run(self):
        os.sched_setaffinity(0, {self.id})

        while True:
            job = self.queue.get()

            if job is None:
                return


            self.timing.value = time.time()

            self.logger.warning({
                "source": "server",
                "event": "start",
                "server_id": self.id,
                "job_id": job.id,
            })

            process_job(job)

            self.logger.warning({
                "source": "server",
                "event": "end",
                "server_id": self.id,
                "job_id": job.id,
                "start_time": self.timing.value,
                "resp_time": time.time() - self.timing.value,
            })

            self.processing.value += time.time() - self.timing.value

            self.timing.value = 0.0


class Handle:
    def __init__(self, id: int):
        self.queue = Queue()
        self.id = id
        self.timing = Value("d", 0.0)
        self.processing_time = Value("d", 0.0)

        self.server = Server(id, self.queue, self.timing, self.processing_time)
        self.server.start()

    def dispatch(self, job: Optional[Job]):
        self.queue.put(job)

    def pendings(self):
        return self.queue.qsize()

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value


def process_job(job: Job, base_work=20_000):
    """
    Simulates a CPU-bound job with heavy-tailed processing time.
    job: job
    """
    # Heavy-tailed amplification
    multiplier = random.paretovariate(job.alpha)

    # Total CPU work
    n = int(base_work * job.size * multiplier)
    acc = 0.0

    for i in range(n):
        acc += math.sin(i) * math.cos(i)

    return acc


class Dispatcher:
    def __init__(self):
        self.logger = logging.getLogger("logs")


    def choose(self, job: Job, servers: list[Handle]) -> Handle:
        servers_info = [
            {"id": s.id, "pendings": s.pendings(), "age": s.current_age()}
            for s in servers
        ]

        chosen = self.dispatch(job, servers)

        self.logger.warning({
            "source": "dispatcher",
            "event": "dispatching",
            "job_id": job.id,
            "servers": servers_info,
            "chosen": chosen.id,
            "decision_time": time.time(),
        })

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]


class JSQ(Dispatcher):  # join the shortest queue
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        # Find the less value of pending
        pendings = [s.pendings() for s in servers]
        min_pending = min(pendings)

        # server with least pending
        idle_servers = [
            s for (i, s) in enumerate(servers) if pendings[i] == min_pending
        ]

        # choose at random a server
        chosen = random.choice(idle_servers)

        return chosen


class JIQ(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        idle_servers = []
        for s in servers:
            if s.pendings() == 0:
                idle_servers.append(s)

        if len(idle_servers) > 0:
            choose = random.choice(idle_servers)
        else:
            choose = random.choice(servers)

        return choose


class Silly(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job, servers):
        return servers[0]


class CheapLAS(Dispatcher):  
    # By assuming to actually know the distribution of the service time, 
    # we can exploit this fact to calculate the mean amount of time the 
    # jobs in line will take to finish + the residual time that the job
    # in services needs. This last part is not directly calculated, but it's
    # "derived" by using the reciprocal of the hazard rate, which is basically
    # a penalty for jobs that have heavy tailed distributions, while others like
    # the exponential will have a smaller amount of time added
    def __init__(self, dist):
        super().__init__()
        self.dist = dist

    def hazardRatePenalty(self, age):
        # calculate the hazard rate and use it as a penalty for long running jobs
        # h(t) = f(t) / S(t)
        #  low hazard rate -> large penalty (job won't finish soon)
        # high hazard rate -> small penalty (job will finish soon)

        if hasattr(self.dist, 'pdf'): # use PDF for continuous, PMF for discrete distributions
            pdf = self.dist.pdf(age)  # probability density function
        else:
            pdf = self.dist.pmf(age)  # probability mass function

        sf = self.dist.sf(age)  # survival function (1-cumulative distribution function)

        hazardRate = 1e5 if sf <= 1e-5 else pdf / sf
        return 1.0 / hazardRate if hazardRate != 0 else float("inf")

    def dispatch(self, job, servers):
        minServer = servers[0]
        minRemainingTime = float("inf")
        for s in servers:
            currJobAge = s.current_age()
            time = s.pendings() * (
                self.dist.mean()
                if self.dist.mean() != float("inf")
                else self.dist.median()
            )  # use median if mean is infinite
            time += self.hazardRatePenalty(
                currJobAge
            )  # + currJobAge (removed, given that it double counts)
            if minRemainingTime > time:
                minServer = s
                minRemainingTime = time

        if minRemainingTime == float(
            "inf"
        ):  # fallback in case no prediction could be done
            minServer = servers[random.randint(0, len(servers) - 1)]

        return minServer


def simulate(dispatcher, load, SERVERS: int = 3, ALPHA: float = 1.0, jobs=100):
    os.sched_setaffinity(0, {0})

    init_logging(f"simulations/{type(dispatcher).__name__}-{load}.txt")
    logger = logging.getLogger("logs")

    servers = [Handle(i + 1) for i in range(SERVERS)]

    start = time.time()

    for id in range(jobs):
        time.sleep(random.expovariate(load) / 10)

        req = Job(id, ALPHA, 40)
        server = dispatcher.choose(req, servers)
        server.dispatch(req)


    for handle in servers:
        handle.dispatch(None)

    for handle in servers:
        handle.server.join()

    diff = time.time() - start
    logger.warning({"source": "dispatcher", "event": "summary", "processing": diff})

    for handle in servers:
        logger.warning({
            "source": "server",
            "event": "summary",
            "server_id": handle.id,
            "processing": handle.processing_time.value,
        })
    
    stop_logging()


if __name__ == "__main__":
    SERVERS = 3
    ALPHA = 1.3  # Alpha parameter for job size extraction (pareto distribution)

    dist = pareto(b=ALPHA, scale=1)
    # dist = randint(low=40, high=41)  # keep aligned with the fixed size set for the jobs

    for load in [0.2, 0.5, 0.8]:
        for dispatcher in [Random(), JSQ(), JIQ(), Silly(), CheapLAS(dist)]:
            random.seed(42)
            simulate(dispatcher, load, SERVERS, ALPHA)

    for dispatcher in [Random(), JSQ(), JIQ(), Silly(), CheapLAS(dist)]:
        random.seed(42)
        simulate(dispatcher, 0.5, SERVERS, 2)

