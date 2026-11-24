"""Reference Template: Upper / Lower 4x Hypertrophy & Conditioning.

A balanced 4-day split under a 50-minute session cap.
"""

PROGRAM_METADATA = {
    "general_notes": "The exact exercises, sets, reps, RPE, warmup ramps, rests and cardio doses are coaching choices. Grgic 2022 supports non-failure training; accessories need not reach failure. Currier 2026 concerns healthy-adult resistance training, not exercise-specific injury protection. The 48-hour buffer is a scheduling choice, not a recovery guarantee. Age and reported sex remain unknown unless supplied as explicit metadata; titles do not establish physiology. Joint and life-stage labels do not establish clinical clearance.",
    "title": "Upper / Lower 4x — Hypertrophy & Aerobic Base",
    "version": "1.0.0",
    "target_demographic": "Intermediate Lifters (General Strength & Hypertrophy)",
    "session_time_cap_minutes": 50,
    "min_recovery_buffer_hours": 48,
    "description": (
        "4 resistance training days (Mon/Tue/Thu/Fri) with weekend aerobic cardio."
    ),
}

ROUTINES = [
    {
        "name": "Upper A — Bench & Row Focus",
        "day_key": "Monday",
        "notes": ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
                 "Upper Body Strength & Hypertrophy."),
        "exercises": [
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "6-8",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["chest", "triceps", "front_delts"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Seated Cable Row - V Grip",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 90,
                "muscle_groups": ["upper_back", "lats", "biceps"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Incline Dumbbell Press",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "10-12",
                "rpe": 9,
                "rest_seconds": 60,
                "muscle_groups": ["chest", "front_delts"],
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
                "muscle_groups": ["rear_delts"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
        ],
    },
    {
        "name": "Lower A — Squat & Calves Focus",
        "day_key": "Tuesday",
        "notes": ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
                 "Lower Body Quad & Posterior Strength."),
        "exercises": [
            {
                "name": "Squat (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["quads", "glutes"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Romanian Deadlift (Dumbbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 90,
                "muscle_groups": ["hamstrings", "glutes"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Standing Calf Raise (Dumbbell)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "12-15",
                "rpe": 9,
                "rest_seconds": 60,
                "muscle_groups": ["calves"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
        ],
    },
    {
        "name": "Upper B — Overhead Press & Pull-Up",
        "day_key": "Thursday",
        "notes": ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
                 "Vertical Push & Pull Strength."),
        "exercises": [
            {
                "name": "Overhead Press (Barbell)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["shoulders", "triceps"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Pull Up (Weighted)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "6-8",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["lats", "biceps"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Lateral Raise (Dumbbell)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "12-15",
                "rpe": 10,
                "rest_seconds": 45,
                "muscle_groups": ["side_delts"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
        ],
    },
    {
        "name": "Lower B — Deadlift & Unilateral",
        "day_key": "Friday",
        "notes": ("Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
                 "Hinge & Unilateral Strength."),
        "exercises": [
            {
                "name": "Deadlift (Trap Bar - High Handles)",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["hamstrings", "glutes", "lower_back"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
            },
            {
                "name": "Bulgarian Split Squat",
                "compound": True,
                "warmup_reps": [5, 5, 3],
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 90,
                "muscle_groups": ["quads", "glutes"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
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
]

CARDIO_SCHEDULE = [
    {
        "day": "Saturday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 60,
        "evidence_citation": "Seiler 2010 (endurance-athlete intensity context; this easy dose is a coaching choice, not proven recovery)",
    },
    {
        "day": "Sunday",
        "modality": "Stationary Bike",
        "type": "VO2 Max 4x4",
        "duration_minutes": 40,
        "evidence_citation": "Milanović et al. 2015",
    },
]
