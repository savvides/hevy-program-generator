#!/usr/bin/env python3
"""Build and reconcile Hevy routines from the selected Python program. Stdlib only."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from program_loader import load_program
from prescriptions import parse_work_sets
from eval_evidence_grounding import parse_citation, split_citations

API_BASE = "https://api.hevyapp.com/v1"
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "exercise_templates.json"
CACHE_MAX_AGE_SECONDS = 30 * 86400
# Failures that can interrupt a sync besides an HTTP error status. socket.timeout is only an
# alias of TimeoutError from Python 3.10.
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError)

# Dynamic program loading with backward-compatible global exports
try:
    _ACTIVE_PROGRAM = load_program()
except (FileNotFoundError, ValueError, ImportError):
    _ACTIVE_PROGRAM = {}

PROGRAM_METADATA = _ACTIVE_PROGRAM.get("PROGRAM_METADATA", {})
ROUTINES = _ACTIVE_PROGRAM.get("ROUTINES", [])
CARDIO_SCHEDULE = _ACTIVE_PROGRAM.get("CARDIO_SCHEDULE", [])
FOLDER_TITLE = PROGRAM_METADATA.get("title", "Health Training Program")

# Existing coaching ramp. Export supplies reps only; choose progressive warmup loads.
WU_STANDARD = [5, 5, 3]

EXERCISE_ALIASES: dict[str, str] = {
    "pallof press band": "Cable Core Pallof Press",
    "palloff press band": "Cable Core Pallof Press",
    "pallof press": "Cable Core Pallof Press",
    "palloff press": "Cable Core Pallof Press",
    "cable core palloff press": "Cable Core Pallof Press",
}


# ---------------------------------------------------------------------------
# HTTP + .env helpers (mirrors scripts/fetch_workouts.py style)
# ---------------------------------------------------------------------------

def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def http_request(api_key: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"api-key": api_key, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    if not raw:
        return {}
    return json.loads(raw)


def fetch_templates(api_key: str | None = None) -> list[dict]:
    if CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_MAX_AGE_SECONDS or not api_key:
            print(f"  using cache ({CACHE_PATH.relative_to(REPO_ROOT)}, age={int(age/3600)}h)")
            return json.loads(CACHE_PATH.read_text())

    if not api_key:
        print("error: HEVY_API_KEY not set and cache missing", file=sys.stderr)
        return []

    templates: list[dict] = []
    page = 1
    while True:
        payload = http_request(api_key, "GET", f"/exercise_templates?page={page}&pageSize=100")
        page_items = payload.get("exercise_templates", []) or payload.get("data", [])
        templates.extend(page_items)
        page_count = payload.get("page_count", 1)
        print(f"  page {page}/{page_count}: +{len(page_items)} (total {len(templates)})")
        if page >= page_count or not page_items:
            break
        page += 1

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(templates, indent=2, sort_keys=True) + "\n")
    return templates


# ---------------------------------------------------------------------------
# Exercise-name resolution (fuzzy match by token overlap)
# ---------------------------------------------------------------------------

def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _score(target_tokens: set[str], title_tokens: set[str]) -> float:
    if not target_tokens or not title_tokens:
        return 0.0
    overlap = len(target_tokens & title_tokens)
    return overlap / max(len(target_tokens | title_tokens), 1)


def find_template(templates: list[dict], target: str) -> dict | None:
    norm_target = normalize(target)
    if norm_target in EXERCISE_ALIASES:
        target = EXERCISE_ALIASES[norm_target]
        norm_target = normalize(target)
    target_tokens = set(norm_target.split())
    exact = [t for t in templates if normalize(t.get("title", "")) == norm_target]

    def tie_break(t: dict) -> tuple[bool, str]:
        return (bool(t.get("is_custom")), str(t.get("id", "")))

    if exact:
        # Deterministic tie-break when two templates share a normalized title
        # (e.g. a built-in and a custom "Sled Push"): prefer the built-in one,
        # then the lowest id. The Hevy catalog's list order isn't guaranteed
        # stable across fetches — "first in list" would otherwise resolve to
        # a different template run to run depending on API response order.
        exact.sort(key=tie_break)
        return exact[0]
    best, best_score = None, 0.0
    for t in templates:
        title_tokens = set(normalize(t.get("title", "")).split())
        score = _score(target_tokens, title_tokens)
        # Equal top scores use the same tie-break as above, not catalog order.
        if score > best_score or (best is not None and score == best_score
                                  and tie_break(t) < tie_break(best)):
            best_score, best = score, t
    return best if best_score >= 0.55 else None


def candidates_for(templates: list[dict], target: str, n: int = 5) -> list[dict]:
    norm_target = normalize(target)
    if norm_target in EXERCISE_ALIASES:
        norm_target = normalize(EXERCISE_ALIASES[norm_target])
    target_tokens = set(norm_target.split())
    scored = [
        (_score(target_tokens, set(normalize(t.get("title", "")).split())), t)
        for t in templates
    ]
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:n]]


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def build_set(spec: dict, is_warmup: bool, warmup_reps: int | None = None) -> dict:
    s: dict = {"type": "warmup" if is_warmup else "normal"}
    if is_warmup and warmup_reps is not None:
        s["reps"] = warmup_reps
        return s
    if "duration_seconds" in spec:
        s["duration_seconds"] = spec["duration_seconds"]
    elif "reps_min" in spec:
        s["rep_range"] = {"start": spec["reps_min"], "end": spec["reps_max"]}
        s["reps"] = spec["reps_min"]
    elif "reps" in spec:
        s["reps"] = spec["reps"]
    return s


def citation_keys(raw: str) -> list[str]:
    """'Polito et al. 2021 (claim; more); Currier et al. 2026 (claim)' -> the two keys."""
    keys = []
    for citation in split_citations(raw):
        parsed = parse_citation(citation)
        keys.append(parsed["citation_key"] if parsed else citation)
    return keys


def uses_writing_standard(program: dict) -> bool:
    return bool(program.get("PROGRAM_METADATA", {}).get("writing_standard"))


def build_compact_exercise_note(ex: dict, specs: list[dict]) -> str:
    """Build a self-contained BLUF note under 250 chars with progression and gym cues."""
    is_per_side = any(s.get("sides") == 2 for s in specs)
    work_sets = ex["work_sets"]
    reps = str(ex.get("reps", "")).strip()
    rpe = ex.get("rpe")
    rpe_str = f" at RPE {rpe}" if rpe is not None else ""

    first_spec = specs[0] if specs else {}
    low = None
    if "duration_seconds" in first_spec:
        top = f"{first_spec['duration_seconds']}s"
        if "-" in reps:
            low = reps.split("-")[0].strip() + "s"
    elif "reps_max" in first_spec:
        top = str(first_spec["reps_max"])
        low = str(first_spec["reps_min"])
    else:
        top = str(first_spec.get("reps", reps))

    side_str = " per side" if is_per_side else ""
    bluf = f"BLUF: {work_sets} x {reps}{rpe_str}. Add load after {work_sets} x {top}{side_str}{rpe_str}."

    body: list[str] = []
    if low and low != top:
        body.append(f"Then start again at {low}.")
    if ex.get("notes"):
        body.append(ex["notes"].strip())
    if is_per_side:
        body.append("Do both sides. Record one set.")
    if ex.get("evidence_citation"):
        body.append("Evidence: " + "; ".join(citation_keys(ex["evidence_citation"])) + ".")
    return bluf + ("\n" + " ".join(body) if body else "")


def build_routine_payload(routine: dict, resolved: dict[str, int], compact: bool = False) -> dict:
    """compact=True (programs with a writing_standard) exports short cues plus citation keys only."""
    exercises = []
    for ex in routine["exercises"]:
        sets: list[dict] = []
        warmup_reps = ex.get("warmup_reps") or []
        for wu_reps in warmup_reps:
            sets.append(build_set({}, is_warmup=True, warmup_reps=wu_reps))
        specs = parse_work_sets(ex)
        for ws in specs:
            sets.append(build_set(ws, is_warmup=False))
        if compact:
            note_text = build_compact_exercise_note(ex, specs)
        else:
            instructions = [ex.get("notes") or ex.get("evidence_citation", "")]
            if "reps" in ex:
                instructions.append(f"Prescription: {ex['work_sets']} x {ex['reps']}.")
            if ex.get("rpe") is not None:
                instructions.append(f"Target RPE {ex['rpe']}.")
            if any(s.get("sides") == 2 for s in specs):
                instructions.append("Per side: do both sides. Record the two sides as one set. "
                                    "Warmup reps are also per side.")
            note_text = " ".join(filter(None, instructions))
        exercises.append({
            "exercise_template_id": resolved[ex["name"]],
            # superset_id groups exercises into a Hevy superset; None = solo lift.
            "superset_id": ex.get("superset"),
            "notes": note_text,
            "rest_seconds": ex.get("rest_seconds", 60),
            "sets": sets,
        })
    title = routine.get("title") or routine.get("name", "")
    notes = routine.get("notes", "")
    # Hevy supports exercise notes, but silently drops routine-level notes.
    # Non-compact programs append session instructions to exercise 0; compact
    # programs keep self-contained per-exercise BLUF notes under 250 characters.
    if not compact and notes and exercises:
        exercises[0]["notes"] += "\n\nSession instructions:\n" + notes
    return {
        "routine": {
            "title": title,
            "exercises": exercises,
        }
    }


def extract_id(resp: dict | list, key: str) -> tuple[str | None, str]:
    """Try to find an id in the create response. Returns (id, debug_summary)."""
    if isinstance(resp, dict):
        wrapped = resp.get(key)
        if isinstance(wrapped, dict) and wrapped.get("id"):
            return str(wrapped["id"]), ""
        if isinstance(wrapped, list) and wrapped and isinstance(wrapped[0], dict) and wrapped[0].get("id"):
            return str(wrapped[0]["id"]), ""
        if resp.get("id"):
            return str(resp["id"]), ""
        return None, f"keys={list(resp.keys())}"
    if isinstance(resp, list) and resp and isinstance(resp[0], dict) and resp[0].get("id"):
        return str(resp[0]["id"]), ""
    return None, f"type={type(resp).__name__}"


# ---------------------------------------------------------------------------
# Idempotent reconcile — match existing routines by routine_key so the sync
# UPDATEs in place instead of creating duplicates. Identity is the weekday
# (Mon/Tue/…) parsed from the title prefix — so a descriptive-suffix change
# ("Hinge" → "Spine Deload") still targets the same routine — or, for
# non-weekday routines (e.g. "Full-Body A", "Daily — Core"), the normalized
# full title. The Hevy API has no DELETE for routines (verified via OPTIONS:
# /routines/{id} → GET,HEAD,PUT), so stale/duplicate routines are reported for
# manual removal.
# ---------------------------------------------------------------------------

WEEKDAYS = {
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tues": "tue", "tuesday": "tue",
    "wed": "wed", "weds": "wed", "wednesday": "wed",
    "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}


def day_key(title: str) -> str | None:
    """Weekday identity for a routine, parsed from the title's first token."""
    tokens = (title or "").strip().split()
    if not tokens:
        return None
    first = re.sub(r"[^a-z]", "", tokens[0].lower())
    return WEEKDAYS.get(first)


def routine_key(title: str) -> str:
    """Stable match key: weekday if the title has one, else the normalized full
    title. Lets non-weekday routines (e.g. 'Full-Body A', 'Daily — Core')
    reconcile by title instead of never-matching and creating a duplicate on
    every sync."""
    return day_key(title) or normalize(title)


def plan_reconcile(
    desired: list[dict], existing: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Decide update-vs-create per desired routine, matched by routine_key
    (weekday, or normalized title for non-weekday routines).

    Returns (actions, extras):
      actions = [{"action": "update"|"create", "routine": <desired>,
                  "routine_id": <id>|None}, ...]
      extras  = existing routines left unmatched (stale or duplicate); the API
                cannot delete these, so they are reported for manual cleanup.

    Raises ValueError when two desired routines share a routine_key: both would
    match the same existing routine, and the second PUT would overwrite the first.
    """
    by_key: dict[str, dict] = {}
    for r in existing:
        k = routine_key(r.get("title", ""))
        if k and k not in by_key:  # first occurrence wins; dupes become extras
            by_key[k] = r

    actions: list[dict] = []
    matched_ids: set = set()
    desired_keys: dict[str, str] = {}
    for r in desired:
        r_title = r.get("title") or r.get("name", "")
        key = routine_key(r_title)
        if key in desired_keys:
            raise ValueError(
                f"routines {desired_keys[key]!r} and {r_title!r} share the reconcile key "
                f"{key!r}; a sync would write both to the same Hevy routine. "
                "Give each routine a different weekday or title.")
        desired_keys[key] = r_title
        match = by_key.get(key)
        if match is not None:
            actions.append({"action": "update", "routine": r,
                            "routine_id": match["id"]})
            matched_ids.add(match["id"])
        else:
            actions.append({"action": "create", "routine": r, "routine_id": None})

    extras = [r for r in existing if r.get("id") not in matched_ids]
    return actions, extras


def fetch_routines(api_key: str) -> list[dict]:
    """All routines on the account (paginated; Hevy caps routines pageSize at 10)."""
    routines: list[dict] = []
    page = 1
    while True:
        payload = http_request(api_key, "GET", f"/routines?page={page}&pageSize=10")
        items = payload.get("routines", []) or payload.get("data", [])
        routines.extend(items)
        page_count = payload.get("page_count", 1)
        if page >= page_count or not items:
            break
        page += 1
    return routines


def find_folder(api_key: str, title: str) -> str | None:
    """Return the id of the folder whose title matches, else None."""
    want = title.strip()
    page = 1
    while True:
        payload = http_request(api_key, "GET",
                               f"/routine_folders?page={page}&pageSize=10")
        items = payload.get("routine_folders", []) or payload.get("data", [])
        for f in items:
            if (f.get("title") or "").strip() == want:
                return str(f.get("id"))
        page_count = payload.get("page_count", 1)
        if page >= page_count or not items:
            break
        page += 1
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None,
                        help="Path to training program python file (default: programs/starter_full_body_2x.py)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payloads, do not create folder/routines")
    parser.add_argument("--skip-qa", action="store_true",
                        help="Skip configured pre-flight QA checks")
    parser.add_argument("--folder", default=None,
                        help="Routine folder title override (default from program metadata)")
    args = parser.parse_args(argv)

    prog = load_program(args.program)
    routines = prog.get("ROUTINES", [])
    metadata = prog.get("PROGRAM_METADATA", {})
    target_folder = args.folder or metadata.get("title", FOLDER_TITLE)
    compact = uses_writing_standard(prog)

    if not args.skip_qa:
        import qa_program
        print("Running pre-flight evidence & program QA gate...")
        qa_args = ["--program", args.program] if args.program else []
        qa_rc = qa_program.main(qa_args)
        if qa_rc != 0:
            print("\nerror: Pre-flight QA failed. A configured policy or structural check failed.", file=sys.stderr)
            print("Run 'python3 scripts/qa_program.py' for diagnostics or use '--skip-qa' to bypass.", file=sys.stderr)
            return qa_rc
        print()

    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("HEVY_API_KEY")
    if not api_key and not args.dry_run:
        print("error: HEVY_API_KEY not set (export it or add it to .env)", file=sys.stderr)
        return 1

    print(f"Loading exercise templates ({CACHE_PATH.relative_to(REPO_ROOT)})…")
    # A dry run passes no key, so fetch_templates reads the cache and never rewrites it.
    templates = fetch_templates(None if args.dry_run else api_key)
    print(f"  {len(templates)} templates available")

    print("\nResolving exercises against Hevy catalog:")
    resolved: dict[str, int] = {}
    unresolved: list[tuple[str, list[dict]]] = []
    seen: set[str] = set()
    for routine in routines:
        for ex in routine["exercises"]:
            name = ex["name"]
            if name in seen:
                continue
            seen.add(name)
            match = find_template(templates, name)
            if match is not None:
                resolved[name] = match["id"]
                print(f"  {name[:50]:50s} → {match['title']} (id={match['id']})")
            else:
                cands = candidates_for(templates, name)
                unresolved.append((name, cands))
                print(f"  {name[:50]:50s} → UNRESOLVED")

    if unresolved:
        print("\nUnresolved — top candidates per item:")
        for name, cands in unresolved:
            print(f"  {name!r}")
            for c in cands:
                print(f"    - {c.get('title', '?')} (id={c.get('id', '?')})")
        print("\nEdit the 'name' fields in ROUTINES (or add a custom exercise in the "
              "Hevy app), then re-run.")
        return 1

    # Reconcile against what's already in the target folder so we UPDATE in place
    # rather than create duplicates.
    folder_id = None
    in_folder: list[dict] = []
    # Why the existing routines could not be read (dry-run only); None = they were read.
    unchecked = None if api_key else "HEVY_API_KEY is not set"
    if api_key:
        try:
            folder_id = find_folder(api_key, target_folder)
            if folder_id:
                in_folder = [r for r in fetch_routines(api_key) if str(r.get("folder_id")) == str(folder_id)]
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if args.dry_run:
                if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403):
                    unchecked = f"Hevy rejected the API key (HTTP {e.code})"
                else:
                    unchecked = f"Hevy API unreachable ({e})"
                print(f"  note: {unchecked}; running dry-run against local cache")
            else:
                raise
    try:
        actions, extras = plan_reconcile(routines, in_folder)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    def _print_extras(header: str) -> None:
        if extras:
            print(f"\n{header}")
            for r in extras:
                print(f"  - {r.get('title')!r} (id={r.get('id')})")

    if args.dry_run:
        loc = f"id={folder_id}" if folder_id else "WILL BE CREATED"
        if unchecked:
            loc = "not checked"
            print(f"\nWARNING: this plan was NOT checked against Hevy: {unchecked}. "
                  "It is unknown whether the folder exists and whether each routine "
                  "will be created or updated.")
        print(f"\nTarget folder: {target_folder!r} ({loc})")
        print(f"Existing routines in folder: {len(in_folder)}")
        print("\nReconcile plan:")
        for a in actions:
            tgt = f"→ PUT {a['routine_id']}" if a["action"] == "update" else "→ POST (new)"
            r_title = a["routine"].get("title") or a["routine"].get("name", "")
            if unchecked:
                print(f"  ?      {r_title[:52]:52s} → not checked (POST or PUT)")
                continue
            print(f"  {a['action'].upper():6s} {r_title[:52]:52s} {tgt}")
        _print_extras("Stale routines in folder (API has no DELETE — remove in app):")
        print("\nPayload preview:")
        for action in actions:
            print(json.dumps(build_routine_payload(action["routine"], resolved, compact), indent=2))
        print("\n(dry run — no API writes made; existing routines may have been read)")
        return 0

    # Past the dry-run return above, a key is guaranteed: main() exits earlier
    # when HEVY_API_KEY is missing and this is not a dry run.
    assert api_key is not None

    if folder_id is None:
        print(f"\nCreating folder: {target_folder!r}")
        try:
            folder_resp = http_request(api_key, "POST", "/routine_folders",
                                       {"routine_folder": {"title": target_folder}})
        except urllib.error.HTTPError as e:
            print(f"error: folder create failed: HTTP {e.code} — "
                  f"{e.read().decode('utf-8', 'replace')}", file=sys.stderr)
            return 1
        except NETWORK_ERRORS as e:
            print(f"error: sync stopped at folder create ({e!r}). No routine was written; "
                  "it is safe to re-run.", file=sys.stderr)
            return 1
        folder_id, dbg = extract_id(folder_resp, "routine_folder")
        if not folder_id:
            print(f"error: no folder id in response ({dbg}); raw={folder_resp!r}",
                  file=sys.stderr)
            return 1
    print(f"\nTarget folder id={folder_id}")

    for a in actions:
        r = a["routine"]
        payload = build_routine_payload(r, resolved, compact)
        r_title = r.get("title") or r.get("name", "")
        if a["action"] == "update":
            # PUT rejects routine.folder_id; the routine already lives in the folder.
            verb, method, path = "Updating", "PUT", f"/routines/{a['routine_id']}"
        else:
            payload["routine"]["folder_id"] = folder_id  # required on create
            verb, method, path = "Creating", "POST", "/routines"
        print(f"{verb} routine: {r_title}")
        try:
            resp = http_request(api_key, method, path, payload)
        except urllib.error.HTTPError as e:
            print(f"  error: HTTP {e.code} — {e.read().decode('utf-8', 'replace')}",
                  file=sys.stderr)
            return 1
        except NETWORK_ERRORS as e:
            print(f"  error: sync stopped partway at {r_title!r} ({e!r}). It is safe to "
                  "re-run: routines are matched by key, not duplicated.", file=sys.stderr)
            return 1
        rid, dbg = extract_id(resp, "routine")
        print(f"  routine_id={rid}" if rid else f"  done (id parse miss; {dbg})")
        time.sleep(0.4)

    _print_extras("⚠ Stale routines remain (Hevy API has no DELETE — remove in app):")
    print(f"\nDone. Open Hevy → Routines → '{target_folder}' to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
