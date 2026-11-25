#!/usr/bin/env python3
"""Fetch all workouts from the Hevy API into data/workouts/<id>.json."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

from setup_hevy import auth_error_hint, is_placeholder_key, missing_key_message

API_BASE = "https://api.hevyapp.com/v1"
PAGE_SIZE = 10  # Hevy API max
REPO_ROOT = Path(__file__).resolve().parent.parent
# HTTPError is a URLError. socket.timeout is only an alias of TimeoutError from Python 3.10.
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError)


def resolve_workouts_dir(cli_dir: str | None = None) -> Path:
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    env_dir = os.environ.get("HEVY_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return REPO_ROOT / "data" / "workouts"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def fetch_page(api_key: str, page: int) -> dict:
    url = f"{API_BASE}/workouts?page={page}&pageSize={PAGE_SIZE}"
    req = urllib.request.Request(url, headers={"api-key": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=None, help="Directory to save workout logs (or set HEVY_DATA_DIR)")
    args = ap.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    raw_key = os.environ.get("HEVY_API_KEY")
    if is_placeholder_key(raw_key):
        print(missing_key_message(raw_key), file=sys.stderr)
        return 1
    assert raw_key is not None
    api_key = raw_key.strip()

    out_dir = resolve_workouts_dir(args.data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        first = fetch_page(api_key, 1)
    except urllib.error.HTTPError as e:
        print(f"error: HTTP {e.code} on page 1: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        if e.code in (401, 403):
            print(f"  hint: {auth_error_hint(e.code)}", file=sys.stderr)
        return 1
    except NETWORK_ERRORS as e:
        print(f"error: fetch stopped on page 1 ({e!r}). It is safe to re-run.", file=sys.stderr)
        return 1

    page_count = first.get("page_count", 1)
    total = 0

    def write_page(payload: dict, page: int) -> int:
        workouts = payload.get("workouts", [])
        for w in workouts:
            wid = w["id"]
            (out_dir / f"{wid}.json").write_text(
                json.dumps(w, indent=2, sort_keys=True) + "\n"
            )
        print(f"[page {page}/{page_count}] wrote {len(workouts)} workouts")
        return len(workouts)

    total += write_page(first, 1)
    for page in range(2, page_count + 1):
        try:
            payload = fetch_page(api_key, page)
        except NETWORK_ERRORS as e:
            print(f"error: fetch stopped partway on page {page}/{page_count} ({e!r}). "
                  "It is safe to re-run.", file=sys.stderr)
            return 1
        total += write_page(payload, page)

    try:
        out_display = str(out_dir.relative_to(REPO_ROOT))
    except ValueError:
        out_display = str(out_dir)

    print(f"Done: {total} workouts synced to {out_display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
