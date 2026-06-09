import random
from typing import List


def gen_interarrivals(load: float, jobs: int, seed: int = 42) -> List[float]:
    """
    Generate "jobs" Poisson-distributed interarrival times
    """
    random.seed(seed)
    return [random.expovariate(load) / 10 for _ in range(jobs)]

def gen_multipliers(alpha: float, jobs: int, seed: int = 42) -> List[float]:
    """
    Generate "jobs" Pareto-distributed multipliers with shape parameter alpha
    """
    random.seed(seed)
    return [random.paretovariate(alpha) for _ in range(jobs)]