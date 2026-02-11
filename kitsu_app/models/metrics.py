import numpy as np

def aggregate_cycle_times(runs, group_key):
    """
    runs: list of TimerRun
    group_key: 'process', 'machine', or 'operator'
    """
    grouped = {}

    for r in runs:
        key = getattr(r, group_key)
        grouped.setdefault(key, []).append(r.cycle_time)

    results = []

    for key, times in grouped.items():
        times = np.array(times)

        median = float(np.median(times))
        std = float(np.std(times, ddof=1)) if len(times) > 1 else 0.0
        cv = float(std / median) if median > 0 else 0.0

        results.append({
            group_key: key,
            "runs": len(times),
            "median_cycle_time": round(median, 2),
            "std_cycle_time": round(std, 2),
            "cv": round(cv, 3)
        })

    return results
