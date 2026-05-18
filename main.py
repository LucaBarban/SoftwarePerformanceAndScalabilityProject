from multiprocessing import Process, Queue, Value
import json
import math
import random
import time


def log_json(**kwargs):
    print(json.dumps(kwargs))

class Job:
    def __init__(self, id: int, size: int):
        self.id = id
        self.size = size


class Server(Process):
    def __init__(self, id: int, queue: Queue, output: Queue, timing):
        super().__init__()

        self.id = id
        self.queue = queue
        self.output = output
        self.timing = timing

    def run(self):
        while True:
            job = self.queue.get()

            self.timing.value = time.time()

            log_json(source="server", server_id=self.id, job_id=job.id, event="start")

            process_job(job)

            log_json(
                source="server",
                server_id=self.id,
                job_id=job.id,
                event="end",
                resp_time=time.time() - self.timing.value,
                start_time=self.timing.value,
            )

            self.output.put(job)
            self.timing.value = 0.0


class Handle:
    def __init__(self, id: int, output: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value("d", 0.0)

        self.server = Server(id, self.queue, output, self.timing)
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
    def choose(self, job: Job, servers: list[Server]) -> Server:
        servers_info = [{"id": s.id, "pendings": s.pendings(), "age": s.current_age()} for s in servers]

        chosen = self.dispatch(job, servers)

        log_json(
            source="dispatcher",
            job_id=job.id,
            servers=servers_info,
            chosen=chosen.id,
            decision_time=time.time(),
        )

        return chosen

    def dispatch(self, job: Job, servers: list[Server]) -> Server:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Server]) -> Server:
        id = random.randint(0, len(servers) - 1)
        return servers[id]


if __name__ == "__main__":
    SERVERS = 3
    JOBS = 100

    output = Queue()
    dispatcher = Random()

    servers = [Handle(i + 1, output) for i in range(SERVERS)]

    # TODO: need to randomly generate `job` instead of 1..JOBS
    for x in range(JOBS):
        time.sleep(.2) # TODO: will replace with lambda-wait

        req = Job(x, x) # TODO: change into extraction from Pareto
        server = dispatcher.choose(req, servers)
        server.dispatch(req)

    for _ in range(JOBS):
        output.get()

    for handle in servers:
        handle.server.terminate()
