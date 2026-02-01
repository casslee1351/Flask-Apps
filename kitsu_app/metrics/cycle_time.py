from typing import Iterable, Optional
from statistics import median


def median_cycle_time(runs: Iterable) -> Optional[float]:
    """
    Compute median cycle time from a collection of TimerRun objects.

    Args:
        runs: iterable of objects with a .duration attribute (seconds)

    Returns:
        Median cycle time in seconds, or None if no valid runs.
    """
    durations = [
        r.duration for r in runs
        if r.duration is not None
    ]

    if not durations:
        return None

    return median(durations)
