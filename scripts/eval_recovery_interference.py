#!/usr/bin/env python3
"""Check configured recovery policies and report planned cardio dose.

48-hour spacing, RPE 8 and a 25% interval-work ceiling are conservative repository
policies, not universal thresholds established by Schumann, Polito or Seiler.
Weekday-only schedules assume equal start times; actual hours remain unverified.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from program_loader import load_program  # noqa: E402

# Configurable scheduling policy; start-to-start hours, not measured recovery.
MIN_LOWER_TO_VO2_HOURS = 48.0
MAX_VO2_RATIO = 0.25  # repository planning ceiling, not a physiological limit
AEROBIC_PRIMARY_GOAL = "vo2max"
MAX_COMPOUND_RPE = 8.0

DAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

LOWER_MUSCLES = {"quads", "quadriceps", "hamstrings", "glutes", "calves", "legs", "adductors", "abductors"}
LOWER_NAME_KEYWORDS = ("squat", "deadlift", "step up", "step-up", "split squat", "lunge", "leg press", "calf")


def _is_aerobic_primary(goal: str) -> bool:
    """primary_goal is free text: 'VO2 max', 'VO2Max' and 'vo2_max' name the same goal."""
    return re.sub(r"[\s_-]+", "", goal.lower()) == AEROBIC_PRIMARY_GOAL


def _parse_day_idx(day_str: str) -> Optional[int]:
    clean = day_str.strip().lower()
    for token in clean.replace("—", " ").replace("-", " ").split():
        token_clean = "".join(c for c in token if c.isalpha())
        if token_clean in DAY_MAP:
            return DAY_MAP[token_clean]
    return None


def is_heavy_lower_routine(routine: dict) -> bool:
    for ex in routine.get("exercises", []):
        if not ex.get("compound", False):
            continue
        muscles = set(m.lower() for m in ex.get("muscle_groups", []))
        if muscles & LOWER_MUSCLES:
            return True
        name_low = ex.get("name", "").lower()
        if any(kw in name_low for kw in LOWER_NAME_KEYWORDS):
            return True
    return False


def check_recovery_spacing(
    routines: list[dict], cardio: list[dict], min_hours: float = MIN_LOWER_TO_VO2_HOURS,
) -> tuple[list[str], list[str]]:
    """Weekly start-to-start spacing; absent times are explicitly provisional."""
    violations: list[str] = []
    log_lines: list[str] = []

    def entries(items: list[dict], day_key: str) -> list[tuple[float, str, bool]]:
        result = []
        for item in items:
            day = item.get(day_key, "")
            idx = _parse_day_idx(day)
            if idx is None:
                violations.append(f"Unknown weekday: {day!r}")
                continue
            clock = item.get("start_time")
            if clock is None:
                hour = 0.0
                log_lines.append(f"  - {day}: start time missing; same-clock assumption only (actual hours unverified).")
            else:
                h, m = str(clock).split(":")
                hour = int(h) + int(m) / 60
            result.append((idx * 24 + hour, item.get("name", day), clock is not None))
        return result

    lower = entries([r for r in routines if is_heavy_lower_routine(r)], "day_key")
    intervals = entries([c for c in cardio if any(t in c.get("type", "").lower() for t in ("vo2", "hiit"))], "day")

    def compare(first: tuple[float, str, bool], second: tuple[float, str, bool], threshold: float) -> None:
        if first[2] and second[2]:
            gap = (second[0] - first[0]) % 168
        else:
            gap = ((second[0] // 24 - first[0] // 24) % 7) * 24
        log_lines.append(f"  - {first[1]} → {second[1]}: {gap:g}h (configured ≥{threshold:g}h)")
        if gap < threshold:
            violations.append(f"Scheduling policy: {first[1]} → {second[1]} is {gap:g}h, below configured {threshold:g}h.")

    for lift in lower:
        for interval in intervals:
            compare(lift, interval, min_hours)
            compare(interval, lift, min_hours)
    lower.sort()
    if len(lower) > 1:
        for i, lift in enumerate(lower):
            compare(lift, lower[(i + 1) % len(lower)], min_hours)
    return violations, log_lines


def cardio_duration_min(session: dict) -> float:
    """Session duration, accepting either spelling of the key."""
    return float(session.get("duration_minutes", session.get("duration_min", 0)))


def interval_minutes(session: dict) -> float:
    """Prescribed interval-work minutes in one cardio session.

    An explicit interval_work_min wins; otherwise the named protocols carry their own dose and
    unknown protocols require an explicit dose. Non-interval sessions contribute none.
    """
    stype = session.get("type", "").lower()
    if "vo2" not in stype and "hiit" not in stype:
        return 0.0
    if "interval_work_min" in session:
        return float(session["interval_work_min"])
    # Whole-token match: "14x4" or "5x30s" must not earn the 4x4 / 5x3 dose.
    if re.search(r"(?<!\d)4x4(?!\d)", stype):
        return 16.0
    if re.search(r"(?<!\d)5x3(?!\d)", stype):
        return 15.0
    raise ValueError("Unknown interval protocol requires interval_work_min")


def check_cardio_distribution(
    cardio: list[dict], primary_goal: str = ""
) -> tuple[float, float, list[str]]:
    """Report explicit easy and interval-work fractions of total scheduled time.

    Interval recoveries, warmup and cooldown remain unclassified. A protocol's
    work minutes are not measured time above a physiological intensity threshold.
    """
    violations: list[str] = []
    total = sum(cardio_duration_min(c) for c in cardio)
    if total <= 0:
        return 0.0, 0.0, ["No cardio duration scheduled."] if _is_aerobic_primary(primary_goal) else []
    easy = work = 0.0
    for session in cardio:
        stype = session.get("type", "").lower()
        if stype in ("zone 2", "zone2", "z2"):
            easy += cardio_duration_min(session)
        elif "vo2" in stype or "hiit" in stype:
            try:
                dose = interval_minutes(session)
                if dose <= 0 or dose > cardio_duration_min(session):
                    violations.append("Interval work must be positive and cannot exceed session duration")
                else:
                    work += dose
            except ValueError as exc:
                violations.append(str(exc))
        else:
            violations.append(f"Unclassified cardio intensity: {session.get('type')!r}; not counted as easy")
    if work / total > MAX_VO2_RATIO:
        violations.append(f"Interval-work fraction exceeds maximum configured {MAX_VO2_RATIO:.0%}; review the schedule (coaching policy).")
    if _is_aerobic_primary(primary_goal) and work == 0:
        violations.append("VO2-primary schedule has no interval work; review goal coverage.")
    return easy / total, work / total, violations


def check_compound_rpe_bounds(routines: list[dict]) -> list[str]:
    """Verify that all compound multi-joint movements enforce submaximal RPE <= 8.0 (repository policy)."""
    violations: list[str] = []
    for routine in routines:
        r_title = routine.get("name") or routine.get("title", "Routine")
        for ex in routine.get("exercises", []):
            if ex.get("compound", False):
                rpe = ex.get("rpe")
                if rpe is not None and float(rpe) > MAX_COMPOUND_RPE:
                    violations.append(
                        f"Proximity to failure violation: Compound lift '{ex['name']}' prescribes "
                        f"RPE {rpe} in routine '{r_title}'. Must be capped at RPE {MAX_COMPOUND_RPE:.0f} (repository policy)."
                    )
                notes = (ex.get("notes") or "").lower()
                if "failure" in notes and "non-failure" not in notes and "without failure" not in notes and "to technical failure" not in notes:
                    violations.append(
                        f"Proximity to failure violation: Compound lift '{ex['name']}' prescribes "
                        f"failure in routine '{r_title}'. Must be capped at RPE 8 (repository policy)."
                    )
    return violations


def check_cardio_modality(cardio: list[dict]) -> list[str]:
    """Check the repository cycling preference; other modalities are not inherently unsafe."""
    violations: list[str] = []
    for session in cardio:
        modality = session.get("modality", "")
        if modality:
            mod_low = modality.lower()
            if "cycling" not in mod_low and "bike" not in mod_low and "cycle" not in mod_low:
                day = session.get("day", "Cardio")
                violations.append(
                    f"Modality violation on {day}: '{modality}'. "
                    "This repository currently selects cycling; review modality preference before changing it."
                )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None, help="Path to training program python file")
    parser.add_argument(
        "--check",
        choices=["all", "spacing", "rpe"],
        default="all",
        help="Evaluation check subset: 'spacing' (temporal & cardio), 'rpe' (compound failure ceiling), or 'all' (default)",
    )
    args = parser.parse_args(argv)

    prog = load_program(args.program)
    metadata = prog.get("PROGRAM_METADATA", {})
    routines = prog.get("ROUTINES", [])
    cardio = prog.get("CARDIO_SCHEDULE", [])

    print("=" * 80)
    print("  CONCURRENT TRAINING RECOVERY & INTERFERENCE EVALUATION")
    print(f"  Program: {metadata.get('title', 'Active Program')}")
    print("  Coaching policies and limitations: docs/evidence_base.md")
    print("=" * 80)

    violations: list[str] = []

    if args.check in ("all", "spacing"):
        # 1. Spacing check
        spacing_violations, spacing_logs = check_recovery_spacing(routines, cardio, float(metadata.get("min_recovery_buffer_hours", 48)))
        print("\n1. TEMPORAL RECOVERY & INTERFERENCE SPACING:")
        for line in spacing_logs:
            print(line)
        if not spacing_logs:
            print("  - No conflicting lower-body / VO2 Max concurrent sessions scheduled.")

        # 2. Cardio ratio check
        z2_ratio, vo2_ratio, cardio_violations = check_cardio_distribution(
            cardio, str(metadata.get("primary_goal", ""))
        )
        print("\n2. PLANNED CARDIO DOSE (not measured time in zones):")
        print(f"  - Explicit easy sessions: {z2_ratio:.1%}; interval work: {vo2_ratio:.1%}; unclassified recovery/warmup: {max(0, 1-z2_ratio-vo2_ratio):.1%}")
        print("  - No universal 80/20 minute rule or 20-minute minimum is inferred from the literature.")
        modality_violations = check_cardio_modality(cardio)

        violations.extend(spacing_violations + cardio_violations + modality_violations)

    if args.check in ("all", "rpe"):
        # Compound RPE check
        rpe_violations = check_compound_rpe_bounds(routines)
        print("\n3. PROXIMITY TO FAILURE & SUBMAXIMAL INTENSITY:")
        print(f"  - Heavy-lift RPE policy: {'FAIL' if rpe_violations else 'PASS'} (ceiling 8, approximately 2 RIR)")
        violations.extend(rpe_violations)

    print("=" * 80)

    if violations:
        print("\nFAILURES DETECTED:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1

    print("\nPASS: All evaluated recovery, interference, and proximity-to-failure policies passed; actual recovery and individual suitability are not verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
