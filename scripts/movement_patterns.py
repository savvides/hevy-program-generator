"""Movement Pattern Registry & Constraint-Driven Exercise Taxonomy.

Provides the 8 fundamental human movement patterns + joint integrity slots,
mapping exercises against Hevy catalog templates, equipment constraints,
joint-selection profiles, and scoped sports science citations.

Joint tags (including fai_safe and zero_spinal_load) are legacy selection labels,
not measured biomechanics, injury guarantees or clinical clearance. Exact doses,
RPE, warmups and rests are coaching choices; preserve elicited constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MovementPattern(str, Enum):
    SQUAT = "squat"
    HINGE = "hinge"
    UNILATERAL_LOWER = "unilateral_lower"
    HORIZONTAL_PUSH = "horizontal_push"
    VERTICAL_PUSH = "vertical_push"
    HORIZONTAL_PULL = "horizontal_pull"
    VERTICAL_PULL = "vertical_pull"
    CORE_STABILITY = "core_stability"
    JOINT_PREHAB = "joint_prehab"


@dataclass(frozen=True)
class MovementExercise:
    name: str
    pattern: MovementPattern
    compound: bool
    equipment: frozenset[str]
    joint_tags: frozenset[str]
    tiers: frozenset[str]
    muscle_groups: tuple[str, ...]
    warmup_reps: Optional[tuple[int, ...]]
    work_sets: int
    reps: str
    rpe: int
    rest_seconds: int
    evidence_citation: str


MOVEMENT_REGISTRY: dict[MovementPattern, list[MovementExercise]] = {
    MovementPattern.SQUAT: [
        MovementExercise(
            name="Goblet Squat",
            pattern=MovementPattern.SQUAT,
            compound=True,
            equipment=frozenset({"dumbbell", "kettlebell"}),
            joint_tags=frozenset({"lumbar_friendly", "beginner_friendly", "athletic_multiplanar", "knee_friendly"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Box Squat (Barbell)",
            pattern=MovementPattern.SQUAT,
            compound=True,
            equipment=frozenset({"barbell"}),
            joint_tags=frozenset({"fai_safe", "lumbar_friendly", "knee_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="6-8",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Leg Press (Machine)",
            pattern=MovementPattern.SQUAT,
            compound=True,
            equipment=frozenset({"machine"}),
            joint_tags=frozenset({"lumbar_friendly", "fai_safe"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="10-12",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Leg Extension (Machine)",
            pattern=MovementPattern.SQUAT,
            compound=False,
            equipment=frozenset({"machine"}),
            joint_tags=frozenset({"fai_safe", "lumbar_friendly", "quad_isolation"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("quads",),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=9,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
    MovementPattern.HINGE: [
        MovementExercise(
            name="Romanian Deadlift (Dumbbell)",
            pattern=MovementPattern.HINGE,
            compound=True,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"lumbar_friendly", "beginner_friendly", "lengthened_hamstring"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("hamstrings", "glutes", "lower_back"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Deadlift (Trap Bar - High Handles)",
            pattern=MovementPattern.HINGE,
            compound=True,
            equipment=frozenset({"barbell"}),
            joint_tags=frozenset({"lumbar_friendly", "high_strength"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("hamstrings", "glutes", "lower_back"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="6-8",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Hip Thrust (Barbell)",
            pattern=MovementPattern.HINGE,
            compound=True,
            equipment=frozenset({"barbell"}),
            joint_tags=frozenset({"pure_glute", "zero_spinal_load", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("glutes", "hamstrings"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-12",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Andersen et al. 2017 (acute EMG comparison in trained men; not injury protection or long-term hypertrophy proof)",
        ),
    ],
    MovementPattern.UNILATERAL_LOWER: [
        MovementExercise(
            name="Dumbbell Step Up",
            pattern=MovementPattern.UNILATERAL_LOWER,
            compound=True,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"running_mechanics", "fai_safe", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Lateral Lunge",
            pattern=MovementPattern.UNILATERAL_LOWER,
            compound=False,
            equipment=frozenset({"dumbbell", "bodyweight"}),
            joint_tags=frozenset({"athletic_multiplanar", "frontal_plane", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=8,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Bulgarian Split Squat",
            pattern=MovementPattern.UNILATERAL_LOWER,
            compound=True,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"high_hypertrophy", "quad_stretch"}),
            tiers=frozenset({"intermediate", "advanced"}),
            muscle_groups=("quads", "glutes"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
    MovementPattern.HORIZONTAL_PUSH: [
        MovementExercise(
            name="Push Up",
            pattern=MovementPattern.HORIZONTAL_PUSH,
            compound=False,
            equipment=frozenset({"bodyweight"}),
            joint_tags=frozenset({"closed_chain", "shoulder_friendly", "core_integration", "athletic_multiplanar"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("chest", "triceps", "front_delts"),
            warmup_reps=None,
            work_sets=3,
            reps="10-15",
            rpe=8,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Bench Press (Dumbbell)",
            pattern=MovementPattern.HORIZONTAL_PUSH,
            compound=True,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"shoulder_friendly", "converging_path"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("chest", "triceps", "front_delts"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Bench Press (Barbell)",
            pattern=MovementPattern.HORIZONTAL_PUSH,
            compound=True,
            equipment=frozenset({"barbell"}),
            joint_tags=frozenset({"maximal_power"}),
            tiers=frozenset({"intermediate", "advanced"}),
            muscle_groups=("chest", "triceps", "front_delts"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="5",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Incline Bench Press (Dumbbell)",
            pattern=MovementPattern.HORIZONTAL_PUSH,
            compound=False,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"shoulder_friendly", "clavicular_head"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("chest", "front_delts"),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=9,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
    MovementPattern.VERTICAL_PUSH: [
        MovementExercise(
            name="Overhead Press (Dumbbell)",
            pattern=MovementPattern.VERTICAL_PUSH,
            compound=True,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"shoulder_friendly", "neutral_grip", "athletic_multiplanar"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("shoulders", "triceps"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Overhead Press (Barbell)",
            pattern=MovementPattern.VERTICAL_PUSH,
            compound=True,
            equipment=frozenset({"barbell"}),
            joint_tags=frozenset({"maximal_strength"}),
            tiers=frozenset({"intermediate", "advanced"}),
            muscle_groups=("shoulders", "triceps", "upper_chest"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="5",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Seated Shoulder Press (Machine)",
            pattern=MovementPattern.VERTICAL_PUSH,
            compound=False,
            equipment=frozenset({"machine"}),
            joint_tags=frozenset({"isolated_delts", "stable", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("shoulders", "triceps"),
            warmup_reps=None,
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=60,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
    ],
    MovementPattern.HORIZONTAL_PULL: [
        MovementExercise(
            name="Dumbbell Row",
            pattern=MovementPattern.HORIZONTAL_PULL,
            compound=False,
            equipment=frozenset({"dumbbell"}),
            joint_tags=frozenset({"anti_rotational_core", "lumbar_friendly", "athletic_multiplanar"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("upper_back", "lats", "biceps"),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=8,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Seated Cable Row - V Grip",
            pattern=MovementPattern.HORIZONTAL_PULL,
            compound=False,
            equipment=frozenset({"cable"}),
            joint_tags=frozenset({"scapular_retraction", "lumbar_neutral"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("upper_back", "lats", "biceps"),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=8,
            rest_seconds=60,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
    MovementPattern.VERTICAL_PULL: [
        MovementExercise(
            name="Lat Pulldown (Cable)",
            pattern=MovementPattern.VERTICAL_PULL,
            compound=True,
            equipment=frozenset({"cable"}),
            joint_tags=frozenset({"scalable", "scapular_depression", "returning_friendly", "shoulder_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("lats", "upper_back", "biceps"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="8-10",
            rpe=8,
            rest_seconds=90,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
        MovementExercise(
            name="Pull Up (Weighted)",
            pattern=MovementPattern.VERTICAL_PULL,
            compound=True,
            equipment=frozenset({"bodyweight", "barbell"}),
            joint_tags=frozenset({"relative_strength"}),
            tiers=frozenset({"intermediate", "advanced"}),
            muscle_groups=("lats", "biceps", "upper_back"),
            warmup_reps=(5, 5, 3),
            work_sets=3,
            reps="6",
            rpe=8,
            rest_seconds=120,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
    MovementPattern.CORE_STABILITY: [
        MovementExercise(
            name="Cable Core Pallof Press",
            pattern=MovementPattern.CORE_STABILITY,
            compound=False,
            equipment=frozenset({"cable", "band"}),
            joint_tags=frozenset({"anti_rotation", "transverse_abdominis", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("core",),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=9,
            rest_seconds=45,
            evidence_citation="McGill 2010 (general trunk guidance; this exercise and dose are coaching choices, not injury protection)",
        ),
        MovementExercise(
            name="Side Plank",
            pattern=MovementPattern.CORE_STABILITY,
            compound=False,
            equipment=frozenset({"bodyweight"}),
            joint_tags=frozenset({"lateral_core", "glute_med", "lumbar_friendly", "athletic_multiplanar"}),
            tiers=frozenset({"returning", "intermediate"}),
            muscle_groups=("core",),
            warmup_reps=None,
            work_sets=3,
            reps="30-45s",
            rpe=9,
            rest_seconds=45,
            evidence_citation="McGill 2010 (general trunk guidance; this exercise and dose are coaching choices, not injury protection)",
        ),
        MovementExercise(
            name="Plank",
            pattern=MovementPattern.CORE_STABILITY,
            compound=False,
            equipment=frozenset({"bodyweight"}),
            joint_tags=frozenset({"anti_extension", "anterior_core", "lumbar_friendly"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("core",),
            warmup_reps=None,
            work_sets=3,
            reps="45-60s",
            rpe=9,
            rest_seconds=45,
            evidence_citation="McGill 2010 (general trunk guidance; this exercise and dose are coaching choices, not injury protection)",
        ),
    ],
    MovementPattern.JOINT_PREHAB: [
        MovementExercise(
            name="Face Pull (Cable)",
            pattern=MovementPattern.JOINT_PREHAB,
            compound=False,
            equipment=frozenset({"cable", "band"}),
            joint_tags=frozenset({"rotator_cuff", "rear_delt", "posture"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("rear_delts", "rotator_cuff"),
            warmup_reps=None,
            work_sets=3,
            reps="15-20",
            rpe=10,
            rest_seconds=45,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Hip Abduction (Machine)",
            pattern=MovementPattern.JOINT_PREHAB,
            compound=False,
            equipment=frozenset({"machine"}),
            joint_tags=frozenset({"glute_med", "pelvic_stability", "athletic_multiplanar"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("glutes",),
            warmup_reps=None,
            work_sets=3,
            reps="15-20",
            rpe=10,
            rest_seconds=60,
            evidence_citation="Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
        ),
        MovementExercise(
            name="Seated Leg Curl (Machine)",
            pattern=MovementPattern.JOINT_PREHAB,
            compound=False,
            equipment=frozenset({"machine"}),
            joint_tags=frozenset({"lengthened_hamstring"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("hamstrings",),
            warmup_reps=None,
            work_sets=3,
            reps="10-12",
            rpe=10,
            rest_seconds=60,
            evidence_citation="Maeo et al. 2021 (lengthened hamstring hypertrophy)",
        ),
        MovementExercise(
            name="Single Arm Lateral Raise (Cable)",
            pattern=MovementPattern.JOINT_PREHAB,
            compound=False,
            equipment=frozenset({"cable"}),
            joint_tags=frozenset({"lateral_deltoid"}),
            tiers=frozenset({"returning", "intermediate", "advanced"}),
            muscle_groups=("shoulders",),
            warmup_reps=None,
            work_sets=3,
            reps="12-15",
            rpe=10,
            rest_seconds=45,
            evidence_citation="Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
        ),
    ],
}


def filter_candidates(
    pattern: MovementPattern,
    allowed_equipment: set[str],
    joint_profile: str = "standard",
    tier: str = "intermediate",
    exclude_names: Optional[set[str]] = None,
) -> list[MovementExercise]:
    """Filter candidate exercises for a movement pattern by constraints, ordered by fitness score."""
    candidates = MOVEMENT_REGISTRY.get(pattern, [])
    filtered: list[tuple[float, MovementExercise]] = []
    excludes = exclude_names or set()

    for ex in candidates:
        if ex.name in excludes:
            continue

        # Check equipment compatibility
        if "all" not in allowed_equipment and not (ex.equipment & allowed_equipment):
            continue

        if tier not in ex.tiers:
            continue
        profile_tag = {"spine_sparing": "lumbar_friendly"}.get(joint_profile, joint_profile)
        if joint_profile != "standard" and profile_tag not in ex.joint_tags:
            continue

        # Registry order breaks ties; prefer the heavy slot when both are eligible.
        score = 1.0 if ex.compound else 0.0

        filtered.append((score, ex))

    filtered.sort(key=lambda item: item[0], reverse=True)
    return [ex for _, ex in filtered]
