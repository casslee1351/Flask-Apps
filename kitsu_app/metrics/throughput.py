from datetime import datetime

def throughput_per_day(runs):
    """
    Compute throughput as runs per day.
    
    runs: list of dicts with 'start_time' and 'end_time'
    Returns: float (runs per day) or None
    """

    if not runs:
        return None

    start_times = []
    end_times = []

    for r in runs:
        if r["start_time"] and r["end_time"]:
            start_times.append(datetime.fromisoformat(r["start_time"]))
            end_times.append(datetime.fromisoformat(r["end_time"]))

    if not start_times or not end_times:
        return None

    time_window_seconds = (max(end_times) - min(start_times)).total_seconds()

    if time_window_seconds <= 0:
        return None

    days = time_window_seconds / 86400  # 60 * 60 * 24 to get runs per day instead of runs per hour

    return len(runs) / days
