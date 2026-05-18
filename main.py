from typing import Optional
from multiprocessing import Process, Queue, Value
import json
import math
import random
import time
import os


class Logger:
    def __init__(self, filename: Optional[str] = None):
        self.buf = []

        self.f = None
        if filename is not None:
            self.f = open(filename, 'w')

    def format(self, **kwargs):
        return json.dumps(kwargs)

    def print(self, **kwargs):
        print(self.format(**kwargs))

    def buffer(self, **kwargs):
        self.buf.append(kwargs)
        
    def file(self, **kwargs):
        if self.f is None:
            raise Exception("Missing file")
        else:
           self.f.write(self.format(**kwargs)) 

    def close(self):
        if self.f is None:
            raise Exception("Missing file")
        else:
            self.f.close()
   

log = Logger()


class Job:
    def __init__(self, id: int, size: int):
        self.id = id
        self.size = size


class Server(Process):
    def __init__(self, id: int, queue: Queue, output: Queue, timing, processing):
        super().__init__()

        os.sched_setaffinity(0, {id})
        
        self.id = id
        self.queue = queue
        self.output = output
        self.timing = timing
        self.processing = processing

    def run(self):
        while True:
            job = self.queue.get()

            self.timing.value = time.time()

            log.print(source="server", event="start", server_id=self.id, job_id=job.id)

            process_job(job)

            log.print(
                source="server",
                event="end",
                server_id=self.id,
                job_id=job.id,
                start_time=self.timing.value,
                resp_time=time.time() - self.timing.value,
            )

            self.output.put(job)
            self.processing.value += time.time() - self.timing.value

            self.timing.value = 0.0


class Handle:
    def __init__(self, id: int, output: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value('d', 0.0)
        self.processing_time = Value('d', 0.0)
      
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
    def choose(self, job: Job, servers: list[Handle]) -> Handle:
        servers_info = [{"id": s.id, "pendings": s.pendings(), "age": s.current_age()} for s in servers]

        chosen = self.dispatch(job, servers)

        log.print(
            source="dispatcher",
            event="dispatching",
            job_id=job.id,
            servers=servers_info,
            chosen=chosen.id,
            decision_time=time.time(),
        )

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self):
        super().__init__()
    
    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]


class JIQ(Dispatcher):
    def __init__(self):
        super().__init__()

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        # Find the less value of pending
        min_pendings = min(s.pendings() for s in servers)

        # server with less pending
        idle_servers = []
        for s in servers:
            if s.pendings() == min_pendings:
                idle_servers.append(s)

        # choose at random a server
        chosen = random.choice(idle_servers)

        return chosen

if __name__ == "__main__":
    os.sched_setaffinity(0, {0})

    SERVERS = 3
    JOBS = 100
    LOAD = 0.9

    output = Queue()
    servers = [Handle(i + 1, output) for i in range(SERVERS)]
    dispatcher = JIQ()

    start = time.time()

    for x in range(JOBS):
        time.sleep(random.expovariate(LOAD) / 10)
        req = Job(x, x) # TODO: change into extraction from Pareto

        server = dispatcher.choose(req, servers)
        server.dispatch(req)


    for _ in range(JOBS):
        output.get()

    diff = time.time() - start

    log.print(source="dispatcher", event="summary", processing=diff)

    for handle in servers:
        log.print(source="server", event="summary", server_id=handle.id, processing=handle.processing_time.value)
        handle.server.terminate()

