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
    dispatched = []

    with open(file_path, mode="r") as f:
        for line in f:
            point = json.loads(line)

            if (
                point["source"] == "dispatcher" and point["event"] == "dispatching"
            ):
                dispatched.append(point)

            if (
                point["source"] == "server" and point["event"] != "end"
            ):
                continue

            if (
                point["source"] == "server" and point["event"] == "end"
            ):
                starting = [p for p in dispatched if p["job_id"] == point["job_id"]]
                starting = starting[0]
                point["resp_time"] = point["end_time"] - starting["decision_time"]
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
                if isinstance(p["chosen"], list):
                    for item in p["chosen"]:
                        queued_jobs[-1][item] += 1
                else:
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
    save_path: str = None,
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
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def plot_response_time_distribution(
    datasets: Dict[str, List[Dict]],
    bins: int = 20,
    title_suffix: str = "",
    log_mode: str = "off",
    plot_type: str = "bar",
    probability: bool = False,
    save_path: str = None,
):
    """
    Process points from load_points and plots the distribution of the seen response times

    datasets: data returned by load_points
    bins: number of "slots" where to put jobs based on their response time
    title_suffix: extra information in the plot's title
    log_mode: off for linear scales, y for log density, x for log response time,
              xy for log-log scale
    plot_type: the type of the plot ("bar" for a histogram or "line")
    probability: true to scale heights to values between 0 and 1 (relative frequency)
    save_path: where to save the plot if specified
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

        label_str = f"{label} (Mean: {mean_time:.3f}s, Med: {median_time:.3f}s)"

        if plot_type == "line":
            counts, edges = np.histogram(
                response_times, bins=actual_bins, **hist_kwargs
            )
            bin_centers = (
                np.sqrt(edges[:-1] * edges[1:])
                if "x" in log_mode
                else (edges[:-1] + edges[1:]) / 2
            )
            plt.plot(bin_centers, counts, label=label_str, linewidth=2, alpha=0.9)
        else:
            hist_kwargs.update({"histtype": "bar", "edgecolor": "black", "alpha": 0.5})
            plt.hist(response_times, bins=actual_bins, label=label_str, **hist_kwargs)

    # set axis scales based on the mode
    if "x" in log_mode:
        plt.xscale("log")
    if "y" in log_mode:
        plt.yscale("log")

    title = "Distribution of Server Response Times" + (
        f" - {title_suffix}" if title_suffix else ""
    )
    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel(
        "Response Time (" + ("log " if "x" in log_mode else "") + "seconds)",
        fontsize=12,
    )
    plt.ylabel(
        ("Probability" if probability else "Density")
        + (" (log scale)" if "y" in log_mode else ""),
        fontsize=12,
    )
    plt.grid(True, linestyle="--", alpha=0.6, which="both")
    plt.legend(fontsize=11)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def plot(
    file_path: str = "simulations/output.txt",
    bins: int = 20,
    window_size: float = 2.0,
    log_mode: str = "off",
    plot_type: str = "bar",
    probability: bool = False,
    save_dir: str = None,
):
    """
    file_path: path of the to load data from
    bins: number of bins used in the service time distribution graph
    window_size: size in seconds of the window of time that will
                 be considered to calculate the utilization
    save_dir: were to save the plot
    """
    points = load_points(file_path)
    queued_jobs = deg_queued_jobs_number(points)
    plot_times, utilizations, server_ids = calculate_plot_times_utilization(
        queued_jobs, window_size
    )

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    resp_name = f"{base_name}_response_time.png"
    util_name = f"{base_name}_utilization.png"
    
    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        resp_save = os.path.join(save_dir, resp_name)
        util_save = os.path.join(save_dir, util_name)
    else:
        resp_save = None
        util_save = None

    plot_response_time_distribution(
        {os.path.basename(file_path): points},
        bins,
        log_mode=log_mode,
        plot_type=plot_type,
        probability=probability,
        save_path=resp_save,
    )
    plot_utilizations_sliding_window(
        plot_times, utilizations, server_ids, window_size, save_path=util_save
    )


def plot_multiplier_response_time_sorted(
    files: List[str],
):
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
        plt.figure(figsize=(10, 5))
        plt.title(f"Response time (sorted) per Job size: load {load}", fontsize=14, fontweight="bold")


        for label, points in datasets.items():
            useful_points = [
                p
                for p in points
                if p.get("source") == "server" and p.get("event") == "end"
            ]

            data = [
                (p["multiplier"], p["resp_time"])
                for p in useful_points
            ]

            data.sort(key = lambda p: p[0])
            mult = [p[0] for p in data]
            resp = [p[1] for p in data]

            plt.plot(mult, resp, label=label)

        plt.xscale("log")
        plt.xlabel("Job size (log-scale)", fontsize=12)
        plt.ylabel("Response time (seconds)", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.6, which="both")
        plt.legend(fontsize=11)
        plt.show()
        

def plot_summary(
    files: List[str]
):
    data = {}

    for file in files:
        filename = os.path.basename(file).replace(".txt", "")
        parts = filename.split("-")
        dispatcher = parts[0] if len(parts) > 0 else "Unknown"
        load = parts[1] if len(parts) > 1 else "Unknown"

        summary = []
        with open(file, mode="r") as f:
            for line in f:
                point = json.loads(line)
                if point.get("source") == "server" and point.get("event") == "summary":
                    summary.append(point)

        if load not in data:
            data[load] = {}
        data[load][dispatcher] = summary


    for load, datasets in sorted(data.items()):
        plt.title(f"Utilization times with load {load}", fontsize=14, fontweight="bold")

        labels = datasets.keys()
        heights = [
            [p["processing"] for p in d]
            for d in datasets.values()
        ]
        heights = list(zip(*heights)) # swap
        maximum = max(max(i) for i in heights)

        heights = np.array(heights) / maximum

        colors = ['tab:blue', 'tab:orange', 'tab:green']
        bins = len(heights[0])
        bar_width = 0.25
        bin_centres = np.arange(bins)
        offsets = np.array([-1, 0, 1]) * bar_width
        
        for (i, color) in enumerate(colors):
            plt.bar(
                bin_centres + offsets[i],
                heights[i],
                width=bar_width,
                color=color,
                label=f"Server {i + 1}",
            )

        plt.xticks(
            bin_centres,
            labels=labels,
            rotation=45,
            ha="right"
        )
        plt.xlabel("Dispatcher", fontsize=12)
        plt.ylabel("Utilization", fontsize=12)
        plt.legend()

        plt.tight_layout()
        plt.show()


def plot_comparison(
    files: List[str],
    bins: int = 20,
    log_mode: str = "off",
    plot_type: str = "bar",
    probability: bool = False,
    save_dir: str = None,
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
        if save_dir is not None:
            os.makedirs(save_dir, exist_ok=True)
            resp_save = os.path.join(save_dir, f"comparison_load_{load}_response_time.png")
        else:
            resp_save = None

        plot_response_time_distribution(
            datasets,
            bins,
            title_suffix=f"Load: {load}",
            log_mode=log_mode,
            plot_type=plot_type,
            probability=probability,
            save_path=resp_save,
        )



PLOT_TYPE = "line" # bar or line
LOG_MODE = "x"     # off, x (response time, x axis), y (density, y axis), xy (both axis)
PROBABILITY = True # False for standard density (area=1), True for relative frequency (sum of heights=1)


if __name__ == "__main__":
    save_directory = None
    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 < len(sys.argv):
            save_directory = sys.argv[idx + 1]
            sys.argv.pop(idx + 1)
        else:
            save_directory = ""
        sys.argv.pop(idx)

    should_summary = "--summary" in sys.argv
    if should_summary:
        sys.argv.remove("--summary")

    if len(sys.argv) == 2 and os.path.isfile(
        sys.argv[1]
    ):  # plot for a single file (filename passed)
        plot(
            sys.argv[1], log_mode=LOG_MODE, plot_type=PLOT_TYPE, probability=PROBABILITY, save_dir=save_directory
        )

    elif len(sys.argv) == 1 and should_summary and os.path.isdir(
        "simulations/hedged"
    ):  # summary mode explicitly requested, plot everything
        sim_files = [
            os.path.join("simulations/hedged", f)
            for f in os.listdir("simulations/hedged")
            if f.endswith(".txt")
        ]

        if sim_files:
            plot_comparison(
                sim_files,
                log_mode=LOG_MODE,
                plot_type=PLOT_TYPE,
                probability=PROBABILITY,
                save_dir=save_directory,
            )

            plot_multiplier_response_time_sorted(sim_files)

            plot_summary(sim_files)
        else:
            print("No simulator .txt files found inside the 'simulations/' directory.")

    else:
        print(
            f"Usage:  To plot all files (summary): python3 {sys.argv[0]} --summary [--save <save_path>]\n"
            f"To plot single file:                 python3 {sys.argv[0]} <file_path> [--save <save_path>]\n\n"
            f"Examples:\n"
            f"    python3 {sys.argv[0]} --summary\n"
            f"    python3 {sys.argv[0]} simulations/Silly-0.2.txt  \n"
            f"    python3 {sys.argv[0]} simulations/Silly-0.2.txt --save export/"
        )
        sys.exit(1)