# GEMINI.md

This file provides guidance to Google Antigravity / Gemini CLI when working with code in this repository.

## Operating standards

Global standards (how-to-work mindset, latent-vs-deterministic split, gate-test/eval lanes,
completion protocol, safety, communication style) apply to all coding sessions. This file covers
what is specific to this repo.

## What this is

Open-source evidence-grounded Hevy program generator (`hevy-program-generator`):
1. **Define & Validate** training programs in Python with deterministic structure and coaching-policy checks.
2. **Push** the training program up to Hevy as a routine folder + routines (`scripts/build_routines.py`).
3. **Pull** workout history down into gitignored local storage (`scripts/fetch_workouts.py`).
4. **Ground & Validate** exercise citations against peer-reviewed literature via Consensus Academic API & local cache (`scripts/consensus_client.py`, `scripts/eval_evidence_grounding.py`).
5. **Synthesize** custom evidence-grounded programs with automated compiler pre-flight (`scripts/suggest_program.py`).

Python 3, standard library only — zero external dependencies, no virtual environment required, no Makefile, no package manager. Entry points are direct `python3 scripts/*.py` calls.

## Evidence and citation policy

Use [exercise evidence](docs/evidence_base.md) and [nutrition evidence](docs/nutrition_evidence_base.md), checking the original paper when making a new claim. Cite evidence for exercise selection, volume, RPE/RIR, warmups, rests, cardio, spacing and nutrition recommendations. State what the study supports, its population and relevant limitations. Label exact coaching choices as such; never invent support for a number to satisfy a citation gate.

Software verifies structure, citation resolution and configured policies. A green result is not scientific validation, medical clearance or proof of optimal programming. Do not reinstate the superseded universal 48-hour, 80/20-minute, 20-minute HIIT-floor, 18-set age ceiling, mandatory failure, mandatory fed-state or whole-food-quota claims. See the evidence documents for corrected interpretations.

## Commands

```bash
# Setup (once): configure HEVY_API_KEY (requires Hevy Pro, https://hevy.com/settings?developer)
python3 scripts/setup_hevy.py                                         # interactive setup + verification
python3 scripts/setup_hevy.py --check                                 # verify configured HEVY_API_KEY

# Master QA Gate (runs unit tests, volume evals, interference/recovery evals, time model, evidence grounding)
python3 scripts/qa_program.py                                         # evaluates active/default program
python3 scripts/qa_program.py --program programs/starter_full_body_2x.py
python3 scripts/qa_program.py --program programs/three_day_split_3x.py
python3 scripts/qa_program.py --program programs/upper_lower_4x.py

# Push program → Hevy (runs qa_program.py pre-flight automatically)
python3 scripts/build_routines.py --dry-run                           # preview reconcile + payloads, no writes
python3 scripts/build_routines.py --program programs/starter_full_body_2x.py --dry-run
python3 scripts/build_routines.py                                     # sync active program to Hevy
python3 scripts/build_routines.py --folder "<title>"                  # override the folder name

# Consensus Academic Literature queries & cache inspection (zero credit offline hits)
python3 scripts/consensus_client.py --query "seated leg curl lengthened hamstring"
python3 scripts/consensus_client.py --doi "10.1249/MSS.0000000000002523"
python3 scripts/consensus_client.py --query "rest intervals hypertrophy" --format markdown
python3 scripts/update_literature.py --dry-run                        # preview annual Consensus DOI refresh & discovery
python3 scripts/update_literature.py --refresh-existing --discover    # refresh approved DOIs + discover new papers

# Synthesize evidence-grounded program with automated QA pre-flight
python3 scripts/suggest_program.py --days 3 --time-cap 60 --focus "Men 40+" --output programs/three_day_split_3x.py

# Pull workout history → data/workouts/<id>.json (or HEVY_DATA_DIR)
python3 scripts/fetch_workouts.py

# Privacy & Secret Gatekeeper
python3 scripts/install_hooks.py                                      # install pre-commit leak gatekeeper
python3 scripts/check_privacy_leaks.py --all                          # verify zero secret or workout leaks

# Individual gate tests & evals (accept --program flag)
python3 scripts/test_program_loader.py                                # schema loader unit tests
python3 scripts/test_check_privacy_leaks.py                           # privacy gatekeeper unit tests
python3 scripts/test_consensus_cache.py                               # consensus cache schema tests
python3 scripts/test_consensus_client.py                              # consensus API client unit tests
python3 scripts/test_eval_evidence_grounding.py                       # evidence grounding gate tests
python3 scripts/test_suggest_program.py                               # program synthesis unit tests
python3 scripts/test_build_routines.py --program <path>               # payload & structural asserts
python3 scripts/eval_program_volume.py --program <path>               # weekly weighted sets vs configured bounds
python3 scripts/eval_recovery_interference.py --program <path>        # configured spacing and classified cardio dose
python3 scripts/estimate_session_time.py --program <path>             # per-session minutes vs time cap
python3 scripts/calibrate_session_time.py --program <path>            # model vs ACTUAL logged wall clock
python3 scripts/eval_evidence_grounding.py --program <path>           # Gate 6 deterministic citation grounding
python3 scripts/check_cache_schema.py                                 # Gate 7 cache schema integrity
python3 scripts/check_import_health.py                                # Gate 8 import & CLI health
python3 scripts/check_writing_standard.py --program <path>            # Gate 9 ASD-STE100 + BLUF text rules (opt-in)
python3 scripts/render_program.py --check                             # verify readable HTML plan drift
python3 -m unittest discover -s scripts -p "test_*.py"                # run all 200+ unit tests
```

`qa_program.py` executes all gates in one command and exits non-zero if any invariant is violated.
All gates must stay green before any program sync.

## Architecture

- **The program is code, not data.** Pluggable program definitions live in `programs/` (e.g. `programs/starter_full_body_2x.py` — the default program — `programs/upper_lower_4x.py`, `programs/three_day_split_3x.py`, or custom `programs/program.py`). The program loader (`scripts/program_loader.py`) dynamically resolves the program from `--program`, `HEVY_PROGRAM` env var, `programs/program.py`, or the active default.
- **Tests and evals read the same source.** `test_build_routines.py`, `eval_program_volume.py`, `eval_recovery_interference.py`, `estimate_session_time.py`, and `eval_evidence_grounding.py` all consume the resolved program definition, ensuring immediate evaluation coverage.
- **Offline-first Consensus cache (`data/consensus_cache.json`).** Pre-seeded with bibliographic metadata for core studies from `docs/evidence_base.md`. Gate 6 (`eval_evidence_grounding.py`) resolves citation entries without an API key or network access; it does not validate whether claims follow from papers. Live API calls (`--verify-online`) query the Consensus Academic API and cache responses with DOI deduplication.
- **First-Principles Movement Pattern Registry (`scripts/movement_patterns.py`) & Synthesis (`scripts/suggest_program.py`).** Programs must never be cloned or anchored to existing repository templates. The synthesizer dynamically satisfies the 8 fundamental human movement patterns (Squat, Hinge, Horizontal Push/Pull, Vertical Push/Pull, Unilateral/Multi-Planar Lower, Joint Integrity/Core) mapped directly to lifter constraints (equipment, joint profile, tier) via constraint scoring, validating against the Hevy catalog and running `qa_program.py` pre-flight before outputting.
- **Training policies:** Follow `AGENTS.md` and the corrected evidence documents for qualified defaults. `compound` selects the heavy-slot policy, not anatomy. Warmup weights are not exported. Rest, recovery and volume checks are planning rules, not safety guarantees.
- **Isolation warmup invariant:** `test_isolations_have_no_warmups` requires `warmup_reps` to be `None` or `[]` whenever `compound: False` (even for multi-joint accessories like `Chin Up (Weighted)`). Put unlogged warmup cues in `general_notes` or `notes`.
- **Single source of truth & schedule sync:** `python3 scripts/render_program.py` renders `docs/program.html` (`--check` detects drift).
- **Exercise resolution is fuzzy.** Prescribed names are matched against the cached Hevy catalog (`data/exercise_templates.json`, 30-day TTL) via token-overlap scoring. Unresolved names print candidate titles and abort before writes.
- **The sync is idempotent.** `plan_reconcile` matches desired routines to existing ones by `routine_key` (weekday prefix or normalized title). Match → PUT update in place; no match → POST create.

## Hevy API Gotchas (All Confirmed in Code)

- **No DELETE** for routines — stale/extra routines are reported for manual cleanup in the mobile app.
- **PUT rejects `routine.folder_id`** — set `folder_id` only on the initial POST that creates a routine.
- **pageSize ≤ 10** for `/routines` and `/workouts`; **≤ 100** for `/exercise_templates`.
- **Supersets:** Exercises sharing the same integer `superset` field emit one `superset_id` (`None` = solo lift).
- **Notes are write-only** — synced up, not read back during reconcile.
- **`HEVY_API_KEY`** comes from `.env` or the environment; scripts exit non-zero if missing. `.env` is gitignored.

## Data & Privacy

- `data/workouts/` — fetched session JSON (gitignored; `.gitkeep` committed). Override via `HEVY_DATA_DIR` or `--data-dir` to isolate outside repository.
- `data/exercise_templates.json` — cached Hevy catalog, committed so matching and tests work offline.
- `data/consensus_cache.json` — cached literature database, committed and scanned by `scripts/check_privacy_leaks.py` for zero API keys or authorization tokens.
- `scripts/check_privacy_leaks.py` — pre-commit privacy gatekeeper preventing accidental commit of secrets, workout logs, or custom programs.
