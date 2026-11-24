# CLAUDE.md

This repository follows the universal agent operating standard documented in [AGENTS.md](AGENTS.md).

All AI coding assistants (Claude Code, Google Antigravity, Gemini CLI, Cursor, etc.) must adhere to `AGENTS.md` as the authoritative specification for:
- Agent persona, zero-dependency mandate, and first-principles program synthesis
- Scientific evidence and citation policies (`docs/evidence_base.md`, `docs/nutrition_evidence_base.md`)
- User-facing ASD-STE100 writing standard and BLUF formatting
- Lifter intake & nutrition elicitation protocol
- Autonomous program verification loop and schema contract (`scripts/qa_program.py`)
- Hevy API sync constraints and idempotency rules

## Commands Quick Reference

```bash
# Master QA Gate (all 9 compiler gates)
python3 scripts/qa_program.py

# Push active program to Hevy (dry-run preview)
python3 scripts/build_routines.py --dry-run

# Privacy & secret leak check
python3 scripts/check_privacy_leaks.py --all

# Run full test suite
python3 -m unittest discover -s scripts -p "test_*.py"
```

For detailed CLI workflows, architecture guidelines, and Hevy API gotchas, consult [GEMINI.md](GEMINI.md) and [AGENTS.md](AGENTS.md).
