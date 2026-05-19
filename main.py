from typing import Optional
from multiprocessing import Process, Queue, Value
import json
import math
import random
import time
import os

log: Optional["LoggerProxy"] = None

class LoggerProxy:
    def __init__(self, queue: Queue):
        self.queue = queue
        self.buf = []

    def print(self, **kwargs):
        self.queue.put(kwargs)

    def buffer(self, **kwargs):
        self.buf.append(kwargs)

    def close(self):
        self.queue.put(None)


def _logger_listener_worker(queue: Queue, filename: Optional[str], target_core: int):
    os.sched_setaffinity(0, {target_core})
    f = None
    if filename is not None:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        print(json.dumps({"source": "logger", "message": f"Opening file {filename} in writing mode"}))
        f = open(filename, 'w')

    try:
        while True:
            record = queue.get()
            if record is None: # stopping condition
                break
            
            line = json.dumps(record)
            print(line)
            if f is not None:
                f.write(line + "\n")
                f.flush()
    finally:
        if f is not None:
            f.flush()
            f.close()


def setup_child_logger(queue: Queue):
    global log
    if log is None:
        log = LoggerProxy(queue)


def init_global_logger(target_core: int, filename: Optional[str] = None):
    global log
    log_queue = Queue()
    
    listener = Process(target=_logger_listener_worker, args=(log_queue, filename, target_core))
    listener.start()
    
    log = LoggerProxy(log_queue)
    return listener, log_queue


# --- 2. CLEAN INTERFACES ---

class Job:
    def __init__(self, id: int, size: int):
        self.id = id
        self.size = size


class Server(Process):
    def __init__(self, id: int, queue: Queue, output: Queue, timing, processing, log_queue: Queue):
        super().__init__()
        self.id = id
        self.queue = queue
        self.output = output
        self.timing = timing
        self.processing = processing
        self.log_queue = log_queue

    def run(self):
        setup_child_logger(self.log_queue)
        os.sched_setaffinity(0, {self.id})

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
    def __init__(self, id: int, output: Queue, log_queue: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value('d', 0.0)
        self.processing_time = Value('d', 0.0)
      
        self.server = Server(id, self.queue, output, self.timing, self.processing_time, log_queue)
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
        raise NotImplementedError()


class Random(Dispatcher):
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
    ALPHA = 0.7 # Alpha parameter for job size extraction

    logger_process, log_queue = init_global_logger(filename="simulations/output.txt", target_core=SERVERS+2) # dispatcher/main + servers + logger

    output = Queue()
    servers = [Handle(i + 1, output, log_queue) for i in range(1, SERVERS+1)]
    dispatcher = JIQ()

    start = time.time()

    for x in range(JOBS):
        time.sleep(random.expovariate(LOAD) / 10)
        req = Job(id=x, size=random.paretovariate(ALPHA)) # TODO: change into extraction from Pareto

        server = dispatcher.choose(req, servers)
        server.dispatch(req)


    for _ in range(JOBS):
        output.get()

    diff = time.time() - start

    log.print(source="dispatcher", event="summary", processing=diff)

    for handle in servers:
        log.print(source="server", event="summary", server_id=handle.id, processing=handle.processing_time.value)
        handle.server.terminate()

    # Tear down the background process cleanly
    log.close()
    logger_process.join()