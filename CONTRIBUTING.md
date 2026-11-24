# Contributing to Hevy Program Generator

Contributions are welcome under the [MIT License](LICENSE).

## Guidelines

1. **Zero external runtime dependencies:** Keep all Python scripts strictly on the Python 3 standard library.
2. **Evidence and citation policy:** Cite primary peer-reviewed sources for new training or nutrition claims, state population scope and limitations, and never invent support for a coaching choice.
3. **Synthetic data only:** Never commit personal health records, workout logs (`data/workouts/*.json`), `.env` secrets, or personal Hevy custom exercise templates.
4. **Verification:** Run `python3 scripts/qa_program.py`, `python3 scripts/check_privacy_leaks.py --all`, and `python3 -m unittest discover -s scripts -p "test_*.py"` before opening a pull request.

## Documentation

- [`README.md`](README.md): Engine overview, setup, and CLI reference
- [`AGENTS.md`](AGENTS.md): Universal AI agent operating standards and invariants
- [`docs/architecture.md`](docs/architecture.md): System architecture and mathematical evaluation models
- [`docs/evidence_base.md`](docs/evidence_base.md): Exercise physiology and biomechanics literature ground truth
- [`docs/nutrition_evidence_base.md`](docs/nutrition_evidence_base.md): Nutritional physiology and bioenergetics literature ground truth
