"""Strict set prescriptions shared by validation, Hevy export and timing."""
from __future__ import annotations

import re


def parse_work_sets(ex: dict) -> list[dict]:
    """Ranges use the lower rep target in Hevy; timed ranges use the upper duration.

    A per-side set includes both sides, recorded once. Logged set dictionaries are
    accepted for timing comparisons; program files use a positive integer count.
    """
    count = ex.get("work_sets")
    if isinstance(count, list):
        return count
    if type(count) is not int or count <= 0:
        raise ValueError("work_sets must be a positive integer")
    if "duration_seconds" in ex:
        value = ex["duration_seconds"]
        if type(value) is not int or value <= 0:
            raise ValueError("duration_seconds must be a positive integer")
        spec = {"duration_seconds": value}
    else:
        match = re.fullmatch(r"(\d+)(?:-(\d+))?(s)?( per side)?", str(ex.get("reps", "")).strip())
        if not match:
            raise ValueError(f"Unsupported reps prescription: {ex.get('reps')!r}")
        low = int(match[1])
        high = int(match[2] or low)
        if low <= 0 or high < low:
            raise ValueError("Rep/duration range must be positive and ascending")
        if match[3]:
            spec = {"duration_seconds": high}
        elif match[2]:
            spec = {"reps_min": low, "reps_max": high, "reps": low}
        else:
            spec = {"reps": low}
        if match[4]:
            spec["sides"] = 2
    return [dict(spec) for _ in range(count)]
