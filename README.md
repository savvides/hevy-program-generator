# Hevy Program Generator (`hevy-program-generator`)

[![CI: QA & Verification Gate](https://github.com/savvides/hevy-program-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/savvides/hevy-program-generator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/savvides/hevy-program-generator)](https://github.com/savvides/hevy-program-generator/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg)](https://docs.python.org/3/library/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Evidence Reference](https://img.shields.io/badge/evidence-Exercise%20Physiology-orange.svg)](docs/evidence_base.md)
[![Nutrition Reference](https://img.shields.io/badge/nutrition-Bioenergetics%20Evidence-green.svg)](docs/nutrition_evidence_base.md)

**Hevy Program Generator** (`hevy-program-generator`) is an open-source, evidence-grounded training & nutrition engine that treats exercise science, nutritional bioenergetics, and Hevy training programs as **executable, test-driven software**.

Define training routines in Python, validate them against deterministic structure and coaching-policy checks (volume screens, RPE ceilings, scheduling and duration estimates), push routines seamlessly to your mobile [Hevy](https://hevy.com) app via REST API, and pull workout history into clean, git-friendly JSON.

---

## Key Highlights

- **Zero-Dependency Guarantee:** Built **100% on the Python 3 standard library** (`urllib`, `json`, `dataclasses`, `argparse`, `math`, `pathlib`, `unittest`). No `pip install`, no `virtualenv`, no package manager headaches.
- **Evidence with stated limits:** Research summaries distinguish study findings from coaching choices. Checks detect malformed data and configured-policy violations; they cannot establish physiological safety or an optimal workout.
- **Consensus Literature Integration & Program Synthesis:** Query peer-reviewed sports science via the [Consensus Academic API](https://consensus.app), validate citations offline via `data/consensus_cache.json` (Gate 6), and synthesize custom training programs with automated compiler pre-flight (`scripts/suggest_program.py`).
- **AI Agent Native:** Turn Claude, Antigravity, Gemini, Cursor, Copilot, or Windsurf into your personal strength & conditioning scientist using structured elicitation protocols and compiler-in-the-loop refinement.
- **Idempotent Hevy Synchronization:** Declarative sync engine matches routines by day or title, updating existing routines in place (`PUT`) and creating missing ones (`POST`) without polluting your Hevy library.
- **Time-Cap Simulator:** Estimates warmups, reps, both sides, rests and transitions with an explicit planning range. Compare only matching program versions with logged history; estimates are not guaranteed finish times.

---

## How to Use This Repo

### 1. Setup (Once)

```bash
git clone https://github.com/savvides/hevy-program-generator.git
cd hevy-program-generator
```

- *(Optional — for Hevy sync or workout history)* Set up `HEVY_API_KEY` (offline QA, program synthesis, and cached citation checks work with no API keys):
  1. **Requires Hevy Pro.** Open [`https://hevy.com/settings?developer`](https://hevy.com/settings?developer) in a web browser (not the mobile app), sign in, and click **Generate API Key**.
  2. Run `python3 scripts/setup_hevy.py` to save and verify your key in `.env` (or copy `.env.example` to `.env`, set `HEVY_API_KEY=...`, and run `python3 scripts/setup_hevy.py --check`).
  3. `.env` is gitignored and never committed. *(For live literature queries, you can also add `CONSENSUS_API_KEY` to `.env`.)*
- *(Optional — recommended before committing)* Install the pre-commit privacy hook to block accidental commits of workout logs, custom programs, or secrets:

```bash
python3 scripts/install_hooks.py
```

### 2. Option A: Use Natural Language (AI Assistant)

Open this repository in Claude Code, Antigravity, Gemini CLI, Cursor, GitHub Copilot, or Windsurf. The repo's instruction files ([`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), [`GEMINI.md`](GEMINI.md), and [`.cursorrules`](.cursorrules)) guide the assistant to ask clarifying intake questions when needed, write or edit Python program definitions, run `scripts/qa_program.py`, and handle dry-run or sync when asked.

Copy and adapt any of these prompts — you don't need to mention file names or commands, because the assistant maps plain English to the right scripts and docs automatically:

1. **Build a new program from scratch**
   > *"Design a 3-day full-body program on Mon/Wed/Fri under a 55-minute time cap using a barbell, adjustable bench, dumbbells, and a stationary bike. Account for mild lower-back sensitivity, separate research findings from coaching choices, and make sure all checks pass."*

2. **Modify an existing program**
   > *"In my 2-day starter program, swap Box Squat for a joint-friendly single-leg exercise, keep sessions under 55 minutes without cutting rest times, add a 40-minute Zone 2 bike ride on Sunday, and re-check the program."*

3. **Sync to Hevy & update the printable plan**
   > *"Validate my program, preview what will change in Hevy first, and once I confirm, sync it to Hevy and update the readable workout plan."*

4. **Pull & analyze Hevy workout history**
   > *"Pull my latest Hevy workouts, summarize my recent consistency and top sets, and compare my actual gym times against the program's time estimates."*

5. **Ask evidence or nutrition questions**
   > *"Using this repo's evidence base, what does the research say about rest intervals for hypertrophy and protein intake around morning workouts? Separate study findings and limits from coaching choices."*

### 3. Option B: Use the CLI Directly

```bash
# 1. Validate a program against all 9 QA gates (starter_full_body_2x.py, upper_lower_4x.py, three_day_split_3x.py)
python3 scripts/qa_program.py --program programs/starter_full_body_2x.py

# 2. Synthesize a new program from movement patterns with automatic QA pre-flight
python3 scripts/suggest_program.py --days 3 --time-cap 60 --focus "Strength" --output programs/my_program.py

# 3. Render the readable HTML plan (docs/program.html)
python3 scripts/render_program.py

# 4. Preview Hevy sync without writing, then push routines to Hevy
python3 scripts/build_routines.py --program programs/starter_full_body_2x.py --dry-run
python3 scripts/build_routines.py --program programs/starter_full_body_2x.py

# 5. Pull workout history and print a deterministic lift/frequency summary
python3 scripts/fetch_workouts.py && python3 scripts/analyze_history.py
```

---

## Architecture: Programs as Code

Programs are defined as declarative Python modules conforming to the strict schema enforced by [`scripts/program_loader.py`](scripts/program_loader.py):

```python
"""Example program definition (programs/my_program.py)."""

PROGRAM_METADATA = {
    "title": "Full-Body 2x — Strength & VO2 Max",
    "version": "1.0.0",
    "target_demographic": "General Strength & Longevity (Men 40+)",
    "session_time_cap_minutes": 60,
    "min_recovery_buffer_hours": 48,
    "description": "2-day full-body strength paired with polarized stationary bike cardio.",
}

ROUTINES = [
    {
        "name": "Full-Body A — Squat / Bench / Pull",
        "day_key": "Tuesday",
        "notes": "RPE 8 and warmup ramps are coaching choices; Grgic 2022 supports non-failure training.",
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
                "evidence_citation": "Grgic et al. 2022 (non-failure training; exact RPE and dose are coaching choices)",
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
                "evidence_citation": "Grgic et al. 2022 (failure is not required; accessory effort is a coaching choice)",
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

### Coaching policies and QA limits

The current policy choices and their evidence limits are documented in
[exercise evidence](docs/evidence_base.md) and [nutrition evidence](docs/nutrition_evidence_base.md).
They are not universal physiological invariants. In particular, the 48-hour buffer,
3–18 weighted-set screen and selected rest/warmup scheme are coaching defaults.
A resolved author/year citation does not prove its attached claim.

The [November 2, 2026 review](docs/research/2026-11-02-consensus-review.md)
accounts for all selected papers with source depth and population limits. The
[authority manifest](data/evidence_authority.json) distinguishes
selected sources, eight explicit program-citation supplements and background cache
material. Original-paper checks qualify exported takeaways. API queries and ordinary
document mentions do not promote a background source into the authority.

Run `python3 scripts/qa_program.py --program <path>` before syncing. A successful
scorecard means configured checks passed, not “100% compliant with sports science.”
Actual recovery, training outcomes and individual suitability still require review.

The default [readable plan](docs/program.html) is generated from
`programs/starter_full_body_2x.py`, including set counts, instructions and time estimates:

```bash
python3 scripts/render_program.py
python3 scripts/render_program.py --check
```

A unilateral prescription such as `6-8 per side` or `30-45s per side` means both
sides before logging one set and taking the prescribed rest. Invalid text stops
export instead of silently becoming five reps.

### Individual Evaluation Lanes

```bash
python3 scripts/test_program_loader.py                           # Schema validation & resolution unit tests
python3 scripts/test_build_routines.py --program <path>          # Structural assertions & catalog resolution
python3 scripts/eval_program_volume.py --program <path>          # configured weighted-volume bounds
python3 scripts/eval_recovery_interference.py --program <path>  # configured spacing and cardio accounting
python3 scripts/estimate_session_time.py --program <path>        # Gym duration simulator vs time cap
python3 scripts/calibrate_session_time.py --program <path>       # Model vs actual logged wall clock
python3 scripts/eval_evidence_grounding.py --program <path>      # Deterministic evidence & Consensus citation gate
```

---

## Consensus Academic Literature Integration & Program Suggester

`hevy-program-generator` integrates directly with the [Consensus Academic API](https://consensus.app) to ground training prescriptions in peer-reviewed scientific studies. A local, offline-first citation cache (`data/consensus_cache.json`) ensures fast, zero-credit evaluations without network requests.

### Configuration

Add your optional Consensus API key to `.env` (offline queries and pre-cached citations require no key):

```bash
cp .env.example .env
# Edit .env:
CONSENSUS_API_KEY=your_consensus_api_key_here
```

### Querying Literature via CLI

Search sports science literature or inspect cached studies:

```bash
# Query literature with instant caching (or 0-credit offline cache hit)
python3 scripts/consensus_client.py --query "seated leg curl lengthened hamstring" --limit 3

# Inspect study by DOI from local cache
python3 scripts/consensus_client.py --doi "10.1249/MSS.0000000000002523"

# Format markdown citation for evidence documentation
python3 scripts/consensus_client.py --query "rest intervals hypertrophy" --format markdown
```

### Synthesizing Programs with Pre-Flight QA (`scripts/suggest_program.py`)

Generate a customized, evidence-grounded program tailored to specific weekly days, time caps, and joint constraints. The generator automatically validates movement patterns against the Hevy catalog and executes `scripts/qa_program.py` pre-flight checks before saving:

```bash
# Synthesize an adult split with explicit reported context and a 60-minute time cap
python3 scripts/suggest_program.py --days 3 --time-cap 60 --focus "Strength" --age-years 46 --sex "male" --primary-goal "strength" --output programs/my_program.py
```

Optional `age_years`, `sex` and `primary_goal` describe reported context. Omitted
values stay unknown; a focus/title such as "Men 40+" does not supply them. No automatic
training or calorie dose follows. Explicit ages under 18 stop the adult generator.
Joint-profile labels preserve selection constraints and do not provide clinical clearance.

---

## AI Agent Pair-Programming Workflow

`hevy-program-generator` is engineered for autonomous AI development. Detailed operating standards are built into [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), and [`GEMINI.md`](GEMINI.md).

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Lifter Elicitation (Days, Time Cap, Equipment, Goals)    │
│    Agent conducts structured intake assessment              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Synthesize Program Definition                            │
│    Agent writes custom program to programs/my_program.py    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Run Pre-Flight QA Gatekeeper                             │
│    python3 scripts/qa_program.py --program <path>           │
└──────────────────────────────┬──────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
       [ QA Errors ✗ ]                   [ QA Green ✓ ]
              │                                 │
              ▼                                 ▼
┌───────────────────────────┐    ┌────────────────────────────┐
│ 4. Autonomous Refinement  │    │ 5. Dry-Run & Hevy Sync     │
│    Fix volume, RPE, rest, │    │    python3                 │
│    spacing, or time cap   │    │    scripts/build_routines  │
│    Loop back to Step 3    │    │    .py --program <path>    │
└───────────────────────────┘    └────────────────────────────┘
```

---

## Hevy Cloud Sync & Workout History

> **Need an API key?** See [Setup (Once)](#1-setup-once) or run `python3 scripts/setup_hevy.py` (verify an existing key with `python3 scripts/setup_hevy.py --check`).

### Pulling Workout Logs & Privacy Isolation

Sync your full Hevy workout history into local, gitignored JSON files:

```bash
python3 scripts/fetch_workouts.py

# Or isolate logs completely outside the repository directory:
python3 scripts/fetch_workouts.py --data-dir ~/.hevy/workouts
# Or via environment variable:
export HEVY_DATA_DIR=~/.hevy/workouts
```

- Paginates through `GET /v1/workouts` (`pageSize=10`).
- Stores each session in `data/workouts/<workout_id>.json` (gitignored) or your designated `HEVY_DATA_DIR`.
- Automated pre-commit privacy gatekeeper (`scripts/check_privacy_leaks.py`) blocks accidental staging of session files, API keys, or custom routines. Install it with:
  ```bash
  python3 scripts/install_hooks.py
  ```

### Pushing Program Routines

Push your program definition to Hevy:

```bash
python3 scripts/build_routines.py --program programs/starter_full_body_2x.py
```

- Automatically runs `qa_program.py` pre-flight checks before touching the network.
- Resolves prescribed exercise names against cached templates (`data/exercise_templates.json`) using token similarity.
- Reconciles routines by weekday key or title: performs `PUT` for updates and `POST` for new routines.
- Reports orphaned/stale routines for manual cleanup in the Hevy app (the Hevy API does not expose a routine deletion endpoint).

---

## Evidence & Knowledge Base

The local knowledge base that informs program generation and citation verification lives in five files:

- [Exercise evidence](docs/evidence_base.md) — synthesized resistance-training and cardio guidance with study populations and limits.
- [Nutrition evidence](docs/nutrition_evidence_base.md) — protein, energy-deficit, and fueling guidance.
- [November 2, 2026 Consensus review](docs/research/2026-11-02-consensus-review.md) — 100-paper corpus index with DOIs, populations, policy notes, and appraisal depth.
- [Evidence authority manifest](data/evidence_authority.json) — machine-readable corpus allowlist and program-citation supplements.
- [Consensus bibliographic cache](data/consensus_cache.json) — offline-first bibliographic metadata for 309 papers (`doi`, `citation_key`, `authors`, `title`, `year`, `journal`, `consensus_url`) used by Gate 6 without network requests or verbatim third-party text.

Cached metadata and unappraised records do not certify a prescription.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, evidence requirements, and local QA checks before opening a pull request.

---

## Disclaimer

This software is provided for educational and training-planning purposes only. It is not medical advice, physical therapy, or clinical clearance, and automated QA checks do not establish individual physiological safety or optimal programming.

---

## License & Third-Party Notices

- Repository source code and original documentation are licensed under the [MIT License](LICENSE) (`Copyright (c) 2026 Philippos Savvides`).
- Built-in exercise catalog entries in [`data/exercise_templates.json`](data/exercise_templates.json) and bibliographic records in [`data/consensus_cache.json`](data/consensus_cache.json) support local validation; optional cloud integrations use the [Hevy API](https://api.hevyapp.com/docs/) and [Consensus Academic API](https://consensus.app) under their respective terms of service and do not redistribute verbatim third-party paper abstracts or takeaways.
