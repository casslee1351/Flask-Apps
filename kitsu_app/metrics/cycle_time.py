from typing import Iterable, Optional
from statistics import median, mean, stdev


def _durations(runs: Iterable) -> list[float]:
    """Extract valid durations from runs."""
    return [
        r.duration for r in runs
        if r.duration is not None
    ]


def median_cycle_time(runs: Iterable) -> Optional[float]:
    durations = _durations(runs)
    if not durations:
        return None
    return median(durations)


def std_cycle_time(runs: Iterable) -> Optional[float]:
    """
    Sample standard deviation of cycle time.
    Requires at least 2 runs.
    """
    durations = _durations(runs)
    if len(durations) < 2:
        return None
    return stdev(durations)


def coefficient_of_variation(runs: Iterable) -> Optional[float]:
    """
    CV = std / mean
    Returns 0 if undefined.
    """
    durations = _durations(runs)
    if len(durations) < 2:
        return 0

    avg = mean(durations)
    if avg == 0:
        return 0
    
    return stdev(durations) / avg
