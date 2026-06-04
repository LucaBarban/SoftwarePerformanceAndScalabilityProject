import json
import os
import sys
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


def load_points(file_path: str = "simulations/output.txt") -> List[Dict]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError("Couldn't find the requested file to load from")

    points = []

    with open(file_path, mode="r") as f:
        for line in f:
            point = json.loads(line)

            if (
                point["source"] == "server" and "resp_time" not in point.keys()
            ):  # skip logged serving start for each request
                continue

            points.append(point)

    if len(points) == 0:
        raise Exception("No points where loaded. Is the file empty?")

    return points


def deg_queued_jobs_number(points: List[Dict]) -> List[Dict]:
    """
    Process points returned by load_points into a list of dictionaries
    that for each even time save the number of jobs running or at
    waiting each server
    """
    queued_jobs = []
    base_time = 0

    for p in points:
        match p["source"]:
            case "dispatcher":
                if (
                    p["event"] != "dispatching"
                ):  # consider only dispatches (e.g. not summary)
                    continue

                queued_jobs.append({"time": float(p["decision_time"])})
                for server in p["servers"]:
                    n_jobs = 0
                    n_jobs = int(server["pendings"])
                    n_jobs += 1 if float(server["age"]) != 0 else 0
                    queued_jobs[-1][server["id"]] = n_jobs
                queued_jobs[-1][p["chosen"]] += 1

            case "server":
                queued_jobs.append(queued_jobs[-1].copy())
                queued_jobs[-1]["time"] = float(p["start_time"]) + float(p["resp_time"])
                queued_jobs[-1][p["server_id"]] -= 1

            case _:
                continue

        # make the time start from 0
        if len(queued_jobs) == 1:
            base_time = queued_jobs[0]["time"]
            queued_jobs[-1]["time"] = 0
        else:
            queued_jobs[-1]["time"] -= base_time

    # reorder based on time, just in case (should do anything)
    return sorted(queued_jobs, key=lambda x: x["time"])


def calculate_plot_times_utilization(
    queued_jobs: List[Dict], window_size: float
) -> Tuple[List[float], Dict[Any, List], List[str]]:
    """
    queued_jobs: data returned by deg_queued_jobs_number
    window_size: size in seconds of the window of time that will
                 be considered to calculate the utilization
    """
    server_ids = [key for key in queued_jobs[0].keys() if key != "time"]
    plot_times = []
    utilizations = {s: [] for s in server_ids}

    for i in range(1, len(queued_jobs)):
        current_time = queued_jobs[i]["time"]
        window_start = max(0.0, current_time - window_size)

        active_window_duration = current_time - window_start
        window_busy_time = {
            s: 0.0 for s in server_ids
        }  # busy times inside this specific window

        # look backwards for past events that intersect with the active window
        for j in range(i, 0, -1):
            prev_event = queued_jobs[j - 1]
            curr_event = queued_jobs[j]

            if curr_event["time"] <= window_start:
                break

            # determine overlap of this "segment" between events with the window
            seg_start = max(window_start, prev_event["time"])
            seg_end = min(current_time, curr_event["time"])
            duration_in_window = seg_end - seg_start

            if duration_in_window > 0:
                for s in server_ids:
                    if (
                        prev_event[s] > 0
                    ):  # add busy period if server was busy in segment
                        window_busy_time[s] += duration_in_window

        for s in server_ids:  # calculate utilizations
            utilizations[s].append(window_busy_time[s] / active_window_duration)

        plot_times.append(current_time)

    return plot_times, utilizations, server_ids


def plot_utilizations_sliding_window(
    plot_times: List[float],
    utilizations: Dict[Any, List],
    server_ids: List[str],
    window_size: float,
):
    plt.figure(figsize=(12, 6))
    time_deltas = np.diff(plot_times, append=plot_times[-1])
    for s in server_ids:
        if sum(time_deltas) > 0:  # weighted average of the utilization for all server
            total_avg = np.average(utilizations[s], weights=time_deltas)
        else:
            total_avg = 0.0

        plt.plot(
            plot_times,
            utilizations[s],
            label=f"Server {s} (Average Utilization: {total_avg * 100:.2f}%)",
            linewidth=1.5,
        )
    plt.title(f"Sliding Window Server Utilization (Window Size = {window_size}s)")
    plt.xlabel("Simulation Time")
    plt.ylabel("Utilization")
    plt.ylim(-0.05, 1.05)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.show()


def plot_response_time_distribution(
    datasets: Dict[str, List[Dict]],
    bins: int = 20,
    title_suffix: str = "",
    log_mode: str = "off",
    plot_type: str = "bar",
    probability: bool = False,
):
    """
    Process points from load_points and plots the distribution of the seen response times

    datasets: data returned by load_points
    bins: number of "slots" where to put jobs based on their response time
    title_suffix: extra information in the plot's title
    log_mode: off for linear scales, y for log density, x for log response time, 
              xy for log-log scale
    plot_type: the type of the plot (e.g. "bar" for a histogram or "line" for the same
               but without the colored filling)
    probability: true to scale heights to values between 0 and 1 (relative frequency)
    """
    plt.figure(figsize=(10, 5))

    for label, points in datasets.items():
        response_times = [
            p["resp_time"]
            for p in points
            if p.get("source") == "server" and "resp_time" in p
        ]

        if not response_times:
            continue

        mean_time = np.mean(response_times)
        median_time = np.median(response_times)

        # generate logarithmically spaced bins ONLY if the x-axis uses a log scale
        actual_bins = (
            np.logspace(
                np.log10(max(1e-5, min(response_times))),
                np.log10(max(response_times)),
                bins,
            )
            if "x" in log_mode
            else bins
        )

        hist_kwargs = {"density": not probability}
        if probability:
            hist_kwargs["weights"] = np.ones_like(response_times) / len(response_times)

        if plot_type == "line":
            hist_kwargs["histtype"] = "step"
            hist_kwargs["linewidth"] = 2
            hist_kwargs["alpha"] = 0.9
        else:
            hist_kwargs["histtype"] = "bar"
            hist_kwargs["edgecolor"] = "black"
            hist_kwargs["alpha"] = 0.5

        plt.hist(
            response_times,
            bins=actual_bins,
            label=f"{label} (Mean: {mean_time:.3f}s, Med: {median_time:.3f}s)",
            **hist_kwargs,
        )

    # set axis scales based on the mode
    if "x" in log_mode:
        plt.xscale("log")
    if "y" in log_mode:
        plt.yscale("log")

    title = "Distribution of Server Response Times" + (
        f" - {title_suffix}" if title_suffix else ""
    )
    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Response Time (" + ("log " if "x" in log_mode else "") + "seconds)", fontsize=12)
    plt.ylabel(("Probability" if probability else "Density") + (" (log scale)" if "y" in log_mode else ""), fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6, which="both")
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.show()


def plot(
    file_path: str = "simulations/output.txt",
    bins: int = 20,
    window_size: float = 2.0,
    log_mode: str = "off",
    plot_type: str = "bar",
    probability: bool = False,
):
    """
    file_path: path of the to load data from
    bins: number of bins used in the service time distribution graph
    window_size: size in seconds of the window of time that will
                 be considered to calculate the utilization
    """
    points = load_points(file_path)
    queued_jobs = deg_queued_jobs_number(points)
    plot_times, utilizations, server_ids = calculate_plot_times_utilization(
        queued_jobs, window_size
    )

    plot_response_time_distribution(
        {os.path.basename(file_path): points},
        bins,
        log_mode=log_mode,
        plot_type=plot_type,
        probability=probability,
    )
    plot_utilizations_sliding_window(plot_times, utilizations, server_ids, window_size)


def plot_comparison(
    files: List[str], bins: int = 20, log_mode: str = "off", plot_type: str = "bar", probability: bool = False
):
    """
    Automagically plot the data by grouping the dispatchers based on the specified load
    in each filename (uses the format "dispatcherType-load.txt")
    """
    loads = {}
    for file_path in files:
        filename = os.path.basename(file_path).replace(".txt", "")
        parts = filename.split("-")
        dispatcher = parts[0] if len(parts) > 0 else "Unknown"
        load = parts[1] if len(parts) > 1 else "Unknown"

        if load not in loads:
            loads[load] = {}
        loads[load][dispatcher] = load_points(file_path)

    for load, datasets in sorted(loads.items()):
        plot_response_time_distribution(
            datasets,
            bins,
            title_suffix=f"Load: {load}",
            log_mode=log_mode,
            plot_type=plot_type,
            probability=probability,
        )



PLOT_TYPE = "line" # bar (with filling) or line (no filling)
LOG_MODE = "x"     # off, x (response time, x axis), y (density, y axis), xy (both axis)
PROBABILITY = True # False for standard density (area=1), True for relative frequency (sum of heights=1)


if __name__ == "__main__":
    if len(sys.argv) == 2 and os.path.isfile(sys.argv[1]): # plot for a single file (filename passed)
        plot(sys.argv[1], log_mode=LOG_MODE, plot_type=PLOT_TYPE, probability=PROBABILITY)

    elif len(sys.argv) == 1 and os.path.isdir("simulations"): # no filename passed, plot everything (except for utilization graphs)
        sim_files = [
            os.path.join("simulations", f)
            for f in os.listdir("simulations")
            if f.endswith(".txt")
        ]
        if sim_files:
            plot_comparison(sim_files, log_mode=LOG_MODE, plot_type=PLOT_TYPE, probability=PROBABILITY)
        else:
            print("No simulator .txt files found inside the 'simulations/' directory.")

    else:
        print(
            f"Usage:\n  To plot all files:    python3 {sys.argv[0]}\n  To plot single file:  python3 {sys.argv[0]} <file_path>"
        )
        sys.exit(1)