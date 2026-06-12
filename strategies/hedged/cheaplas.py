import random

from utils.hedged_dispatcher import HedgedDispatcher


class CheapLAS(HedgedDispatcher):
    # By assuming to actually know the distribution of the service time,
    # we can exploit this fact to calculate the mean amount of time the
    # jobs in line will take to finish + the residual time that the job
    # in services needs. This last part is not directly calculated, but it's
    # "derived" by using the reciprocal of the hazard rate, which is basically
    # a penalty for jobs that have heavy tailed distributions, while others like
    # the exponential will have a smaller amount of time added
    def __init__(self, dist, k: int = 2):
        super().__init__()
        self.dist = dist
        self.k = k

    def hazardRatePenalty(self, age):
        # calculate the hazard rate and use it as a penalty for long running jobs
        # h(t) = f(t) / S(t)
        #  low hazard rate -> large penalty (job won't finish soon)
        # high hazard rate -> small penalty (job will finish soon)

        if hasattr(
            self.dist, "pdf"
        ):  # use PDF for continuous, PMF for discrete distributions
            pdf = self.dist.pdf(age)  # probability density function
        else:
            pdf = self.dist.pmf(age)  # probability mass function

        sf = self.dist.sf(age)  # survival function (1-cumulative distribution function)

        hazardRate = 1e5 if sf <= 1e-5 else pdf / sf
        return 1.0 / hazardRate if hazardRate != 0 else float("inf")

    def __expected_remaining_time__(self, s):
        currJobAge = s.current_age()
        time = s.pendings() * (
            self.dist.mean() if self.dist.mean() != float("inf") else self.dist.median()
        )
        time += self.hazardRatePenalty(currJobAge)
        return time

    def dispatch(self, job, servers):
        k = min(self.k, len(servers))
        try:
            chosen = sorted(servers, key=self.__expected_remaining_time__)
            return chosen[:k]
        except:
            return random.sample(servers, k)
