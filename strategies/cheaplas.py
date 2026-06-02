import random

from utils.dispatcher import Dispatcher


class CheapLAS(Dispatcher):
    # By assuming to actually know the distribution of the service time,
    # we can exploit this fact to calculate the mean amount of time the
    # jobs in line will take to finish + the residual time that the job
    # in services needs. This last part is not directly calculated, but it's
    # "derived" by using the reciprocal of the hazard rate, which is basically
    # a penalty for jobs that have heavy tailed distributions, while others like
    # the exponential will have a smaller amount of time added
    def __init__(self, dist):
        super().__init__()
        self.dist = dist

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
