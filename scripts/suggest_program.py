#!/usr/bin/env python3
"""Evidence-Based Program Synthesis Engine & Pre-Flight Gatekeeper.

Generates complete, syntactically valid Python training programs conforming to:
  - First-principles Movement Pattern Taxonomy (Squat, Hinge, Push, Pull, Unilateral, Core)
  - PROGRAM_METADATA (time caps, recovery buffers, demographics)
  - ROUTINES (submaximal compounds at RPE <= 8, isolations at RPE 9-10, flat warmups)
  - CARDIO_SCHEDULE (selected easy/interval doses and scheduling buffer)
  - Peer-reviewed citations from Consensus literature cache and evidence base.

Executes scripts/qa_program.py pre-flight gatekeeper to check configured policies
across all configured gates before delivering programs.

Usage:
  python3 scripts/suggest_program.py --days [2|3|4] [--time-cap MINUTES] [--equipment EQ] [--joint-profile JP] [--tier TIER] [--focus FOCUS] [--output PATH]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import pprint
import subprocess
import sys
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from movement_patterns import MovementPattern, filter_candidates  # noqa: E402
from program_loader import validate_program_context  # noqa: E402


def _pick_exercise(
    pattern: MovementPattern,
    allowed_equipment: set[str],
    joint_profile: str,
    tier: str,
    used_exercises: set[str],
) -> dict[str, Any]:
    candidates = filter_candidates(
        pattern=pattern,
        allowed_equipment=allowed_equipment,
        joint_profile=joint_profile,
        tier=tier,
        exclude_names=used_exercises,
    )
    if not candidates:
        raise ValueError(f"No {pattern.value} candidate satisfies equipment={sorted(allowed_equipment)}, joint_profile={joint_profile}, tier={tier}. Expand the registry or explicitly revise constraints; no fallback used.")

    ex = candidates[0]
    used_exercises.add(ex.name)
    return {
        "name": ex.name,
        "compound": ex.compound,
        "warmup_reps": list(ex.warmup_reps) if ex.warmup_reps else None,
        "work_sets": ex.work_sets,
        "reps": ex.reps,
        "rpe": ex.rpe,
        "rest_seconds": ex.rest_seconds,
        "muscle_groups": list(ex.muscle_groups),
        "evidence_citation": ex.evidence_citation,
    }


def _build_2day_split(
    time_cap: int,
    focus: str,
    allowed_equipment: set[str],
    joint_profile: str,
    tier: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata = {
        "title": f"Full-Body 2x — {focus}",
        "version": "1.0.0",
        "target_demographic": focus,
        "session_time_cap_minutes": time_cap,
        "min_recovery_buffer_hours": 48,
        "description": f"Two full-body strength sessions combined with polarized cycling cardio for {focus}.",
    }

    used: set[str] = set()

    # Session A: Squat + Horiz Push + Vert Pull + Lateral/Prehab + Core
    squat_ex = _pick_exercise(MovementPattern.SQUAT, allowed_equipment, joint_profile, tier, used)
    h_push_ex = _pick_exercise(MovementPattern.HORIZONTAL_PUSH, allowed_equipment, joint_profile, tier, used)
    v_pull_ex = _pick_exercise(MovementPattern.VERTICAL_PULL, allowed_equipment, joint_profile, tier, used)
    prehab_a = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)
    core_a = _pick_exercise(MovementPattern.CORE_STABILITY, allowed_equipment, joint_profile, tier, used)

    # Session B: Hinge + Vert Push + Unilateral Lower + Horiz Pull + Prehab
    hinge_ex = _pick_exercise(MovementPattern.HINGE, allowed_equipment, joint_profile, tier, used)
    v_push_ex = _pick_exercise(MovementPattern.VERTICAL_PUSH, allowed_equipment, joint_profile, tier, used)
    uni_ex = _pick_exercise(MovementPattern.UNILATERAL_LOWER, allowed_equipment, joint_profile, tier, used)
    h_pull_ex = _pick_exercise(MovementPattern.HORIZONTAL_PULL, allowed_equipment, joint_profile, tier, used)
    prehab_b = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)

    routines = [
        {
            "name": f"Full-Body A — {squat_ex['name']} / {h_push_ex['name']} / {v_pull_ex['name']}",
            "day_key": "Tuesday",
            "notes": "RPE 8 and the warmup ramp are coaching choices; Grgic 2022 supports non-failure training.",
            "exercises": [squat_ex, h_push_ex, v_pull_ex, prehab_a, core_a],
        },
        {
            "name": f"Full-Body B — {hinge_ex['name']} / {v_push_ex['name']} / {uni_ex['name']}",
            "day_key": "Saturday",
            "notes": "Hinge and unilateral stimulus (Grgic 2022, Currier 2026).",
            "exercises": [hinge_ex, v_push_ex, uni_ex, h_pull_ex, prehab_b],
        },
    ]

    cardio = [
        {
            "day": "Monday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 45,
            "evidence_citation": "Seiler 2010 (Polarized aerobic base)",
        },
        {
            "day": "Wednesday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 45,
            "evidence_citation": "Seiler 2010 (Active aerobic recovery)",
        },
        {
            "day": "Thursday",
            "modality": "Stationary Bike",
            "type": "VO2 Max 5x3",
            "duration_minutes": 40,
            "evidence_citation": "Milanović et al. 2015 (VO2 max interval conditioning)",
        },
        {
            "day": "Sunday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 60,
            "evidence_citation": "Seiler 2010 (Polarized aerobic base)",
        },
    ]

    return metadata, routines, cardio


def _build_3day_split(
    time_cap: int,
    focus: str,
    allowed_equipment: set[str],
    joint_profile: str,
    tier: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata = {
        "title": f"Evidence-Based 3x — {focus}",
        "version": "1.0.0",
        "target_demographic": focus,
        "session_time_cap_minutes": time_cap,
        "min_recovery_buffer_hours": 48,
        "description": f"Evidence-grounded 3-day split designed for {focus} with easy rides and intervals.",
    }

    used: set[str] = set()

    # Tue Upper
    h_push_1 = _pick_exercise(MovementPattern.HORIZONTAL_PUSH, allowed_equipment, joint_profile, tier, used)
    v_pull_1 = _pick_exercise(MovementPattern.VERTICAL_PULL, allowed_equipment, joint_profile, tier, used)
    v_push_1 = _pick_exercise(MovementPattern.VERTICAL_PUSH, allowed_equipment, joint_profile, tier, used)
    h_pull_1 = _pick_exercise(MovementPattern.HORIZONTAL_PULL, allowed_equipment, joint_profile, tier, used)

    # Fri Anterior Lower
    squat_1 = _pick_exercise(MovementPattern.SQUAT, allowed_equipment, joint_profile, tier, used)
    uni_1 = _pick_exercise(MovementPattern.UNILATERAL_LOWER, allowed_equipment, joint_profile, tier, used)
    h_push_2 = _pick_exercise(MovementPattern.HORIZONTAL_PUSH, allowed_equipment, joint_profile, tier, used)
    prehab_1 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)

    # Sun Posterior Full-Body
    hinge_1 = _pick_exercise(MovementPattern.HINGE, allowed_equipment, joint_profile, tier, used)
    v_pull_2 = _pick_exercise(MovementPattern.VERTICAL_PULL, allowed_equipment, joint_profile, tier, used)
    prehab_2 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)
    prehab_3 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)

    routines = [
        {
            "name": f"Upper — {h_push_1['name']} & {v_pull_1['name']} Focus",
            "day_key": "Tuesday",
            "notes": "Upper body pressing and pulling (Grgic 2022, Currier 2026).",
            "exercises": [h_push_1, v_pull_1, v_push_1, h_pull_1],
        },
        {
            "name": f"Anterior Lower — {squat_1['name']} & {uni_1['name']}",
            "day_key": "Friday",
            "notes": "Squat and single-leg choices; Currier 2026 supports general adult resistance training.",
            "exercises": [squat_1, uni_1, h_push_2, prehab_1],
        },
        {
            "name": f"Posterior Full-Body — {hinge_1['name']} & {v_pull_2['name']}",
            "day_key": "Sunday",
            "notes": "Hinge and posterior-chain choices; Grgic 2022 supports non-failure training.",
            "exercises": [hinge_1, v_pull_2, prehab_2, prehab_3],
        },
    ]

    cardio = [
        {
            "day": "Wednesday",
            "modality": "Stationary Bike",
            "type": "VO2 Max 5x3",
            "duration_minutes": 40,
            "evidence_citation": "Milanović et al. 2015 (VO2 max interval conditioning)",
        },
        {
            "day": "Saturday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 60,
            "evidence_citation": "Seiler 2010 (Polarized aerobic base)",
        },
    ]

    return metadata, routines, cardio


def _build_4day_split(
    time_cap: int,
    focus: str,
    allowed_equipment: set[str],
    joint_profile: str,
    tier: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata = {
        "title": f"Upper / Lower 4x — {focus}",
        "version": "1.0.0",
        "target_demographic": focus,
        "session_time_cap_minutes": time_cap,
        "min_recovery_buffer_hours": 48,
        "description": f"Upper/Lower 4-day split tailored for {focus} with weekend aerobic flush.",
    }

    used: set[str] = set()

    # Mon Upper A
    h_push_1 = _pick_exercise(MovementPattern.HORIZONTAL_PUSH, allowed_equipment, joint_profile, tier, used)
    v_pull_1 = _pick_exercise(MovementPattern.VERTICAL_PULL, allowed_equipment, joint_profile, tier, used)
    h_pull_1 = _pick_exercise(MovementPattern.HORIZONTAL_PULL, allowed_equipment, joint_profile, tier, used)
    prehab_1 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)

    # Tue Lower A
    squat_1 = _pick_exercise(MovementPattern.SQUAT, allowed_equipment, joint_profile, tier, used)
    uni_1 = _pick_exercise(MovementPattern.UNILATERAL_LOWER, allowed_equipment, joint_profile, tier, used)
    prehab_2 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)
    core_1 = _pick_exercise(MovementPattern.CORE_STABILITY, allowed_equipment, joint_profile, tier, used)

    # Thu Upper B
    v_push_1 = _pick_exercise(MovementPattern.VERTICAL_PUSH, allowed_equipment, joint_profile, tier, used)
    v_pull_2 = _pick_exercise(MovementPattern.VERTICAL_PULL, allowed_equipment, joint_profile, tier, used)
    h_push_2 = _pick_exercise(MovementPattern.HORIZONTAL_PUSH, allowed_equipment, joint_profile, tier, used)
    prehab_3 = _pick_exercise(MovementPattern.JOINT_PREHAB, allowed_equipment, joint_profile, tier, used)

    # Fri Lower B
    hinge_1 = _pick_exercise(MovementPattern.HINGE, allowed_equipment, joint_profile, tier, used)
    squat_2 = _pick_exercise(MovementPattern.SQUAT, allowed_equipment, joint_profile, tier, used)
    uni_2 = _pick_exercise(MovementPattern.UNILATERAL_LOWER, allowed_equipment, joint_profile, tier, used)
    core_2 = _pick_exercise(MovementPattern.CORE_STABILITY, allowed_equipment, joint_profile, tier, used)

    routines = [
        {
            "name": f"Upper A — {h_push_1['name']} / {v_pull_1['name']}",
            "day_key": "Monday",
            "notes": "Horizontal pressing and vertical pulling strength (Grgic 2022).",
            "exercises": [h_push_1, v_pull_1, h_pull_1, prehab_1],
        },
        {
            "name": f"Lower A — {squat_1['name']} / {uni_1['name']}",
            "day_key": "Tuesday",
            "notes": "Knee-dominant anterior chain strength (Currier 2026).",
            "exercises": [squat_1, uni_1, prehab_2, core_1],
        },
        {
            "name": f"Upper B — {v_push_1['name']} / {v_pull_2['name']}",
            "day_key": "Thursday",
            "notes": "Vertical pressing and pulling balance (Currier 2026).",
            "exercises": [v_push_1, v_pull_2, h_push_2, prehab_3],
        },
        {
            "name": f"Lower B — {hinge_1['name']} / {squat_2['name']}",
            "day_key": "Friday",
            "notes": "Posterior chain hinge and unilateral strength (Grgic 2022).",
            "exercises": [hinge_1, squat_2, uni_2, core_2],
        },
    ]

    cardio = [
        {
            "day": "Wednesday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 45,
            "evidence_citation": "Seiler 2010 (Active aerobic recovery)",
        },
        {
            "day": "Saturday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 60,
            "evidence_citation": "Seiler 2010 (Polarized aerobic base)",
        },
    ]

    return metadata, routines, cardio


def generate_program_code(
    days: int,
    time_cap: int = 60,
    focus: str = "Men 40+ Joint Health",
    equipment: str = "all",
    joint_profile: str = "standard",
    tier: str = "intermediate",
    age_years: int | None = None,
    sex: str | None = None,
    primary_goal: str | None = None,
) -> str:
    """Generate syntactically valid Python code for an evidence-based training program.

    Args:
        days: Weekly training frequency (2, 3, or 4).
        time_cap: Per-session duration cap in minutes.
        focus: Target demographic or training goal.
        equipment: Comma-separated equipment constraints (e.g. 'all', 'dumbbell', 'cable').
        joint_profile: Joint-selection label, not clinical clearance ('standard', 'spine_sparing', 'fai_safe', 'athletic_multiplanar').
        tier: Training age / readiness tier ('returning', 'intermediate', 'advanced').
        age_years: Optional reported age; this generator supports adults aged 18 or older.
        sex: Optional reported descriptor; no physiology or training dose is inferred.
        primary_goal: Optional reported goal, independent of the descriptive focus.

    Returns:
        Complete Python file string.
    """
    context = {key: value for key, value in (
        ("age_years", age_years), ("sex", sex), ("primary_goal", primary_goal)
    ) if value is not None}
    context_errors = validate_program_context(context)
    if context_errors:
        raise ValueError("; ".join(context_errors))
    if age_years is not None and age_years < 18:
        raise ValueError("This adult generator requires age_years >= 18; youth programming is outside its scope.")

    if time_cap <= 0:
        raise ValueError(f"time_cap must be a positive number of minutes, got {time_cap}.")

    days = int(days)
    allowed_equipment = {e.strip().lower() for e in equipment.split(",") if e.strip()}
    if "all" in allowed_equipment or not allowed_equipment:
        allowed_equipment = {"all"}

    if days == 2:
        metadata, routines, cardio = _build_2day_split(
            time_cap=time_cap,
            focus=focus,
            allowed_equipment=allowed_equipment,
            joint_profile=joint_profile,
            tier=tier,
        )
    elif days == 3:
        metadata, routines, cardio = _build_3day_split(
            time_cap=time_cap,
            focus=focus,
            allowed_equipment=allowed_equipment,
            joint_profile=joint_profile,
            tier=tier,
        )
    elif days == 4:
        metadata, routines, cardio = _build_4day_split(
            time_cap=time_cap,
            focus=focus,
            allowed_equipment=allowed_equipment,
            joint_profile=joint_profile,
            tier=tier,
        )
    else:
        raise ValueError(f"Unsupported training days: {days}. Supported splits are 2, 3, or 4 days.")

    metadata["general_notes"] = (
        "Exact exercises, sets, reps, RPE, warmups, rests and cardio doses are coaching choices. "
        "Currier 2026 covers healthy-adult resistance training; Grgic 2022 does not require failure. "
        "Joint-profile tags are selection labels, not injury guarantees. "
        "The 48-hour scheduling buffer does not guarantee recovery."
    )
    metadata["constraints"] = {"equipment": sorted(allowed_equipment), "joint_profile": joint_profile, "tier": tier}
    metadata.update(context)
    meta_str = pprint.pformat(metadata, indent=4, sort_dicts=False)
    routines_str = pprint.pformat(routines, indent=4, sort_dicts=False)
    cardio_str = pprint.pformat(cardio, indent=4, sort_dicts=False)

    header = (
        '"""Synthesized Evidence-Based Training Program.\n\n'
        'Generated using repository coaching defaults; citation resolution is not scientific validation\n'
        'Demographic context is reported only, not suitability validation.\n'
        '(Currier et al. 2026, Grgic et al. 2022, Schumann et al. 2021, McGill 2010).\n'
        '"""\n\n'
    )

    code = f"{header}PROGRAM_METADATA = {meta_str}\n\nROUTINES = {routines_str}\n\nCARDIO_SCHEDULE = {cardio_str}\n"
    return code


def run_qa_preflight(program_file: Path) -> bool:
    """Execute scripts/qa_program.py against the synthesized program."""
    qa_script = SCRIPTS_DIR / "qa_program.py"
    cmd = [sys.executable, str(qa_script), "--program", str(program_file)]
    print(f"\n[Pre-Flight QA] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return res.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthesize evidence-grounded Hevy training program and verify with QA compiler gates."
    )
    parser.add_argument(
        "--days",
        type=int,
        choices=[2, 3, 4],
        default=3,
        help="Weekly resistance training frequency (2, 3, or 4 days, default: 3)",
    )
    parser.add_argument(
        "--time-cap",
        type=int,
        default=60,
        help="Hard per-session gym duration cap in minutes (default: 60)",
    )
    parser.add_argument(
        "--equipment",
        type=str,
        default="all",
        help="Allowed equipment (e.g. 'all', 'dumbbell', 'cable', 'dumbbell,cable', default: 'all')",
    )
    parser.add_argument(
        "--joint-profile",
        type=str,
        default="standard",
        help="Joint-selection profile (not clinical clearance) ('standard', 'fai_safe', 'spine_sparing', 'athletic_multiplanar')",
    )
    parser.add_argument(
        "--tier",
        type=str,
        default="intermediate",
        choices=["returning", "intermediate", "advanced"],
        help="Training age/tier ('returning', 'intermediate', 'advanced', default: 'intermediate')",
    )
    parser.add_argument(
        "--focus",
        type=str,
        default="Men 40+ Joint Health",
        help="Lifter demographic and joint health focus (default: 'Men 40+ Joint Health')",
    )
    parser.add_argument(
        "--age-years", type=int, default=None,
        help="Reported age in years (adult generator: 18 or older; omitted stays unknown)",
    )
    parser.add_argument(
        "--sex", default=None,
        help="Reported sex descriptor (omitted stays unknown; does not change training dose)",
    )
    parser.add_argument(
        "--primary-goal", default=None,
        help="Reported primary training goal (omitted stays unknown)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write the synthesized python program (default: programs/suggested_program.py)",
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Skip automatic pre-flight compiler QA execution",
    )

    args = parser.parse_args(argv)

    out_path = Path(args.output) if args.output else REPO_ROOT / "programs" / "suggested_program.py"
    print(f"=== Synthesizing {args.days}-Day Program for '{args.focus}' (Cap: {args.time_cap} min, Equip: {args.equipment}) ===")
    try:
        code = generate_program_code(
            days=args.days,
            time_cap=args.time_cap,
            focus=args.focus,
            equipment=args.equipment,
            joint_profile=args.joint_profile,
            tier=args.tier,
            age_years=args.age_years,
            sex=args.sex,
            primary_goal=args.primary_goal,
        )
    except ValueError as exc:
        parser.error(str(exc))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.no_qa:
        out_path.write_text(code, encoding="utf-8")
        print(f"✓ Program written to {out_path} ({len(code)} bytes)")
        return 0

    # QA runs on a sibling temp file so a failing program never replaces or leaves a file at out_path.
    # The stem must be a valid module name: check_import_health imports every programs/*.py by stem.
    pending = out_path.with_name(f"_pending_{os.getpid()}.py")
    try:
        pending.write_text(code, encoding="utf-8")
        passed = run_qa_preflight(pending)
        if passed:
            os.replace(pending, out_path)
    finally:
        pending.unlink(missing_ok=True)
    if not passed:
        print(f"\n✗ PRE-FLIGHT QA FAILED. One or more configured checks failed; nothing was written to {out_path}.",
              file=sys.stderr)
        return 1
    print(f"✓ Program written to {out_path} ({len(code)} bytes)")
    print("\n✓ PRE-FLIGHT QA PASSED: configured checks passed; individual suitability still requires review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
