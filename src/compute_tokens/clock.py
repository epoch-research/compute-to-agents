"""Audited union clock; integer microseconds."""
from .intervals import *
def measured_clock(windows, protected, human, cap):
    """Union windows; remove human-only time; cap each remaining uncovered segment.

    Protected machine/model work wins over a simultaneous human wait.
    Uncovered segments are not identified as human: capping them is a sensitivity.
    """
    windows = merge_intervals(windows)
    protected = intersect_intervals(protected, windows)
    human_only = subtract_intervals(intersect_intervals(human, windows), protected)
    uncovered = subtract_intervals(windows, [*protected, *human_only])
    return (duration_us(protected) + sum(min(b-a, cap) for a,b in uncovered),
            duration_us(human_only), duration_us(uncovered))
