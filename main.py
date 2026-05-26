from multiprocessing import Process, Queue, Value, Lock
from typing import Optional
from scipy.stats import pareto, randint
import json
import math
import random
import time
import os


class Job:
    def __init__(self, id: int, size: int):
        self.id = id
        self.size = size


class Server(Process):
    def __init__(self, id: int, queue: Queue, output: Queue, timing, processing):
        super().__init__()
        self.id = id
        self.queue = queue
        self.output = output
        self.timing = timing
        self.processing = processing

    def run(self):
        os.sched_setaffinity(0, {self.id})

        while True:
            job = self.queue.get()

            self.timing.value = time.time()

            self.output.put(
                {
                    "source": "server",
                    "event": "start",
                    "server_id": self.id,
                    "job_id": job.id,
                }
            )

            process_job(job)

            self.output.put(
                {
                    "source": "server",
                    "event": "end",
                    "server_id": self.id,
                    "job_id": job.id,
                    "start_time": self.timing.value,
                    "resp_time": time.time() - self.timing.value,
                }
            )

            self.processing.value += time.time() - self.timing.value

            self.timing.value = 0.0


class Handle:
    def __init__(self, id: int, output: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value("d", 0.0)
        self.processing_time = Value("d", 0.0)

        self.server = Server(id, self.queue, output, self.timing, self.processing_time)
        self.server.start()

    def dispatch(self, job: Job):
        self.queue.put(job)

    def pendings(self):
        return self.queue.qsize()

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value


def process_job(job: Job, alpha=1.3, base_work=20_000):
    """
    Simulates a CPU-bound job with heavy-tailed processing time.
    job: job
    """
    # Heavy-tailed amplification
    multiplier = random.paretovariate(alpha)

    # Total CPU work
    n = int(base_work * job.size * multiplier)
    acc = 0.0

    for i in range(n):
        acc += math.sin(i) * math.cos(i)

    return acc


class Dispatcher:
    def __init__(self, output: Queue):
        self.output = output

    def choose(self, job: Job, servers: list[Handle]) -> Handle:
        servers_info = [
            {"id": s.id, "pendings": s.pendings(), "age": s.current_age()}
            for s in servers
        ]

        chosen = self.dispatch(job, servers)

        self.output.put(
            {
                "source": "dispatcher",
                "event": "dispatching",
                "job_id": job.id,
                "servers": servers_info,
                "chosen": chosen.id,
                "decision_time": time.time(),
            }
        )

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self, output: Queue):
        super().__init__(output)

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]


class SQF(Dispatcher):  # shortest queue first
    def __init__(self, output: Queue):
        super().__init__(output)

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
    def __init__(self, output: Queue):
        super().__init__(output)

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        for s in servers:
            if s.pendings() == 0:
                return s

        return servers[random.randint(0, len(servers) - 1)]


class Silly(Dispatcher):
    def __init__(self, output: Queue, dist):
        super().__init__(output)

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
    def __init__(self, output: Queue, dist):
        super().__init__(output)
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


def log(f, event):
    line = json.dumps(event)

    print(line)
    f.write(line + "\n")


if __name__ == "__main__":
    os.sched_setaffinity(0, {0})

    LOGFILE = "simulations/output.txt"
    SERVERS = 3
    JOBS = 100
    LOAD = 0.9
    ALPHA = 1.0  # Alpha parameter for job size extraction
    XM = 1  # x_m parameter for Pareto distribution

    # dist = pareto(b=ALPHA, scale=XM)
    dist = randint(low=40, high=41)  # keep aligned with the fixed size set for the jobs

    output = Queue()
    servers = [Handle(i + 1, output) for i in range(SERVERS)]
    dispatcher = JIQ(output)
    # dispatcher = CheapLAS(dist)

    start = time.time()

    for id in range(JOBS):
        time.sleep(random.expovariate(LOAD) / 10)

        # req = Job(id=id, size=random.expovariate(ALPHA))
        # req = Job(id=id, size=random.paretovariate(ALPHA) * XM)
        req = Job(id, 40)
        # `exp(LOAD) / 10` e `Job(size=40)` sembra diano valori gestibili
        # possiamo ricalibrarli in caso

        server = dispatcher.choose(req, servers)
        server.dispatch(req)

    with open(LOGFILE, "w") as f:
        for _ in range(3 * JOBS):
            log(f, output.get())

        diff = time.time() - start

        log(f, {"source": "dispatcher", "event": "summary", "processing": diff})

        for handle in servers:
            log(
                f,
                {
                    "source": "server",
                    "event": "summary",
                    "server_id": handle.id,
                    "processing": handle.processing_time.value,
                },
            )
            handle.server.terminate()
