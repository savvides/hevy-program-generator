#!/usr/bin/env python3
"""Analyze fetched Hevy history (data/workouts/*.json) for program design.

Deterministic report, no LLM judgment:
  - timeline: first/last workout, total sessions, layoff length vs today
  - weekly session frequency over the last 26 weeks
  - per-exercise summary: sessions, last performed, best working set
    (max weight x reps), best e1RM (Epley), most recent working top set
  - adherence to the current program's lifts (names from build_routines.ROUTINES)

Usage: python3 scripts/analyze_history.py [--since YYYY-MM-DD] [--top N]
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def resolve_workouts_dir(cli_dir: str | None = None) -> Path:
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    env_dir = os.environ.get("HEVY_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return REPO_ROOT / "data" / "workouts"


KG_TO_LB = 2.2046226218


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def epley(weight: float, reps: int) -> float:
    if reps <= 0:
        return 0.0
    if reps == 1:
        return weight
    return weight * (1 + reps / 30.0)


def load_workouts(workouts_dir: Path) -> list[dict]:
    files = sorted(workouts_dir.glob("*.json"))
    out = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            if isinstance(data, dict) and data.get("start_time"):
                out.append(data)
        except Exception:
            print(f"warning: skipping unparseable {f.name}", file=sys.stderr)
    out.sort(key=lambda w: w.get("start_time") or "")
    return out


def iso_date(s: str) -> str:
    try:
        datetime.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {s!r}, expected YYYY-MM-DD") from None
    return s


def positive_int(s: str) -> int:
    n = int(s)
    if n < 1:
        raise argparse.ArgumentTypeError(f"{s!r} is not a positive integer")
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", type=iso_date, default=None,
                    help="Only analyze workouts on/after this date (YYYY-MM-DD)")
    ap.add_argument("--top", type=positive_int, default=40,
                    help="Show the N most-recently-performed exercises (default 40)")
    ap.add_argument("--data-dir", default=None,
                    help="Directory containing workout logs (or set HEVY_DATA_DIR)")
    args = ap.parse_args(argv)

    workouts_dir = resolve_workouts_dir(args.data_dir)
    workouts = load_workouts(workouts_dir)
    if not workouts:
        print(f"error: no workouts in {workouts_dir} — run fetch_workouts.py first",
              file=sys.stderr)
        return 1

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        workouts = [w for w in workouts if parse_dt(w["start_time"]) >= since]
        if not workouts:
            print(f"error: no workouts since {args.since}", file=sys.stderr)
            return 1

    first_dt = parse_dt(workouts[0]["start_time"])
    last_dt = parse_dt(workouts[-1]["start_time"])
    today = datetime.now(timezone.utc)
    layoff_days = (today - last_dt).days

    print("=== Timeline ===")
    print(f"sessions:      {len(workouts)}")
    print(f"first workout: {first_dt.date()}")
    print(f"last workout:  {last_dt.date()}  ({layoff_days} days ago)")

    # Weekly frequency, last 26 ISO weeks that contain any workout
    print("\n=== Weekly session count (last 26 weeks w/ activity, most recent last) ===")
    by_week: dict[str, int] = defaultdict(int)
    for w in workouts:
        d = parse_dt(w["start_time"]).date()
        iso = d.isocalendar()
        by_week[f"{iso.year}-W{iso.week:02d}"] += 1
    weeks = sorted(by_week)[-26:]
    for wk in weeks:
        print(f"  {wk}: {'#' * by_week[wk]} ({by_week[wk]})")

    # Per-exercise stats
    ex: dict[str, dict] = {}
    for w in workouts:
        w_dt = parse_dt(w["start_time"])
        for e in w.get("exercises") or []:
            title = e.get("title") or "?"
            rec = ex.setdefault(title, {
                "sessions": set(), "last": None, "best_set": None,
                "best_e1rm": 0.0, "best_e1rm_set": None, "last_top_set": None,
            })
            rec["sessions"].add(w["id"])
            work_sets = [s for s in e.get("sets") or []
                         if (s.get("type") or "normal") != "warmup"]
            if not work_sets:
                continue
            if rec["last"] is None or w_dt > rec["last"]:
                rec["last"] = w_dt
                top = max(work_sets,
                          key=lambda s: ((s.get("weight_kg") or 0),
                                         (s.get("reps") or 0),
                                         (s.get("distance_meters") or 0),
                                         (s.get("duration_seconds") or 0)))
                rec["last_top_set"] = top
            for s in work_sets:
                wt = s.get("weight_kg") or 0
                reps = s.get("reps") or 0
                dist = s.get("distance_meters") or 0
                dur = s.get("duration_seconds") or 0
                key = (wt, reps, dist, dur)
                if rec["best_set"] is None or key > (
                        rec["best_set"].get("weight_kg") or 0,
                        rec["best_set"].get("reps") or 0,
                        rec["best_set"].get("distance_meters") or 0,
                        rec["best_set"].get("duration_seconds") or 0):
                    rec["best_set"] = s
                e1 = epley(wt, reps)
                if e1 > rec["best_e1rm"]:
                    rec["best_e1rm"] = e1
                    rec["best_e1rm_set"] = s

    def fmt_set(s: dict | None) -> str:
        if not s:
            return "-"
        wt = s.get("weight_kg")
        reps = s.get("reps")
        dur = s.get("duration_seconds")
        dist = s.get("distance_meters")
        if wt is not None and reps:
            return f"{wt:.1f} kg ({wt * KG_TO_LB:.0f} lb) x {reps}"
        if wt is not None and dist:
            return f"{wt:.1f} kg ({wt * KG_TO_LB:.0f} lb) x {dist:g}m"
        if wt is not None and dur:
            return f"{wt:.1f} kg ({wt * KG_TO_LB:.0f} lb) x {dur}s"
        if reps:
            return f"bw x {reps}"
        if dur:
            return f"{dur}s"
        if dist:
            return f"{dist:g}m"
        return "-"

    print(f"\n=== Exercises ({args.top} most recently performed) ===")
    rows = sorted(ex.items(), key=lambda kv: kv[1]["last"] or first_dt, reverse=True)
    hdr = (f"{'exercise':38s} {'n':>3s}  {'last':10s}  "
           f"{'last top set':26s}  {'best set':26s}  {'best e1RM':>12s}")
    print(hdr)
    print("-" * len(hdr))
    for title, rec in rows[:args.top]:
        n = len(rec["sessions"])
        last = rec["last"].date().isoformat() if rec["last"] else "-"
        e1 = rec["best_e1rm"]
        e1s = f"{e1:.0f} kg/{e1 * KG_TO_LB:.0f} lb" if e1 > 0 else "-"
        print(f"{title[:38]:38s} {n:3d}  {last:10s}  "
              f"{fmt_set(rec['last_top_set']):26s}  {fmt_set(rec['best_set']):26s}  {e1s:>12s}")

    # Adherence to current program lifts
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import build_routines as br
        names = {e["name"] for r in br.ROUTINES for e in r["exercises"]}
        why = "the active program has no routines"
    except Exception as exc:
        names, why = set(), f"could not load the active program ({type(exc).__name__}: {exc})"
    if not names:
        print(f"warning: current-program coverage section skipped: {why}", file=sys.stderr)
    else:
        print("\n=== Current-program lifts: history coverage ===")
        for name in sorted(names):
            # exact-title match against history (Hevy titles), else best fuzzy note
            hit = ex.get(name)
            if hit is None:
                norm = br.normalize(name)
                for t, rec in ex.items():
                    if br.normalize(t) == norm:
                        hit = rec
                        break
            if hit:
                last = hit["last"].date().isoformat() if hit["last"] else "-"
                print(f"  {name[:40]:40s} n={len(hit['sessions']):3d}  last={last}  "
                      f"last top={fmt_set(hit['last_top_set'])}")
            else:
                print(f"  {name[:40]:40s} " + (f"not logged since {args.since}" if since else "NEVER LOGGED"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
