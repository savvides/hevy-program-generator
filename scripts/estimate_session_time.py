#!/usr/bin/env python3
"""Planning estimate for lifting time, including warmups and both sides.

Rep execution assumes 3 s/rep, with a 45 s minimum for heavy-lift handling.
Rest occurs between sets/rounds, not after the final set before station setup.
The ±20% planning range is a sensitivity allowance, NOT a calibrated prediction
interval. General warmup, cardio, queues and travel are excluded. The nominal
estimate is gated against the configured planning cap; actual duration can vary.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_routines as br  # noqa: E402
from program_loader import load_program  # noqa: E402

# Planning assumptions, not fitted coefficients.
CAP_MIN = 60.0              # default per-lift-session cap (overridden by program metadata)
WARMUP_SET = 75             # one warm-up ramp set incl. plate change + brief rest
EXEC_COMPOUND = 45          # one heavy compound work set: unrack, execute, rerack
SETUP_COMPOUND = 90         # walk to rack, load bar, set pins/box for a compound
SETUP_OTHER = 40            # grab dumbbells / set a bench / adjust a machine
SUPERSET_INTERNAL_REST = 40 # brief rest between lifts inside a superset round
REST_OVERRUN = 25           # per work set: rest creep past the timer + app logging
# --------------------------------------------------------------------------


def is_compound(ex: dict) -> bool:
    """Compound if explicitly flagged; otherwise infer from having warm-up sets."""
    if "compound" in ex:
        return bool(ex["compound"])
    return bool(ex.get("warmup_reps"))


def exec_seconds(ex: dict, spec: dict) -> int:
    sides = spec.get("sides", 1)
    if "duration_seconds" in spec:
        return int(spec["duration_seconds"] * sides)
    reps = spec.get("reps_max", spec["reps"])
    execution = int(reps * 3 * sides)
    return max(EXEC_COMPOUND, execution) if is_compound(ex) else execution


def setup_seconds(ex: dict) -> int:
    return SETUP_COMPOUND if is_compound(ex) else SETUP_OTHER


def _group_exercises(routine: dict) -> list[list[dict]]:
    """Order-preserving grouping: a run of CONSECUTIVE exercises sharing the same
    non-None `superset` id forms one group; everything else is its own group.
    A `superset` id that recurs after a break starts a fresh group — supersets
    are always defined consecutively, so non-adjacent reuse is not one superset."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_sid: int | None = None
    for ex in routine["exercises"]:
        sid = ex.get("superset")
        if sid is not None and sid == current_sid:
            current.append(ex)
            continue
        if current:
            groups.append(current)
        current = [ex]
        current_sid = sid
    if current:
        groups.append(current)
    return groups


def routine_seconds(routine: dict) -> int:
    total = 0
    for group in _group_exercises(routine):
        # Setup + warm-ups for every exercise in the group.
        for ex in group:
            total += setup_seconds(ex)
            wu_sets = ex.get("warmup_reps") or []
            total += len(wu_sets) * WARMUP_SET
            if any(s.get("sides") == 2 for s in br.parse_work_sets(ex)):
                total += sum(wu_sets) * 3  # additional side execution, not double rest
        if len(group) == 1:
            ex = group[0]
            work_sets = br.parse_work_sets(ex)
            for i, spec in enumerate(work_sets):
                total += exec_seconds(ex, spec) + REST_OVERRUN
                if i < len(work_sets) - 1:
                    total += ex.get("rest_seconds", 60)
        else:
            group_work_sets = [br.parse_work_sets(ex) for ex in group]
            rounds = max(len(ws) for ws in group_work_sets)
            group_rest = max(ex.get("rest_seconds", 60) for ex in group)
            for r in range(rounds):
                active = [(ex, ws[r]) for ex, ws in zip(group, group_work_sets) if r < len(ws)]
                total += sum(exec_seconds(ex, spec) for ex, spec in active)
                # Internal rest only happens when ≥2 lifts alternate in the round;
                # a trailing round with one lift left (mismatched set counts) has none.
                total += SUPERSET_INTERNAL_REST * (len(active) - 1)
                total += REST_OVERRUN
                if r < rounds - 1:
                    total += group_rest
    return total


def routine_time_range(routine: dict) -> tuple[float, float]:
    minutes = routine_seconds(routine) / 60
    return minutes * 0.8, minutes * 1.2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None, help="Path to training program python file")
    args = parser.parse_args(argv)

    prog = load_program(args.program)
    metadata = prog.get("PROGRAM_METADATA", {})
    cap_min = float(metadata.get("session_time_cap_minutes", CAP_MIN))
    routines = prog.get("ROUTINES", [])

    print(f"ESTIMATED SESSION TIME — {metadata.get('title', 'Active Program')}")
    print(f"Cap: {cap_min:.0f} minutes per session  (nominal planning estimate, not a guaranteed finish time)\n")
    failures: list[str] = []
    for routine in routines:
        mins = routine_seconds(routine) / 60.0
        title = routine.get("title") or routine.get("name", "Routine")
        if mins > cap_min:
            status = f"OVER ✗ (cap {cap_min:.0f})"
            failures.append(title)
        else:
            status = f"OK (cap {cap_min:.0f})"
        n_ex = len(routine["exercises"])
        n_work = sum(
            len(ex["work_sets"]) if isinstance(ex["work_sets"], list) else int(ex["work_sets"])
            for ex in routine["exercises"]
        )
        low, high = routine_time_range(routine)
        print(f"  {title[:46]:46s} {mins:5.1f} min  {n_ex} ex / {n_work} work sets  {status}; planning range {low:.0f}–{high:.0f} min")

    if failures:
        print(f"\nFAIL: sessions over {cap_min:.0f} min: {failures}")
        return 1
    print(f"\nPASS: every nominal estimate ≤ {cap_min:.0f} min.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
