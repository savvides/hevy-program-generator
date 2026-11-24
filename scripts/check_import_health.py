#!/usr/bin/env python3
"""QA gate: every module compiles and imports, and every CLI can build its parser.

Several scripts in this repo are executed by nothing — not CI, not qa_program.py.
A syntax error, a stale import, or a typo at module scope in one of those sits
undetected until someone reaches for the script. This gate exercises the import
path of every module in scripts/ and programs/, and runs --help on every argparse
entry point, so that class of rot fails here instead.

--help is used deliberately: argparse exits before main() runs, so the check is
side-effect free while still forcing the import and the parser construction.

Exits 0 when everything imports and every CLI responds to --help; 1 otherwise.
"""
from __future__ import annotations

import ast
import compileall
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
SOURCE_DIRS = (REPO_ROOT / "scripts", REPO_ROOT / "programs")
TIMEOUT_SECONDS = 30


def python_files() -> list[Path]:
    """Every Python module this repo ships, in a stable order."""
    return sorted(p for d in SOURCE_DIRS for p in d.glob("*.py"))


def uses_argparse(path: Path) -> bool:
    """True when the module actually imports argparse.

    Parsed rather than substring-matched: this module and its test both mention
    argparse in prose and in string literals, and a naive match made the gate
    run itself with --help until it timed out.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "argparse" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == "argparse":
            return True
    return False


def check_file(path: Path) -> tuple[bool, str]:
    """Import the module — and build its parser if it has one — in a subprocess.

    A subprocess keeps one module's import-time state from masking another's.
    """
    if uses_argparse(path):
        cmd = [sys.executable, str(path), "--help"]
    else:
        cmd = [sys.executable, "-c", f"import {path.stem}"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(path.parent),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {TIMEOUT_SECONDS}s"
    if result.returncode == 0:
        return True, ""
    lines = (result.stderr or result.stdout).strip().splitlines()
    return False, lines[-1] if lines else f"exited {result.returncode} with no output"


def main() -> int:
    # quiet=1 prints syntax errors but not per-file chatter. quiet=2 would
    # swallow the errors this message points at.
    # A list, not a generator: all() would short-circuit and hide a syntax error
    # in programs/ behind one in scripts/. Report every directory.
    compiled = all(
        [compileall.compile_dir(str(d), quiet=1, force=True) for d in SOURCE_DIRS]
    )
    if not compiled:
        print("  Import health: a module failed to compile — see the error above.")
        return 1

    failures: list[tuple[Path, str]] = []
    files = python_files()
    for path in files:
        ok, detail = check_file(path)
        if not ok:
            failures.append((path, detail))

    if failures:
        print(f"  Import health: {len(failures)} of {len(files)} modules FAILED.")
        for path, detail in failures:
            print(f"    {path.relative_to(REPO_ROOT)}: {detail}")
        return 1

    clis = sum(1 for p in files if uses_argparse(p))
    print(
        f"  Import health: {len(files)} modules compile and import; "
        f"{clis} CLI parsers build."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
