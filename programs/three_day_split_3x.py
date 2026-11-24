"""Three-Day Split 3x: Strength & Polarized Cardio.

Uses the existing longevity/40+ label and hip-selection constraints; no FAI safety guarantee.
Strictly capped at 60 minutes per lifting session (excluding post-lift sauna)
with >=48-hour recovery buffer between heavy lower-body lifts and Wednesday VO2 Max cycling intervals.
"""

PROGRAM_METADATA = {
    "general_notes": "The exact exercises, sets, reps, RPE, warmup ramps, rests and cardio doses are coaching choices. Grgic 2022 supports non-failure training; accessories need not reach failure. Currier 2026 concerns healthy-adult resistance training, not exercise-specific injury protection. The 48-hour buffer is a scheduling choice, not a recovery guarantee. Age and reported sex remain unknown unless supplied as explicit metadata; titles do not establish physiology. Joint and life-stage labels do not establish clinical clearance.",
    "title": "Three-Day Split 3x — Strength & Polarized Cardio",
    "version": "1.2.0",
    "target_demographic": "Longevity & Master Lifters (40+)",
    "session_time_cap_minutes": 60,
    "min_recovery_buffer_hours": 48,
    "description": (
        "Three lifting sessions (Tuesday Upper, Friday Anterior Lower, "
        "Sunday Posterior Full-Body) paired with polarized cycling cardio "
        "(Wednesday VO2 Max 5x3 + Mon/Sat Zone 2) under a 60-minute lifting cap "
        "(excluding post-lift sauna)."
    ),
}

PROGRESSION_NOTE = (
    "\nProgression: when every work set reaches the top of its rep range at RPE <= 8, "
    "add 2.5 kg (upper) / 5 kg (lower) next session (coaching progression choice).\n"
    "Deload: every 6th week compounds top set only, accessories 2 sets (coaching schedule, not a scientific requirement)."
)

ROUTINES = [
    {
        "name": "Tuesday — Strength A — Pure Upper Body Strength & Postural Health",
        "day_key": "Tuesday",
        "notes": (
            "Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
            "Bench: 3 sets in the 3-5 range — set 1 top set of 3 @ RPE 8, sets 2-3 back-off 5s @ ~90%.\n"
            "Pull-Up: 3x4-5 @ RPE 8 — add load only once 5 reps is a true 1-2 RIR.\n"
            "Machine Shoulder Press: 3x8-10 @ RPE 8.\n"
            "Cable Row: 3x10-12 @ RPE 8.\n"
            "Face Pull & Pallof: 0-1 RIR."
            + PROGRESSION_NOTE
        ),
        "exercises": [
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
                "reps": "4-5",
                "rpe": 8,
                "rest_seconds": 120,
                "muscle_groups": ["lats", "biceps", "upper_back"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Seated Shoulder Press (Machine)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 75,
                "muscle_groups": ["shoulders", "triceps"],
                "evidence_citation": "Grgic et al. 2022 (failure is not required; exact RPE and dose are coaching choices)",
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
        "name": "Friday — Strength B — Anterior Lower & FAI Hip Stability",
        "day_key": "Friday",
        "notes": (
            "Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
            "Box Squat: 3 sets in the 3-5 range — set 1 top set of 3 @ RPE 8, sets 2-3 back-off 5s @ ~90%.\n"
            "Step-Up: 3x8/side @ RPE 8.\n"
            "Leg Extension: 3x10-12 @ RPE 9.\n"
            "Hip Abduction & Plank: 0-1 RIR."
            + PROGRESSION_NOTE
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
                "name": "Leg Extension (Machine)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "10-12",
                "rpe": 9,
                "rest_seconds": 60,
                "muscle_groups": ["quads"],
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
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Plank",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "45-60s",
                "rpe": 9,
                "rest_seconds": 45,
                "muscle_groups": ["core"],
                "evidence_citation": "McGill 2010 (general trunk guidance; this exercise and dose are coaching choices, not injury protection)",
            },
        ],
    },
    {
        "name": "Sunday — Strength C — Posterior Chain Power & Full-Body Finish",
        "day_key": "Sunday",
        "notes": (
            "Doses below are coaching choices. Accessory RPE is a ceiling; failure is not necessary.\n"
            "Trap Bar Deadlift: 3 sets in the 3-5 range — set 1 top set of 3 @ RPE 8, sets 2-3 back-off 5s @ ~90%.\n"
            "Incline DB Press: 3x8-10 @ RPE 8 — second weekly chest exposure, replaces DB shoulder press.\n"
            "Lat Pulldown: 3x8-10 @ RPE 8.\n"
            "Seated Leg Curl: 3x10-12 @ RPE 9. Recline 15° for hip comfort; this is not FAI clearance.\n"
            "Cable Lateral Raise: 3x12-15 at RPE 10 maximum; failure is optional."
            + PROGRESSION_NOTE
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
                "evidence_citation": "Andersen et al. 2017 (acute EMG comparison in trained men; not injury protection or long-term hypertrophy proof)",
            },
            {
                "name": "Incline Bench Press (Dumbbell)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 75,
                "muscle_groups": ["chest", "triceps", "front_delts"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Lat Pulldown (Cable)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "8-10",
                "rpe": 8,
                "rest_seconds": 75,
                "muscle_groups": ["lats", "upper_back", "biceps"],
                "evidence_citation": "Currier et al. 2026 (healthy-adult resistance training; this exercise and dose are coaching choices)",
            },
            {
                "name": "Seated Leg Curl (Machine)",
                "compound": False,
                "warmup_reps": None,
                "work_sets": 3,
                "reps": "10-12",
                "rpe": 9,
                "rest_seconds": 60,
                "muscle_groups": ["hamstrings"],
                "evidence_citation": "Maeo et al. 2021 (lengthened hamstring knee-flexion hypertrophy)",
            },
            {
                "name": "Single Arm Lateral Raise (Cable)",
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
        "type": "VO2 Max 5x3",
        "duration_minutes": 40,
        "evidence_citation": "Milanović et al. 2015, Buchheit & Laursen 2013, Schumann et al. 2021",
    },
    {
        "day": "Saturday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 45,
        "evidence_citation": "Seiler 2010 (endurance-athlete intensity context; this easy dose is a coaching choice, not proven recovery)",
    },
]
