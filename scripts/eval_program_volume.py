#!/usr/bin/env python3
"""Program-correctness eval: weekly training volume + frequency per muscle group.

Derives both from the selected program and the cached Hevy exercise catalog
(data/exercise_templates.json), counting every resistance-training routine.
Catalog muscle assignments are approximate and require exercise-specific review.

Planning thresholds: 3–18 weighted sets and at least one weekly exposure.
These are repository screening defaults, not validated individual MEV/MRV values.
Secondary-muscle weighting is a bookkeeping heuristic, not measured stimulus.

Exits non-zero if any gated prime mover falls below MIN_SETS, exceeds MAX_SETS,
or fails MIN_FREQ.

Run: python3 scripts/eval_program_volume.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_routines as br  # noqa: E402
from program_loader import load_program  # noqa: E402

CACHE_PATH = br.CACHE_PATH
MIN_SETS = 3.0           # repository screening floor
MAX_SETS = 18.0          # repository review ceiling
MIN_FREQ = 1             # repository coverage floor

# Major prime movers held to the MIN_SETS floor and MAX_SETS ceiling.
GATED = {
    "chest", "lats", "upper_back", "quadriceps", "hamstrings", "glutes",
    "shoulders", "biceps", "triceps",
}
# Stabilisers / isometric workers / cardio-trained — reported, not gated.
UNGATED = {"abdominals", "lower_back", "forearms", "abductors", "adductors",
           "traps", "neck", "calves", "full_body", "other", "cardio"}


def _get_routines(program_path: Optional[str] = None) -> list[dict]:
    prog = load_program(program_path)
    return prog.get("ROUTINES", [])


def _lift_exercise_templates(program_path: Optional[str] = None):
    """Yield (template, n_work_sets) for every exercise in the LIFT sessions,
    resolving each name against the cached catalog. Raises if a name can't
    resolve (a live build would abort too)."""
    templates = json.loads(CACHE_PATH.read_text())
    by_title = {br.normalize(t.get("title", "")): t for t in templates}
    missing: list[str] = []
    pairs: list[tuple[dict, int]] = []
    routines = _get_routines(program_path)
    for routine in routines:
        for ex in routine["exercises"]:
            t = br.find_template(templates, ex["name"]) or by_title.get(
                br.normalize(ex["name"]))
            if not t:
                missing.append(ex["name"])
                continue
            n_sets = len(ex["work_sets"]) if isinstance(ex["work_sets"], list) else int(ex["work_sets"])
            pairs.append((t, n_sets))
    if missing:
        raise SystemExit(f"error: unresolved exercises (fix names): {missing}")
    return pairs


def compute_volume(program_path: Optional[str] = None) -> dict[str, float]:
    """Weighted weekly sets/muscle: primary 1.0 + secondary 0.5. Gated on this."""
    vol: dict[str, float] = defaultdict(float)
    for t, n_sets in _lift_exercise_templates(program_path):
        if t.get("primary_muscle_group"):
            vol[t["primary_muscle_group"]] += n_sets
        for sec in t.get("secondary_muscle_groups") or []:
            vol[sec] += 0.5 * n_sets
    return dict(vol)


def compute_direct(program_path: Optional[str] = None) -> dict[str, float]:
    """Weekly sets assigned to the primary muscle by the exercise catalog."""
    direct: dict[str, float] = defaultdict(float)
    for t, n_sets in _lift_exercise_templates(program_path):
        if t.get("primary_muscle_group"):
            direct[t["primary_muscle_group"]] += n_sets
    return dict(direct)


def compute_frequency(program_path: Optional[str] = None) -> dict[str, int]:
    """Per muscle, how many LIFT sessions train it (as primary OR secondary)."""
    templates = json.loads(CACHE_PATH.read_text())
    by_title = {br.normalize(t.get("title", "")): t for t in templates}

    freq: dict[str, int] = defaultdict(int)
    missing: list[str] = []
    routines = _get_routines(program_path)
    for routine in routines:
        muscles: set[str] = set()
        for ex in routine["exercises"]:
            t = br.find_template(templates, ex["name"]) or by_title.get(
                br.normalize(ex["name"]))
            if not t:
                missing.append(ex["name"])
                continue
            if t.get("primary_muscle_group"):
                muscles.add(t["primary_muscle_group"])
            muscles.update(t.get("secondary_muscle_groups") or [])
        for m in muscles:
            freq[m] += 1
    if missing:
        raise SystemExit(f"error: unresolved exercises (fix names): {missing}")
    return dict(freq)


def classify_tier(weighted_sets: float) -> str:
    """Describe weighted-set bands without predicting individual adaptation."""
    if weighted_sets < MIN_SETS:
        return "BELOW POLICY (<3) ✗"
    elif weighted_sets <= 6.0:
        return "Within policy: 3–6 weighted sets"
    elif weighted_sets <= 10.0:
        return "Within policy: >6–10 weighted sets"
    elif weighted_sets <= MAX_SETS:
        return "Within policy: >10–18 weighted sets"
    else:
        return f"ABOVE POLICY (>{MAX_SETS:.0f}) ✗"


def compute_balance_ratios(vol: dict[str, float]) -> dict[str, float]:
    """Compute anterior/posterior (push/pull) and knee/hip balance ratios."""
    push_vol = vol.get("chest", 0.0) + vol.get("shoulders", 0.0) + vol.get("triceps", 0.0)
    pull_vol = vol.get("lats", 0.0) + vol.get("upper_back", 0.0) + vol.get("biceps", 0.0)
    knee_vol = vol.get("quadriceps", 0.0)
    hip_vol = vol.get("hamstrings", 0.0) + vol.get("glutes", 0.0)

    push_pull_ratio = push_vol / pull_vol if pull_vol > 0 else 0.0
    knee_hip_ratio = knee_vol / hip_vol if hip_vol > 0 else 0.0
    return {
        "push_vol": push_vol,
        "pull_vol": pull_vol,
        "push_pull_ratio": push_pull_ratio,
        "knee_vol": knee_vol,
        "hip_vol": hip_vol,
        "knee_hip_ratio": knee_hip_ratio,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None, help="Path to training program python file")
    args = parser.parse_args(argv)

    prog = load_program(args.program)
    metadata = prog.get("PROGRAM_METADATA", {})
    routines = prog.get("ROUTINES", [])

    vol = compute_volume(args.program)
    direct = compute_direct(args.program)
    freq = compute_frequency(args.program)
    ratios = compute_balance_ratios(vol)

    print("=" * 80)
    print("  PLANNED VOLUME & FREQUENCY POLICY CHECK")
    print(f"  Program: {metadata.get('title', 'Active Program')}")
    print(f"  Primary goal: {metadata.get('primary_goal', 'unknown')}")
    print(f"  Age (reported years): {metadata.get('age_years', 'unknown')}")
    print(f"  Sex (reported): {metadata.get('sex', 'unknown')}")
    print("  Reported context is not suitability validation; it does not change numeric gates.")
    print("  Hypertrophy research guidance is goal-specific, not a universal minimum for aerobic support or unknown goals.")
    print("  Thresholds are coaching policies; see docs/evidence_base.md")
    print("=" * 80)
    print(f"  Floor: ≥{MIN_SETS:.0f} weighted sets/wk  |  Ceiling: ≤{MAX_SETS:.0f} weighted sets/wk  |  Freq: ≥{MIN_FREQ}×/wk\n")
    print(f"  {'Muscle':14s} {'Direct':>6s} {'Weighted':>9s}  {'Freq':>4s}  {'Weighted-set band':35s}")
    print("  " + "-" * 75)

    failures: list[str] = []
    excessive: list[str] = []
    low_freq: list[str] = []

    for muscle in sorted(GATED | set(vol), key=lambda m: -vol.get(m, 0.0)):
        v = vol.get(muscle, 0.0)
        d = direct.get(muscle, 0.0)
        f = freq.get(muscle, 0)
        gated = muscle in GATED
        tier = classify_tier(v)

        if gated and v < MIN_SETS:
            failures.append(muscle)
        if gated and v > MAX_SETS:
            excessive.append(muscle)
        if gated and f < MIN_FREQ:
            low_freq.append(muscle)

        status = tier if gated else "— (stabiliser / ungated)"
        print(f"  {muscle:14s} {d:6.1f} {v:9.1f}  {f:>3d}×  {status}")

    total = sum(
        len(ex["work_sets"]) if isinstance(ex["work_sets"], list) else int(ex["work_sets"])
        for r in routines for ex in r["exercises"]
    )

    print("\n  STRUCTURAL BALANCE RATIOS (advisory only — not gated; no anchor in docs/evidence_base.md):")
    print(f"  - Push vs. Pull Volume: {ratios['push_vol']:.1f} sets vs. {ratios['pull_vol']:.1f} sets "
          f"(Ratio: {ratios['push_pull_ratio']:.2f} — target: 0.8–1.2)")
    print(f"  - Knee vs. Hip Volume:  {ratios['knee_vol']:.1f} sets vs. {ratios['hip_vol']:.1f} sets "
          f"(Ratio: {ratios['knee_hip_ratio']:.2f} — target: 0.8–1.2)")

    print(f"\n  Total Lift Working Sets / Week: {total}")
    print("=" * 80)

    if failures or excessive or low_freq:
        if failures:
            print(f"\nFAIL: Prime movers below configured floor (≥{MIN_SETS:.0f} sets/wk): {failures}")
        if excessive:
            print(f"\nFAIL: Prime movers exceeding configured ceiling (≤{MAX_SETS:.0f} sets/wk): {excessive}")
        if low_freq:
            print(f"\nFAIL: Prime movers trained < {MIN_FREQ}×/week: {low_freq}")
        return 1

    print(f"\nPASS: All gated prime movers satisfy configured volume ({MIN_SETS:.0f}–{MAX_SETS:.0f} sets/wk) "
          f"and frequency (≥{MIN_FREQ}×/wk) bounds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
