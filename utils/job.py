import math
import random


class Job:
    def __init__(self, id: int, alpha: float, size: int):
        self.id = id
        self.alpha = alpha
        self.size = size


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
