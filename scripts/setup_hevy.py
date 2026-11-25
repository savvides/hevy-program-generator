#!/usr/bin/env python3
"""Interactive setup and verification for HEVY_API_KEY. Stdlib only."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.hevyapp.com/v1"
DEVELOPER_SETTINGS_URL = "https://hevy.com/settings?developer"
REPO_ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER_KEYS = {
    "your-key-here",
    "your_key_here",
    "your-api-key-here",
    "your_api_key_here",
    "your-hevy-api-key-here",
    "your_hevy_api_key_here",
    "placeholder",
    "<your-api-key>",
    "changeme",
}
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError)


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ without overwriting."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_placeholder_key(value: str | None) -> bool:
    """Return True when the API key is missing, blank, or an unedited template value."""
    if value is None:
        return True
    cleaned = value.strip()
    return not cleaned or cleaned.lower() in PLACEHOLDER_KEYS


def missing_key_message(api_key: str | None) -> str:
    """Return an actionable setup message for a missing or placeholder HEVY_API_KEY."""
    if api_key is not None and api_key.strip():
        header = "error: HEVY_API_KEY is still set to a template placeholder."
    else:
        header = "error: HEVY_API_KEY is not set."
    return (
        f"{header}\n"
        f"  1. Hevy Pro is required. Open {DEVELOPER_SETTINGS_URL} in a web browser\n"
        f"     (not the mobile app), sign in, and click 'Generate API Key'.\n"
        f"  2. Run 'python3 scripts/setup_hevy.py' to save and verify your key in .env,\n"
        f"     or copy .env.example to .env and set HEVY_API_KEY=<your-key>."
    )


def auth_error_hint(status_code: int) -> str:
    """Return a concise recovery hint when Hevy rejects an API key (401/403)."""
    return (
        f"Hevy rejected the API key (HTTP {status_code}). Confirm you have an active "
        f"Hevy Pro subscription, regenerate your key at {DEVELOPER_SETTINGS_URL}, "
        f"and run 'python3 scripts/setup_hevy.py' to update .env."
    )


def verify_api_key(api_key: str) -> tuple[bool, str]:
    """Verify a Hevy API key with a read-only GET /v1/workouts/count request."""
    url = f"{API_BASE}/workouts/count"
    req = urllib.request.Request(
        url,
        headers={"api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, f"HTTP {e.code}: {auth_error_hint(e.code)}"
        detail = e.read().decode("utf-8", "replace").strip()
        suffix = f" — {detail}" if detail else ""
        return False, f"HTTP {e.code}{suffix}"
    except NETWORK_ERRORS as e:
        return False, f"Could not reach Hevy API ({e}). Check your network connection and try again."

    count = data.get("workout_count") if isinstance(data, dict) else None
    if isinstance(count, int):
        return True, f"Hevy API key verified ({count} logged workouts found)."
    return True, "Hevy API key verified."


def write_env_key(env_path: Path, api_key: str, example_path: Path | None = None) -> None:
    """Create or update HEVY_API_KEY in env_path while preserving other entries."""
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    elif example_path is not None and example_path.exists():
        lines = example_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    new_lines: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if not replaced and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() == "HEVY_API_KEY":
                new_lines.append(f"HEVY_API_KEY={api_key}")
                replaced = True
                continue
        new_lines.append(line)

    if not replaced:
        new_lines.append(f"HEVY_API_KEY={api_key}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    if os.name == "posix":
        os.chmod(env_path, 0o600)


def _display_env_path(env_path: Path) -> str:
    try:
        return str(env_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(env_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set up and verify HEVY_API_KEY in .env for Hevy API sync."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the configured HEVY_API_KEY without prompting",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: .env in repository root)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Save the key to .env without calling the Hevy API",
    )
    args = parser.parse_args(argv)

    env_path = Path(args.env_file).expanduser().resolve() if args.env_file else REPO_ROOT / ".env"
    load_dotenv(env_path)
    current_key = os.environ.get("HEVY_API_KEY")

    if args.check:
        if is_placeholder_key(current_key):
            print(missing_key_message(current_key), file=sys.stderr)
            return 1
        assert current_key is not None
        ok, message = verify_api_key(current_key.strip())
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    print("Hevy API Setup")
    print("--------------")
    print("1. Requires a Hevy Pro subscription.")
    print(f"2. Open {DEVELOPER_SETTINGS_URL} in a web browser (not the mobile app).")
    print("3. Sign in, click 'Generate API Key', and copy your key.")
    print("Note: .env is gitignored and your pasted key will not be echoed.\n")

    if not is_placeholder_key(current_key):
        choice = input(
            "HEVY_API_KEY is already configured. [v]erify existing / [r]eplace / [q]uit (default: v): "
        ).strip().lower()
        if choice in ("q", "quit"):
            return 0
        if choice in ("", "v", "verify"):
            assert current_key is not None
            ok, message = verify_api_key(current_key.strip())
            print(message, file=sys.stdout if ok else sys.stderr)
            return 0 if ok else 1
        if choice not in ("r", "replace"):
            print(f"error: unrecognized choice {choice!r}", file=sys.stderr)
            return 1

    raw_key = getpass.getpass("Paste your Hevy API key (input hidden): ").strip()
    if is_placeholder_key(raw_key):
        print("error: no valid API key entered; .env was not modified.", file=sys.stderr)
        return 1

    if not args.no_verify:
        ok, message = verify_api_key(raw_key)
        if not ok:
            print(f"error: {message}\n.env was not modified.", file=sys.stderr)
            return 1
        print(message)

    write_env_key(env_path, raw_key, REPO_ROOT / ".env.example")
    rel = _display_env_path(env_path)
    print(f"Saved HEVY_API_KEY to {rel} (gitignored, mode 600).")
    print("Next: run 'python3 scripts/build_routines.py --dry-run' or 'python3 scripts/fetch_workouts.py'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
