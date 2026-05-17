from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np
import json, os


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
) -> Tuple[List[float], Dict[List], List[str]]:
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
    utilizations: Dict[List],
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
            label=f"Server {s} (Average Utilization: {total_avg*100:.2f}%)",
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


def plot_response_time_distribution(points: List[Dict], bins: int = 20):
    """
    Process points returned by load_points and plots the distribution of
    the seen response times
    """
    response_times = [
        p["resp_time"]
        for p in points
        if p.get("source") == "server" and "resp_time" in p
    ]

    mean_time = np.mean(response_times)
    median_time = np.median(response_times)

    plt.figure(figsize=(10, 5))
    plt.hist(
        response_times,
        bins=bins,
        color="skyblue",
        edgecolor="black",
        alpha=0.7,
        density=True,
    )

    plt.axvline(
        mean_time,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Mean: {mean_time:.3f}s",
    )
    plt.axvline(
        median_time,
        color="green",
        linestyle="-.",
        linewidth=2,
        label=f"Median: {median_time:.3f}s",
    )

    plt.title("Distribution of Server Response Times", fontsize=14, fontweight="bold")
    plt.xlabel("Response Time (seconds)", fontsize=12)
    plt.ylabel("Density", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.show()


def plot(file_path: str = "simulations/output.txt", bins:int = 20, window_size: float = 2.0):
    """
    file_path: path of the to load data from
    bins: number of bins used in the service time distribution graph
    window_size: size in seconds of the window of time that will
                 be considered to calculate the utilization
    """
    points = load_points(file_path)
    queued_jobs = deg_queued_jobs_number(points)
    plot_times, utilizations, server_ids = calculate_plot_times_utilization(queued_jobs, window_size)

    plot_response_time_distribution(points, bins)
    plot_utilizations_sliding_window(plot_times, utilizations, server_ids, window_size)


plot()


# plot carico medio server per tot secondi passati per ogni punto
# raccolta response time (media + discretizzazione per conteggio numero)


# plottare le seguenti cose:
# - distribuzione response time (discretizzazione richiesta) + media (del testo in alto a dx per esempio?)
# - plot carico sui server (discretizzare nel tempo anche qua, plot calcolato come response time accumulato / tempo al momento * 100)
