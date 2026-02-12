from collections import defaultdict

def detect_process_bottleneck(runs):
    """
    Detect bottleneck at the process level.
    Bottleneck = process with highest average cycle time.
    """

    if not runs:
        return None

    grouped = defaultdict(list)

    for r in runs:
        grouped[r.process].append(r.duration)

    process_averages = {
        process: sum(durations) / len(durations)
        for process, durations in grouped.items()
    }

    # Highest average cycle time = bottleneck
    bottleneck_process = max(process_averages, key=process_averages.get)

    return {
        "process": bottleneck_process,
        "avg_cycle_time": process_averages[bottleneck_process]
    }
