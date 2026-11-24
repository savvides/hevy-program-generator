#!/usr/bin/env python3
"""QA gate: validate data/consensus_cache.json row invariants.

Exits 0 when every cached paper has a canonical, unique citation key, an
integer year, and an id that matches its lowercased DOI. Exits 1 otherwise.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(SCRIPTS_DIR), pattern="test_consensus_cache.py"
    )
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
    if result.testsRun == 0:
        print("  Cache schema: no tests ran — test_consensus_cache.py is missing or renamed.")
        return 1
    if result.wasSuccessful():
        print("  Cache schema: all row invariants hold.")
        return 0
    print("  Cache schema: INVARIANT VIOLATED — see failures above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
