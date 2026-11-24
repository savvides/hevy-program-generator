# Changelog

All notable changes to **Hevy Program Generator** (`hevy-program-generator`) are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

### Added
- **Zero-dependency Python 3 standard library engine (`scripts/`):**
  - Program loader & schema validator (`program_loader.py`), first-principles movement pattern registry (`movement_patterns.py`), and constraint-based program synthesizer (`suggest_program.py`).
  - Nine deterministic QA gates (`qa_program.py`): catalog integrity, session time-cap simulation (`estimate_session_time.py`), volume screening (`eval_program_volume.py`), recovery spacing & cardio accounting (`eval_recovery_interference.py`), heavy-lift RPE ceiling, offline citation grounding (`eval_evidence_grounding.py`), cache schema integrity (`check_cache_schema.py`), import/CLI health (`check_import_health.py`), and opt-in ASD-STE100 + BLUF writing standard (`check_writing_standard.py`).
  - Optional Hevy REST API idempotent reconciliation (`build_routines.py`) and workout history export/calibration (`fetch_workouts.py`, `calibrate_session_time.py`, `analyze_history.py`).
  - Optional Consensus Academic API client & annual literature refresh workflow (`consensus_client.py`, `update_literature.py`).
  - Deterministic energy-balance & body-composition tracker (`track_deficit.py`), pre-commit privacy leak gatekeeper (`check_privacy_leaks.py`, `install_hooks.py`), and readable HTML plan renderer (`render_program.py`).
- **Evidence & Knowledge Base:**
  - Synthesized exercise and nutrition guidance (`docs/evidence_base.md`, `docs/nutrition_evidence_base.md`).
  - 100-paper literature review index (`docs/research/2026-11-02-consensus-review.md`), authority manifest (`data/evidence_authority.json`), and 309-record offline bibliographic cache (`data/consensus_cache.json`).
- **Shipped Example Programs (`programs/`):**
  - `starter_full_body_2x.py` (default), `three_day_split_3x.py`, and `upper_lower_4x.py`, plus rendered HTML plan (`docs/program.html`).
- **Open-Source Release & CI:**
  - MIT License (`LICENSE`), contribution guide (`CONTRIBUTING.md`), agent instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`), and GitHub Actions CI workflow (`.github/workflows/ci.yml` covering `ruff`, `mypy`, and Python 3.10–3.13 QA suites).
