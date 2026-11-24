#!/usr/bin/env python3
"""Install repository git hooks (e.g. pre-commit privacy gatekeeper)."""
from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HOOK_CONTENT = """#!/bin/sh
# Automated privacy & secret leak gatekeeper
exec python3 scripts/check_privacy_leaks.py
"""


def install_hooks(repo_root: Path = REPO_ROOT) -> int:
    # Ask git where it reads hooks: .git is a file in a linked worktree, and
    # core.hooksPath can point anywhere.
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"error: cannot locate the git hooks directory: {result.stderr.strip()}", file=sys.stderr)
        return 1
    hooks_dir = Path(result.stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = repo_root / hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook = hooks_dir / "pre-commit"
    if hook.exists() and hook.read_text() != HOOK_CONTENT:
        print(
            f"error: {hook} already exists and is not this hook; not overwriting it. "
            "Merge the call to scripts/check_privacy_leaks.py into it by hand.",
            file=sys.stderr,
        )
        return 1

    hook.write_text(HOOK_CONTENT)
    # Ensure hook is executable (chmod +x)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Installed pre-commit privacy hook: {hook}")
    return 0


if __name__ == "__main__":
    sys.exit(install_hooks())
