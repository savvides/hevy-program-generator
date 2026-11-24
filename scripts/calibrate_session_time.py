#!/usr/bin/env python3
"""Compare logged time against an explicitly selected program version.

Only exact exercise-order and working-set-count matches are included. Prescribed
rest and lift role come from that program, never from whether warmups were logged.
Logged warmups and superset groups are retained. This estimates time for logged
work, not necessarily all work performed; rest adherence and timer boundaries are
unknown. Matching a current program is not proof it was the historical prescription.
No automatic coefficient fitting is performed. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class SessionRow(TypedDict):
    """One logged session compared against the time model."""

    date: str
    title: str
    actual: float
    pred: float
    err: float
    n_ex: int
    n_sets: int


def resolve_workouts_dir(cli_dir: str | None = None) -> Path:
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    env_dir = os.environ.get("HEVY_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return REPO_ROOT / "data" / "workouts"


sys.path.insert(0, str(Path(__file__).resolve().parent))
import estimate_session_time as est  # noqa: E402
import build_routines as br  # noqa: E402
from program_loader import load_program  # noqa: E402


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def as_routine(workout: dict, prescribed: dict, templates: list[dict]) -> dict:
    """Reject mismatches; use prescribed rest/role and logged execution/structure."""
    logged = workout.get("exercises", [])
    expected = prescribed["exercises"]
    ids = [br.find_template(templates, ex["name"]) for ex in expected]
    if len(logged) != len(expected) or any(t is None or str(e.get("exercise_template_id")) != str(t["id"])
                                          for e, t in zip(logged, ids)):
        raise ValueError("Exercise order/identity does not match selected program")
    exercises = []
    for actual, planned in zip(logged, expected):
        warmups = [s for s in actual.get("sets", []) if s.get("type") == "warmup"]
        work = [s for s in actual.get("sets", []) if s.get("type", "normal") != "warmup"]
        if len(work) != planned["work_sets"]:
            raise ValueError("Working-set count differs from selected program")
        sides = br.parse_work_sets(planned)[0].get("sides", 1)
        specs = []
        for actual_set in work:
            if actual_set.get("duration_seconds"):
                key, value = "duration_seconds", actual_set.get("duration_seconds")
            elif actual_set.get("distance_meters"):
                # Approximate 1 m ~ 1 s carry pacing when logged as distance
                key, value = "duration_seconds", actual_set.get("distance_meters")
            else:
                key, value = "reps", actual_set.get("reps")
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError("Logged set has no usable execution quantity")
            specs.append({key: value, "sides": sides})
        warmup_reps = [s.get("reps") for s in warmups]
        if any(type(reps) is not int or reps <= 0 for reps in warmup_reps):
            raise ValueError("Logged warmup has no usable rep count")
        exercises.append({**planned, "warmup_reps": warmup_reps,
                          "work_sets": specs, "superset": actual.get("superset_id")})
    return {"title": workout.get("title", "?"), "exercises": exercises}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--program", required=True, help="Exact prescribed program version for these logs")
    ap.add_argument("--since", default=None, help="only sessions on/after YYYY-MM-DD")
    ap.add_argument("--min-sets", type=int, default=8,
                    help="skip tiny sessions below this work-set count (default 8)")
    ap.add_argument("--data-dir", default=None,
                    help="Directory containing workout logs (or set HEVY_DATA_DIR)")
    args = ap.parse_args(argv)

    program = load_program(args.program)
    templates = json.loads(br.CACHE_PATH.read_text())
    print(f"Reference: {program['_file_path']} version {program['PROGRAM_METADATA'].get('version', 'unspecified')}")
    print("Assumes that version and per-side logging convention applied to matching sessions; verify historical context.")
    workouts_dir = resolve_workouts_dir(args.data_dir)
    unmatched = 0
    rows: list[SessionRow] = []
    for f in sorted(workouts_dir.glob("*.json")):
        try:
            w = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(w, dict) or not w.get("start_time") or not w.get("end_time"):
            continue
        start, end = parse_dt(w["start_time"]), parse_dt(w["end_time"])
        if args.since and start.date().isoformat() < args.since:
            continue
        actual_min = (end - start).total_seconds() / 60.0
        if actual_min <= 0 or actual_min > 180:
            continue  # forgot to stop the timer / clock glitch
        routine = None
        for prescribed in program["ROUTINES"]:
            try:
                routine = as_routine(w, prescribed, templates)
                break
            except ValueError:
                continue
        if routine is None:
            unmatched += 1
            continue
        n_work = sum(len(ex["work_sets"]) for ex in routine["exercises"])
        if n_work < args.min_sets:
            continue
        pred_min = est.routine_seconds(routine) / 60.0
        rows.append({
            "date": start.date().isoformat(),
            "title": (w.get("title") or "?")[:34],
            "actual": actual_min,
            "pred": pred_min,
            "err": actual_min - pred_min,
            "n_ex": len(routine["exercises"]),
            "n_sets": n_work,
        })

    print(f"Skipped {unmatched} sessions with mismatched exercises or set counts.")
    if not rows:
        print(f"error: no usable sessions found in {workouts_dir}", file=sys.stderr)
        return 1

    hdr = (f"{'date':10s}  {'session':34s}  {'sets':>4s}  {'actual':>7s}  "
           f"{'model':>7s}  {'error':>7s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['date']:10s}  {r['title']:34s}  {r['n_sets']:4d}  "
              f"{r['actual']:6.1f}m  {r['pred']:6.1f}m  {r['err']:+6.1f}m")

    errs = [r["err"] for r in rows]
    actuals = [r["actual"] for r in rows]
    print(f"\nsessions analyzed:     {len(rows)}")
    print(f"actual   mean/median:  {statistics.mean(actuals):.1f} / "
          f"{statistics.median(actuals):.1f} min")
    print(f"model    mean/median:  {statistics.mean([r['pred'] for r in rows]):.1f} / "
          f"{statistics.median([r['pred'] for r in rows]):.1f} min")
    print(f"ERROR    mean/median:  {statistics.mean(errs):+.1f} / "
          f"{statistics.median(errs):+.1f} min  "
          f"(positive = model UNDER-predicts, session runs longer)")
    over_60 = sum(1 for r in rows if r["actual"] > 60)
    over_65 = sum(1 for r in rows if r["actual"] > 65)
    print(f"actual sessions >60 min: {over_60}/{len(rows)} "
          f"({100 * over_60 / len(rows):.0f}%)   >65 min: {over_65}/{len(rows)} "
          f"({100 * over_65 / len(rows):.0f}%)")
    print("Differences include unknown rest adherence, unlogged work and timer boundaries; these are not fitted calibration coefficients.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
