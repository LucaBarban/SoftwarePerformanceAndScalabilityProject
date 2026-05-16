from multiprocessing import Process, Queue, Value
import json
import math
import random
import time


def log_json(**kwargs):
    print(json.dumps(kwargs))


class Server(Process):
    def __init__(self, id: int, queue: Queue, output: Queue, timing):
        super().__init__()

        self.id = id
        self.queue = queue
        self.output = output
        self.timing = timing


    def run(self):
        while True:
            request_id = self.queue.get()

            self.timing.value = time.time()

            log_json(source="server", server_id=self.id, request_id=request_id, event="start")

            process_request(request_id)

            log_json(source="server", server_id=self.id, request_id=request_id, event="end", timing=time.time() - self.timing.value)

            self.output.put(request_id)
            self.timing.value = 0.0



class Handle:
    def __init__(self, id: int, output: Queue):
        self.queue = Queue()
        self.id = id
        self.timing = Value('d', 0.0)
       
        self.server = Server(id, self.queue, output, self.timing)
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
    def choose(self, req: int, servers: list[Server]) -> Server:
        servers_info = [{"id": s.id, "pendings": s.pendings(), "age": s.current_age()} for s in servers]

        chosen = self.choose(req, servers)

        log_json(source="dispatcher", request_id=req, servers=servers_info, chosen=chosen.id)

        return chosen

    def dispatch(self, req: int, servers: list[Server]) -> Server:
        raise Exception("NotImplementedException")


class Random(Dispatcher):
    def __init__(self):
        pass
    
    def dispatch(self, req: int, servers: list[Server]) -> Server:
        id = random.randint(0, len(servers) - 1)
        return servers[id]



if __name__ == "__main__":
    SERVERS = 3
    REQUESTS = 100

    output = Queue()
    dispatcher = Random()

    servers = [Handle(i + 1, output) for i in range(SERVERS)]

    # need to randomly generate `request` instead of 1..REQUESTS
    for request in range(REQUESTS):
        time.sleep(.2) # will replace with lambda-wait
        server = dispatcher.choose(request, servers)
        server.dispatch(request)

    for _ in range(REQUESTS):
        output.get()

    for handle in servers:
        handle.server.terminate()

