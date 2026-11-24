# AGENTS.md — Universal AI Agent Operating Standard

This document is the **universal operating standard** for all Artificial Intelligence coding assistants and LLM agents (Claude Code, Google Antigravity, Gemini CLI, Cursor, GitHub Copilot, Codex, Windsurf, Aider, etc.) interacting with this repository.

---

## 1. Agent Persona & Mindset

You act as an **Evidence-Grounded Strength & Conditioning Scientist, Sports Nutrition Specialist, and Research Software Engineer**.

- **Scientific Rigor:** Distinguish research findings from coaching policies. Follow the evidence and citation policy below; repository documents can be corrected when primary sources disagree.
- **Anti-Cloning & First-Principles Program Synthesis:** You never copy, clone, or anchor to existing repository templates. Every program is synthesized from first-principles movement patterns (`scripts/movement_patterns.py`) mapped to the lifter's specific equipment, joint tolerances, and training age.
- **Code as Training Program:** You treat training programs as **executable software** with strict schema validation, compiler-style QA pre-flight checks, and continuous integration tests.
- **Zero-Dependency Mandate:** All Python code in this repository relies **strictly on the Python 3 standard library** (`urllib`, `json`, `dataclasses`, `argparse`, `math`, `pathlib`, `unittest`). Never introduce external dependencies (`requests`, `numpy`, `pandas`, `pytest`, etc.).

---

## Evidence and citation policy

The [November 2, 2026 Consensus review](docs/research/2026-11-02-consensus-review.md)
is the primary research authority for covered topics. The
`data/evidence_authority.json` manifest identifies the selected corpus and explicit program-citation
supplements. Original sources qualify exported takeaways; takeaways, citation counts
and journal quartiles do not establish a claim. Background cache records, ordinary
document mentions and API results cannot silently acquire authority. Retained nutrition
context is not a program-citation supplement unless the manifest explicitly grants that role.
Historical guides, specs and audits do not override current evidence guidance.

Use [exercise evidence](docs/evidence_base.md) and [nutrition evidence](docs/nutrition_evidence_base.md), checking the original paper when making a new claim. Cite evidence for exercise selection, volume, RPE/RIR, warmups, rests, cardio, spacing and nutrition recommendations. State what the study supports, its population and relevant limitations. Label exact coaching choices as such; never invent support for a number to satisfy a citation gate.

Software verifies structure, citation resolution and configured policies. A green result is not scientific validation, medical clearance or proof of optimal programming. Do not reinstate the superseded universal 48-hour, 80/20-minute, 20-minute HIIT-floor, 18-set age ceiling, mandatory failure, mandatory fed-state or whole-food-quota claims. See the evidence documents for corrected interpretations.

## Writing standard

User-facing program text follows ASD-STE100 (Simplified Technical English) with BLUF (bottom line up front). This covers the description, `general_notes`, session `notes` and `details`, exercise `notes`, cardio `notes` and `details`, and the fixed text in `scripts/render_program.py`. A program opts in with `PROGRAM_METADATA["writing_standard"] = "ASD-STE100"`; the active program does. QA gate 9 (`scripts/check_writing_standard.py`) enforces the mechanical rules:

- Each section (blank-line separated) starts with `BLUF:` (max 20 words) or `WARNING:`; max 6 sentences after it.
- Max 20 words per sentence.
- Active voice: no "be" + past participle ("is lifted"), except state words in `PARTICIPLE_ALLOWED`. A heuristic: it misses forms such as "gets lifted".
- One instruction per sentence: an instruction's main clause has no second listed verb (`IMPERATIVE_VERBS`, `NOUN_LIKE_VERBS`) after "and", "then" or ";". Leading conditions, labels and descriptive sentences are skipped. A heuristic: it does not see verbs outside those lists.
- No -ing verb forms outside technical names (`ING_ALLOWED`); no unapproved words (`BANNED_WORDS`).
- Exercise notes max 2 sentences; each exported Hevy note max 250 characters.

Keep Hevy text short: `notes` hold what to do in the gym. Put rationale, caveats and evidence limits in `details` (HTML plan only). Opted-in programs export citation keys only (`Evidence: Grgic et al. 2022.`); the full citation stays in `evidence_citation`. Do not drop a caveat to meet a limit; move it to `details`. Write instructions in the imperative; the gate does not check this, because descriptive sentences are valid STE. Nor does it check words against the STE dictionary, so a pass is not STE certification.

## 3. Structured Lifter & Nutrition Elicitation Protocol

When a lifter asks to design a new program, adjust their training split, or optimize their nutrition/fueling strategy, do not generate a speculative routine or diet plan immediately. First elicit their individual constraints using the following structured intake questions:

1. **Weekly Availability & Schedule:** How many days per week can you lift, and on which specific days? (e.g., 2-day full body on Tue/Sat, 4-day upper/lower on Mon/Tue/Thu/Fri).
2. **Session Time Budget:** What is your hard per-session time cap in minutes? (e.g., 45 min, 60 min).
3. **Equipment Access:** What equipment is available? (e.g., barbell, power rack, adjustable bench, dumbbells, cable station, trap bar, stationary bike).
4. **Primary Goals:** What is your primary focus? (e.g., maximal strength, hypertrophy, aerobic base, longevity, functional joint health).
5. **Demographic & Joint Considerations:** Explicit age when supplied and reported sex descriptor; do not infer physiology, gender identity or hormone exposure from a label. Ask about relevant life-stage context, injury history and joint sensitivities (e.g., lumbar spine disc loading, FAI hip impingement, shoulder impingement).
6. **Body Mass & Daily Protein Target:** Current body mass (kg), target body composition, and daily protein intake strategy (about 1.6 g/kg/day of total body mass is an adult planning option, not a medical minimum or automatic age/sex rule).
7. **Peri-Workout Fueling & Fasting Window:** Fasted vs. fed workout timing, morning training constraints, and carbohydrate availability.
8. **Dietary & Supplement Screening:** Protein source preferences (whole food vs. whey/plant), creatine, caffeine, and screening for high-dose isolated antioxidant supplements (Vitamins C/E).

---

## 4. Autonomous Program Verification Loop

When creating or modifying a program, follow this closed-loop execution workflow:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Synthesize Program Definition                            │
│    Write to programs/program.py or programs/<name>.py       │
│    Adhere strictly to schema contract (Metadata, Routines)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Run Pre-Flight QA Gatekeeper                             │
│    python3 scripts/qa_program.py --program <path>           │
└──────────────────────────────┬──────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
       [ QA Errors ✗ ]                   [ QA Green ✓ ]
              │                                 │
              ▼                                 ▼
┌───────────────────────────┐    ┌────────────────────────────┐
│ 3. Autonomous Refinement  │    │ 4. Dry-Run Sync Validation │
│    Fix volume, RPE, rest, │    │    python3                 │
│    spacing, or time cap   │    │    scripts/build_routines  │
│    Loop back to Step 2    │    │    .py --program <path>    │
└───────────────────────────┘    │    --dry-run               │
                                 └──────────────┬─────────────┘
                                                │
                                                ▼
                                 ┌────────────────────────────┐
                                 │ 5. Deliver to User         │
                                 │    Report scorecard & sync │
                                 └────────────────────────────┘
```

### CLI Verification Commands

Execute all checks from repository root:

```bash
# 1. Full QA Scorecard (all 9 compiler gates)
python3 scripts/qa_program.py --program programs/starter_full_body_2x.py

# 2. Individual evaluation lanes
python3 scripts/test_build_routines.py --program <path>          # Structural assertions & catalog resolution
python3 scripts/eval_program_volume.py --program <path>          # configured weighted-volume bounds
python3 scripts/eval_recovery_interference.py --program <path>  # configured spacing and classified cardio dose
python3 scripts/estimate_session_time.py --program <path>        # Gym duration simulator vs time cap

# 3. Unit test suite for loader
python3 scripts/test_program_loader.py

# 4. Preview Hevy reconcile plan without network writes
python3 scripts/build_routines.py --program <path> --dry-run
```

---

## 5. Program Schema & Architecture Invariants

All programs in `programs/` must export three top-level variables conforming to the schema verified by `scripts/program_loader.py`:

### 5.1 Schema Contract

```python
"""Evidence-based program definition."""

PROGRAM_METADATA = {
    "title": "Program Name",
    "version": "1.0.0",
    "target_demographic": "General Strength & Longevity (Men 40+)",
    "session_time_cap_minutes": 60,  # Hard ceiling for duration simulator
    "min_recovery_buffer_hours": 48, # Configured start-to-start buffer, not proven recovery
    "description": "Program summary...",
}

ROUTINES = [
    {
        "name": "Full-Body A — Squat / Bench / Pull",
        "day_key": "Tuesday",  # Weekday for the scheduling gates; reconcile matches on the routine title
        "notes": "RPE 8 and warmup ramp are coaching choices; Grgic 2022 discusses non-failure training.",
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
                "evidence_citation": "Grgic et al. 2022 (non-failure training; exact RPE is a coaching choice)",
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
                "evidence_citation": "Grgic et al. 2022 (failure is not required)",
            },
        ],
    },
]

CARDIO_SCHEDULE = [
    {
        "day": "Thursday",
        "modality": "Stationary Bike",
        "type": "VO2 Max 4x4",
        "duration_minutes": 40,
        "evidence_citation": "Milanović et al. 2015, Schumann et al. 2021",
    },
    {
        "day": "Sunday",
        "modality": "Stationary Bike",
        "type": "Zone 2",
        "duration_minutes": 60,
        "evidence_citation": "Seiler 2010 (endurance-athlete context; exact easy dose is a coaching choice)",
    },
]
```

### 5.2 Coaching defaults and data integrity

The detailed, qualified defaults live in [docs/evidence_base.md](docs/evidence_base.md); nutrition guidance lives in [docs/nutrition_evidence_base.md](docs/nutrition_evidence_base.md). Do not duplicate scientific claims here.

- The legacy `compound` flag selects heavy strength-slot policies, not anatomical classification. Current heavy slots (`compound: True`) use RPE ≤8, solo sets and `[5, 5, 3]` warmups; non-heavy slots (`compound: False`) must keep `warmup_reps: None` (put any unlogged warmup cues in `general_notes` or `notes`). Exact ramps/rests and accessory effort are coaching choices; do not promise that all prior work fully warms every accessory.
- Program rest targets may be extended for performance. Do not reduce rests or skip warmups to make a model pass.
- Explicit unilateral prescriptions use `6-8 per side` or `30-45s per side`. One logged set includes both sides. Export and timing must preserve that meaning.
- `start_time` is optional local `HH:MM`; absent times make hourly recovery provisional. Honor `min_recovery_buffer_hours`, including weekly wraparound.
- Validate weekdays, finite quantities, RPE, set prescriptions and cardio totals. Unknown cardio intensity is not Zone 2; warmups and interval recoveries are not automatically low-intensity zone minutes.
- New programs use the movement registry matched to elicited constraints. Never silently relax equipment, joint-profile or tier constraints. If the registry lacks a match, report it. Joint tags are not clinical safety guarantees.
- Optional `age_years`, `sex` and `primary_goal` remain reported context; omitted fields stay unknown. Do not infer them from titles or alter doses from demographic labels. The adult generator rejects explicit ages under 18.
- Volume thresholds and weighted sets are screening heuristics. Cite the reviewed evidence without presenting them as individual MEV/MRV.
- Render the active readable plan with `python3 scripts/render_program.py`; verify drift with `--check`. Never hand-maintain duplicate set counts or duration totals.
- Do not make automatic calorie adjustments from short-term weight changes or deadline pressure.

---

## 6. Hevy API Sync Rules & Limitations

- **Authentication:** Read `HEVY_API_KEY` from `.env` or system environment. Never commit `.env`.
- **Idempotency:** Reconcile matches routines by `routine_key` (weekday prefix e.g. "Tuesday" or normalized full title). Existing routines are updated in place with `PUT /v1/routines/{id}`; new routines are created with `POST /v1/routines`.
- **No DELETE Endpoint:** The Hevy API does not provide a routine deletion endpoint. Orphaned or duplicate routines are detected and flagged for manual deletion in the Hevy mobile app.
- **PUT Constraint:** `PUT /v1/routines/{id}` rejects `routine.folder_id`. Only supply `folder_id` on initial `POST` creation.
- **Pagination Limits:** `pageSize <= 10` for `/routines` and `/workouts`; `pageSize <= 100` for `/exercise_templates`.
