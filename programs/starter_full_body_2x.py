"""Reference Starter Program: Full-Body 2x Strength + Polarized Cardio.

Uses the existing longevity/40+ label and hip-selection constraints; no FAI safety guarantee.
Capped at 60 minutes per session with a >=48-hour recovery buffer
before high-intensity cardio intervals.
"""

PROGRAM_METADATA = {
    "general_notes": "The exact exercises, sets, reps, RPE, warmup ramps, rests and cardio doses are coaching choices. Grgic 2022 supports non-failure training; accessories need not reach failure. Currier 2026 concerns healthy-adult resistance training, not exercise-specific injury protection. The 48-hour buffer is a scheduling choice, not a recovery guarantee. Age and reported sex remain unknown unless supplied as explicit metadata; titles do not establish physiology. Joint and life-stage labels do not establish clinical clearance.",
    "title": "Full-Body 2x — Strength + Polarized Cardio",
    "version": "1.0.0",
    "target_demographic": "Longevity & Master Lifters (40+)",
    "session_time_cap_minutes": 60,
    "min_recovery_buffer_hours": 48,
    "description": (
        "Two full-body strength sessions (Tuesday/Sunday) combined with "
        "polarized cycling cardio (Friday VO2 Max 5x3 + Mon/Wed/Sat Zone 2)."
    ),
}

ROUTINES = [
    {
        "name": "Full-Body A — Squat / Bench / Pull",
        "day_key": "Tuesday",
        "notes": (
            ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
            "Squat: 1 top set of 3 @ RPE 8, 2 back-off 5s @ 90%.\n"
            "Bench: 1 top set of 3 @ RPE 8, 2 back-off 5s @ 90%.\n"
            "Pull-Up: 3x6 @ RPE 8.\n"
            "Hip Abduction & Palloff: 0-1 RIR.")
        ),
        "exercises": [
            {
                "name": "Box Squat (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "3-5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["quads", "glutes"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "3-5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["chest", "triceps", "front_delts"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Pull Up (Weighted)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "6",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["lats", "biceps", "upper_back"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Hip Abduction (Machine)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "15-20",
                "rpe": 10,
                "rest_seconds": 60,
                "muscle_groups": ["glutes"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Pallof Press (Band)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "10-12",
                "rpe": 9,
                "rest_seconds": 45,
                "muscle_groups": ["core"],
                "evidence_citation": "McGill 2010 (general trunk guidance; this exercise and dose are coaching choices, not injury protection)",
            },
        ],
    },
    {
        "name": "Full-Body B — Hinge / Press / Unilateral / Row",
        "day_key": "Sunday",
        "notes": (
            ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
            "Trap Bar Deadlift: 1 top set of 3 @ RPE 8, 2 back-off 5s @ 90%.\n"
            "Overhead Press: 3x5 @ RPE 8.\n"
            "Dumbbell Step Up: 3x8/side @ RPE 8.\n"
            "Seated Cable Row: 3x10-12 @ RPE 8.\n"
            "Face Pull: 3x15-20 at RPE 10 maximum; failure is optional.")
        ),
        "exercises": [
            {
                "name": "Deadlift (Trap Bar - High Handles)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "3-5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["hamstrings", "glutes", "lower_back"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Overhead Press (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["shoulders", "triceps", "upper_chest"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Dumbbell Step Up",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "8",
                "rpe": 8,
                "rest_seconds": 105,
                "muscle_groups": ["quads", "glutes"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Seated Cable Row - V Grip",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "10-12",
                "rpe": 8,
                "rest_seconds": 60,
                "muscle_groups": ["upper_back", "lats", "biceps"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Face Pull (Cable)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "15-20",
                "rpe": 10,
                "rest_seconds": 45,
                "muscle_groups": ["rear_delts", "rotator_cuff"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
        ],
    },
]

CARDIO_SCHEDULE = [
    {
        "day": "Monday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 60,
        "evidence_citation": "Seiler 2010 (endurance-athlete intensity context; this easy dose is a coaching choice, not proven recovery)",
    },
    {
        "day": "Wednesday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 45,
        "evidence_citation": "Seiler 2010 (endurance-athlete intensity context; this easy dose is a coaching choice, not proven recovery)",
    },
    {
        "day": "Friday",
        "modality": "Stationary Bike",
        "type": "VO2 Max 5x3",
        "duration_minutes": 40,
        "evidence_citation": "Milanović et al. 2015, Schumann et al. 2021",
    },
    {
        "day": "Saturday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 45,
        "evidence_citation": "Seiler 2010 (endurance-athlete intensity context; this easy dose is a coaching choice, not proven recovery)",
    },
]
