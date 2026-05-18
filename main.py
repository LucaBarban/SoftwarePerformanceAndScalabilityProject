from multiprocessing import Process, Queue, Value
import json
import math
import random
import time
import os


def log_json(**kwargs):
    print(json.dumps(kwargs))


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
            request_id = self.queue.get()

            self.timing.value = time.time()

            log_json(source="server", event="start", server_id=self.id, request_id=request_id)

            process_request(request_id)

            log_json(source="server", event="end", server_id=self.id, request_id=request_id, timing=time.time() - self.timing.value)

            self.output.put(request_id)
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

    def dispatch(self, request_id):
        self.queue.put(request_id)

    def pendings(self):
        return self.queue.qsize()

    def current_age(self):
        if self.timing.value == 0.0:
            return 0.0

        return time.time() - self.timing.value


def process_request(x, alpha=1.3, base_work=20_000):
    """
    Simulates a CPU-bound request with heavy-tailed processing time.
    x: request size / difficulty
    """
    # Heavy-tailed amplification
    multiplier = random.paretovariate(alpha)

    # Total CPU work
    n = int(base_work * x * multiplier)
    acc = 0.0

    for i in range(n):
        acc += math.sin(i) * math.cos(i)

    return acc



class Dispatcher:
    def choose(self, req: int, servers: list[Handle]) -> Handle:
        servers_info = [{"id": s.id, "pendings": s.pendings(), "age": s.current_age()} for s in servers]

        chosen = self.dispatch(req, servers)

        log_json(source="dispatcher", event="dispatching", request_id=req, servers=servers_info, chosen=chosen.id)

        return chosen

    def dispatch(self, req: int, servers: list[Handle]) -> Handle:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self):
        super().__init__()
    
    def dispatch(self, req: int, servers: list[Handle]) -> Handle:
        id = random.randint(0, len(servers) - 1)
        return servers[id]



if __name__ == "__main__":
    os.sched_setaffinity(0, {0})

    SERVERS = 3
    REQUESTS = 100
    LOAD = 0.9

    output = Queue()
    dispatcher = Random()

    servers = [Handle(i + 1, output) for i in range(SERVERS)]

    start = time.time()

    # need to randomly generate `request` instead of 1..REQUESTS
    for request in range(REQUESTS):
        time.sleep(random.expovariate(LOAD) / 10)
        server = dispatcher.choose(20, servers)
        server.dispatch(request)

    for _ in range(REQUESTS):
        output.get()

    diff = time.time() - start

    log_json(source="dispatcher", event="summary", processing=diff)

    for handle in servers:
        log_json(source="server", event="summary", server_id=handle.id, processing=handle.processing_time.value)
        handle.server.terminate()

