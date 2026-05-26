from multiprocessing import Process, Queue, Value, Lock
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

            self.output.put({"source": "server", "event": "start", "server_id": self.id, "job_id": job.id})

            process_job(job)

            self.output.put({
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
    def __init__(self, output: Queue):
        self.output = output

    def choose(self, job: Job, servers: list[Handle]) -> Handle:
        servers_info = [{"id": s.id, "pendings": s.pendings(), "age": s.current_age()} for s in servers]

        chosen = self.dispatch(job, servers)

        self.output.put({
            "source": "dispatcher",
            "event": "dispatching",
            "job_id": job.id,
            "servers": servers_info,
            "chosen": chosen.id,
            "decision_time": time.time(),
        })

        return chosen

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        raise NotImplementedError()


class Random(Dispatcher):
    def __init__(self, output: Queue):
        super().__init__(output)
    
    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]


class JIQ(Dispatcher):
    def __init__(self, output: Queue):
        super().__init__(output)

    def dispatch(self, job: Job, servers: list[Handle]) -> Handle:
        # Find the less value of pending
        pendings= [s.pendings() for s in servers]
        min_pending = min(pendings)

        # server with least pending
        idle_servers = [
            s
            for (i, s) in enumerate(servers)
            if pendings[i] == min_pending
        ]

        # choose at random a server
        chosen = random.choice(idle_servers)

        return chosen

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
    ALPHA = 0.7 # Alpha parameter for job size extraction

    logger_process, log_queue = init_global_logger(filename="simulations/output.txt", target_core=SERVERS+2) # dispatcher/main + servers + logger

    output = Queue()
    servers = [Handle(i + 1, output) for i in range(SERVERS)]
    dispatcher = JIQ(output)

    start = time.time()

    for id in range(JOBS):
        time.sleep(random.expovariate(LOAD) / 10)
        # req = Job(id=id, size=random.paretovariate(ALPHA)) # TODO: change into extraction from Pareto
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
            log(f, {"source": "server", "event": "summary", "server_id": handle.id, "processing": handle.processing_time.value})
            handle.server.terminate()
