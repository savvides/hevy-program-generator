#!/usr/bin/env python3
"""Pre-commit privacy and data leak gatekeeper for hevy-program-generator.

Ensures that private workout logs, API keys, credentials, and personal
program files are never staged or committed to git.

Usage:
  python3 scripts/check_privacy_leaks.py           # Check staged git files (default for pre-commit)
  python3 scripts/check_privacy_leaks.py --all     # Audit all tracked files in git repository
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Patterns for files that MUST NOT be committed
FORBIDDEN_FILE_PATTERNS = [
    (re.compile(r"^data/workouts/(?!(\.gitkeep)$).+", re.IGNORECASE), "Personal workout session data (data/workouts/*.json)"),
    # Any depth; the lookahead keeps .env.example allowed without exempting it from the other rules.
    (re.compile(r"(?:^|/)\.env(?!\.example$)(\..+)?$", re.IGNORECASE), "Environment secret file (.env, .env.*) [use .env.example instead]"),
    (re.compile(r"^programs/program\.py$", re.IGNORECASE), "User private program definition (programs/program.py)"),
]

# Pattern for detecting hardcoded API key assignments
API_KEY_REGEX = re.compile(
    # Name forms: os.environ["HEVY_API_KEY"] =, api_key: str =, apiKey =, HEVY_KEY=.
    r"""["']?(?:HEVY_[A-Z_]*KEY|CONSENSUS_API_KEY|api[-_]?key)["']?\]?(?:\s*:\s*[A-Za-z_][\w.\[\]]*)?\s*[:=]\s*\\?["']?([a-zA-Z0-9_\-]{20,})\\?["']?""",
    re.IGNORECASE,
)
BEARER_TOKEN_REGEX = re.compile(
    r"""bearer\s+([a-zA-Z0-9_\-\.]{20,})""",
    re.IGNORECASE,
)
BENIGN_KEY_PLACEHOLDERS = {
    "your_hevy_api_key_here",
    "your_consensus_api_key_here",
    "your_api_key_here",
    "placeholder",
    "dummy_key",
    "test_key",
}

CONSENSUS_CACHE_SECRET_REGEX = re.compile(
    r"""["'](?:api[-_]?key|access[-_]?token|auth[-_]?token|secret)["']\s*:\s*["']([^"']{10,})["']""",
    re.IGNORECASE,
)
EMAIL_REGEX = re.compile(
    r"""\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"""
)
RESEARCH_SOURCE_PATHS = {
    "data/consensus_cache.json",
}


def get_staged_files() -> list[str]:
    """Return list of staged file paths relative to repo root."""
    # --diff-filter=d keeps renames and copies; -z stops git quoting unusual names.
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=d"],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return [name for name in res.stdout.split("\0") if name]


def get_tracked_files() -> list[str]:
    """Return list of all tracked file paths relative to repo root."""
    res = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return [name for name in res.stdout.split("\0") if name]


def check_file_path(path_str: str) -> list[str]:
    """Check whether a path violates forbidden file rules."""
    normalized = path_str.replace("\\", "/")
    errors = []
    for pattern, desc in FORBIDDEN_FILE_PATTERNS:
        if pattern.search(normalized):
            errors.append(f"Forbidden file tracked/staged: '{normalized}' ({desc})")
    return errors


def check_consensus_cache(
    file_path: Path | str | None = None,
    content: str | None = None,
) -> list[str]:
    """Scan consensus_cache.json for API keys, Bearer tokens, or personal identifiers."""
    errors = []
    if content is None:
        target_path = Path(file_path) if file_path else (REPO_ROOT / "data/consensus_cache.json")
        if not target_path.is_file():
            return []
        try:
            content = target_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        try:
            display_name = str(target_path.relative_to(REPO_ROOT))
        except ValueError:
            display_name = str(target_path)
    else:
        display_name = str(file_path) if file_path else "data/consensus_cache.json"

    for line_idx, line in enumerate(content.splitlines(), start=1):
        match = API_KEY_REGEX.search(line)
        if match:
            key_val = match.group(1).lower()
            if not any(ph in key_val for ph in BENIGN_KEY_PLACEHOLDERS):
                errors.append(
                    f"Possible secret API key detected in '{display_name}' at line {line_idx}."
                )

        bearer_match = BEARER_TOKEN_REGEX.search(line)
        if bearer_match:
            token_val = bearer_match.group(1).lower()
            if not any(ph in token_val for ph in BENIGN_KEY_PLACEHOLDERS):
                errors.append(
                    f"Possible Bearer token detected in '{display_name}' at line {line_idx}."
                )

        secret_match = CONSENSUS_CACHE_SECRET_REGEX.search(line)
        if secret_match:
            val = secret_match.group(1).lower()
            if not any(ph in val for ph in BENIGN_KEY_PLACEHOLDERS):
                errors.append(
                    f"Possible secret or auth token detected in '{display_name}' at line {line_idx}."
                )

        for email_match in EMAIL_REGEX.finditer(line):
            # The original publisher copyright notice is part of the immutable
            # selected export. This exact public contact is not a personal identifier.
            if (display_name in RESEARCH_SOURCE_PATHS
                    and email_match.group(0) == "journals.permissions@oup.com"
                    and line[:email_match.start()].endswith("For permissions, please e-mail: ")):
                continue
            errors.append(
                f"Personal identifier (email: {email_match.group(0)}) detected in '{display_name}' at line {line_idx}."
            )

    return errors


def check_file_content(path_str: str, staged: bool = False) -> list[str]:
    """Scan text file content for raw API keys.

    With staged=True the index copy is scanned, since that is what gets committed.
    Read failures raise (OSError or CalledProcessError) so main() can fail closed.
    """
    full_path = REPO_ROOT / path_str

    # Skip non-text or binary files
    if full_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".zip"}:
        return []

    if staged:
        content = subprocess.run(
            ["git", "cat-file", "blob", f":0:{path_str}"],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        ).stdout
    else:
        if not full_path.is_file():
            return []
        content = full_path.read_text(encoding="utf-8", errors="ignore")

    normalized = path_str.replace("\\", "/")
    if normalized in RESEARCH_SOURCE_PATHS:
        return check_consensus_cache(file_path=normalized, content=content)

    errors = []

    for line_idx, line in enumerate(content.splitlines(), start=1):
        match = API_KEY_REGEX.search(line)
        if match:
            key_val = match.group(1).lower()
            if not any(ph in key_val for ph in BENIGN_KEY_PLACEHOLDERS):
                errors.append(
                    f"Possible secret API key detected in '{path_str}' at line {line_idx}."
                )
        bearer_match = BEARER_TOKEN_REGEX.search(line)
        if bearer_match:
            token_val = bearer_match.group(1).lower()
            if not any(ph in token_val for ph in BENIGN_KEY_PLACEHOLDERS):
                errors.append(
                    f"Possible Bearer token detected in '{path_str}' at line {line_idx}."
                )
    return errors


def run_checks(files_to_check: list[str], staged: bool = False) -> list[str]:
    violations: list[str] = []
    for file_path in files_to_check:
        path_errors = check_file_path(file_path)
        violations.extend(path_errors)
        if not path_errors:
            violations.extend(check_file_content(file_path, staged=staged))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Audit all tracked files in git instead of only staged files",
    )
    args = parser.parse_args(argv)

    try:
        if args.all:
            files = get_tracked_files()
            mode_desc = "all tracked git files"
        else:
            files = get_staged_files()
            mode_desc = "staged git files"

        if not files:
            print(f"Privacy Gatekeeper: No {mode_desc} to verify.")
            return 0

        violations = run_checks(files, staged=not args.all)
    except (OSError, subprocess.CalledProcessError) as exc:
        # Exit 2 (scanner error), never 0: an incomplete scan must not pass the commit.
        detail = (getattr(exc, "stderr", None) or "").strip()
        print(f"Privacy Gatekeeper: ERROR, scan did not complete: {exc} {detail}".rstrip(), file=sys.stderr)
        return 2

    if violations:
        print("=" * 80, file=sys.stderr)
        print("PRIVACY & SECRET LEAK GATEKEEPER: FAILED", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        for v in violations:
            print(f"  ✗ {v}", file=sys.stderr)
        print("\nRemediation:", file=sys.stderr)
        print("  1. Unstage the sensitive file: git reset HEAD <file>", file=sys.stderr)
        print("  2. Store personal workouts in an external dir (export HEVY_DATA_DIR=~/.hevy)", file=sys.stderr)
        print("  3. Keep custom routines in gitignored 'programs/program.py'", file=sys.stderr)
        print("  4. Keep secrets in gitignored '.env'", file=sys.stderr)
        print("  5. Verify data/consensus_cache.json contains no API keys or tokens", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        return 1

    print(f"Privacy Gatekeeper: Checked {len(files)} {mode_desc} — ZERO leaks detected. [ PASS ]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
