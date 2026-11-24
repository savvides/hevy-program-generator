"""Pluggable program loader and schema validator for hevy-program-generator."""

from __future__ import annotations

import importlib.util
import os
import math
import re

from pathlib import Path
from typing import Any, Dict, List, Optional

from prescriptions import parse_work_sets

REQUIRED_ROOT_KEYS = ("PROGRAM_METADATA", "ROUTINES", "CARDIO_SCHEDULE")
REQUIRED_METADATA_KEYS = ("title", "session_time_cap_minutes")
REQUIRED_ROUTINE_KEYS = ("name", "day_key", "exercises")
REQUIRED_EXERCISE_KEYS = (
    "name",
    "compound",
    "work_sets",
    "reps",
    "rpe",
    "warmup_reps",
    "rest_seconds",
    "muscle_groups",
    "evidence_citation",
)


WEEKDAYS = {"mon", "monday", "tue", "tuesday", "wed", "wednesday", "thu", "thursday", "fri", "friday", "sat", "saturday", "sun", "sunday"}
# Spellings a routine name may start with that day_key does not accept.
NAME_WEEKDAYS = WEEKDAYS | {"tues", "weds", "thur", "thurs"}


def _number(value: Any, low: float = 0, high: float = float("inf")) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _schedule_errors(item: dict, day_key: str) -> list[str]:
    errors = []
    if str(item.get(day_key, "")).lower() not in WEEKDAYS:
        errors.append(f"Invalid {day_key}: {item.get(day_key)!r}")
    if "start_time" in item and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(item["start_time"])):
        errors.append("start_time must be HH:MM in local time")
    return errors


def _name_weekday(name: Any) -> str:
    """First three letters of the weekday a routine name starts with, else ''."""
    match = re.match(r"\W*([a-z]+)", str(name).lower())
    return match.group(1)[:3] if match and match.group(1) in NAME_WEEKDAYS else ""


def validate_program_context(metadata: Dict[str, Any]) -> List[str]:
    """Validate optional reported context without inferring individual suitability."""
    errors = []
    if "age_years" in metadata and (
        type(metadata["age_years"]) is not int or metadata["age_years"] <= 0
    ):
        errors.append("age_years must be a positive integer (not bool)")
    for field in ("sex", "primary_goal"):
        if field in metadata and (
            not isinstance(metadata[field], str) or not metadata[field].strip()
        ):
            errors.append(f"{field} must be nonblank reported text")
    return errors


def validate_program_schema(program: Dict[str, Any]) -> List[str]:
    """Validates program dictionary structure and types. Returns list of error messages."""
    errors = []

    for key in REQUIRED_ROOT_KEYS:
        if key not in program:
            errors.append(f"Missing root key: '{key}'")

    metadata = program.get("PROGRAM_METADATA")
    if not isinstance(metadata, dict):
        errors.append("'PROGRAM_METADATA' must be a dictionary")
    else:
        for m_key in REQUIRED_METADATA_KEYS:
            if m_key not in metadata:
                errors.append(f"PROGRAM_METADATA missing required key: '{m_key}'")

        # The title is the Hevy folder name.
        if "title" in metadata and (
            not isinstance(metadata["title"], str) or not metadata["title"].strip()
        ):
            errors.append("title must be nonblank text")

        if not _number(metadata.get("session_time_cap_minutes"), 1):
            errors.append("session_time_cap_minutes must be finite and positive")
        if not _number(metadata.get("min_recovery_buffer_hours", 48), 0, 168):
            errors.append("min_recovery_buffer_hours must be between 0 and 168")
        errors.extend(validate_program_context(metadata))

    routines = program.get("ROUTINES")
    if not isinstance(routines, list):
        errors.append("'ROUTINES' must be a list of routine dictionaries")
    else:
        for r_idx, routine in enumerate(routines):
            if not isinstance(routine, dict):
                errors.append(f"Routine at index {r_idx} is not a dictionary")
                continue
            for r_key in REQUIRED_ROUTINE_KEYS:
                if r_key not in routine:
                    errors.append(
                        f"Routine '{routine.get('name', r_idx)}' missing key: '{r_key}'"
                    )

            errors.extend(_schedule_errors(routine, "day_key"))
            # The name is the Hevy routine title the lifter sees; day_key drives the gates.
            named = _name_weekday(routine.get("name", ""))
            day_key = str(routine.get("day_key", "")).lower()
            if named and day_key in WEEKDAYS and named != day_key[:3]:
                errors.append(
                    f"Routine '{routine.get('name')}' starts with a weekday that disagrees "
                    f"with day_key '{routine.get('day_key')}'"
                )
            exercises = routine.get("exercises", [])
            if not isinstance(exercises, list):
                errors.append(
                    f"Routine '{routine.get('name', r_idx)}' exercises must be a list"
                )
            else:
                for e_idx, ex in enumerate(exercises):
                    if not isinstance(ex, dict):
                        errors.append(
                            f"Exercise {e_idx} in routine '{routine.get('name')}' is not a dict"
                        )
                        continue
                    for e_key in REQUIRED_EXERCISE_KEYS:
                        if e_key not in ex:
                            errors.append(
                                f"Exercise '{ex.get('name', e_idx)}' missing key: '{e_key}'"
                            )
                    if "compound" in ex and not isinstance(ex["compound"], bool):
                        errors.append(
                            f"Exercise '{ex.get('name')}' field 'compound' must be bool"
                        )
                    if "work_sets" in ex and (
                        type(ex["work_sets"]) is not int or ex["work_sets"] <= 0
                    ):
                        errors.append(
                            f"Exercise '{ex.get('name')}' field 'work_sets' must be a positive integer"
                        )

                    if not _number(ex.get("rpe"), 1, 10):
                        errors.append(f"Exercise '{ex.get('name')}' rpe must be between 1 and 10")
                    if not _number(ex.get("rest_seconds"), 0):
                        errors.append(f"Exercise '{ex.get('name')}' rest_seconds must be finite and nonnegative")
                    warmups = ex.get("warmup_reps")
                    if warmups is not None and (not isinstance(warmups, list) or any(type(v) is not int or v <= 0 for v in warmups)):
                        errors.append(f"Exercise '{ex.get('name')}' warmup_reps must be positive integers or None")
                    for key in ("name", "evidence_citation"):
                        if not isinstance(ex.get(key), str) or not ex[key].strip():
                            errors.append(f"Exercise {e_idx}: {key} must be nonempty text")
                    muscles = ex.get("muscle_groups")
                    if not isinstance(muscles, list) or not muscles or any(not isinstance(m, str) or not m for m in muscles):
                        errors.append(f"Exercise {e_idx}: muscle_groups must be a nonempty text list")
                    try:
                        parse_work_sets(ex)
                    except ValueError as exc:
                        errors.append(f"Exercise '{ex.get('name')}': {exc}")

    cardio = program.get("CARDIO_SCHEDULE", [])
    if not isinstance(cardio, list):
        errors.append("'CARDIO_SCHEDULE' must be a list")

    else:
        for session in cardio:
            if not isinstance(session, dict):
                errors.append("Cardio sessions must be dictionaries")
                continue
            errors.extend(_schedule_errors(session, "day"))
            for key in ("type", "modality", "evidence_citation"):
                if not isinstance(session.get(key), str) or not session[key].strip():
                    errors.append(f"Cardio {key} must be nonempty text")
            duration = session.get("duration_minutes", session.get("duration_min"))
            if not _number(duration, 1):
                errors.append("Cardio duration_minutes must be finite and positive")
            stype = str(session.get("type", "")).lower()
            interval = session.get("interval_work_min")
            if interval is None and ("vo2" in stype or "hiit" in stype):
                # Whole-token match, consistent with eval_recovery_interference.interval_minutes.
                interval = 16 if re.search(r"(?<!\d)4x4(?!\d)", stype) else 15 if re.search(r"(?<!\d)5x3(?!\d)", stype) else None
                if interval is None:
                    errors.append("Unknown interval protocol requires interval_work_min")
            if interval is not None and (not _number(interval, 0) or not _number(duration, interval)):
                errors.append("Cardio interval_work_min must be finite and cannot exceed session duration")

    constraints = metadata.get("constraints") if isinstance(metadata, dict) else None
    if constraints is not None:
        from movement_patterns import MOVEMENT_REGISTRY, filter_candidates
        if (not isinstance(constraints, dict) or not isinstance(constraints.get("equipment"), list)
                or not constraints["equipment"] or any(not isinstance(e, str) for e in constraints["equipment"])
                or not isinstance(constraints.get("joint_profile"), str) or not constraints["joint_profile"]
                or not isinstance(constraints.get("tier"), str) or not constraints["tier"]):
            errors.append("constraints requires an equipment list, joint_profile and tier")
        elif isinstance(routines, list):
            allowed = {ex.name for pattern in MOVEMENT_REGISTRY for ex in filter_candidates(
                pattern, set(constraints["equipment"]), constraints.get("joint_profile", "standard"), constraints.get("tier", "intermediate"))}
            for routine in routines:
                if isinstance(routine, dict) and isinstance(routine.get("exercises"), list):
                    for ex in routine["exercises"]:
                        if isinstance(ex, dict) and ex.get("name") not in allowed:
                            errors.append(f"Exercise '{ex.get('name')}' does not satisfy declared equipment/joint/tier constraints")
    return errors


def _load_dotenv(path: Path) -> None:
    """Load KEY=value lines from .env into os.environ without overriding existing values."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_program_path(explicit_path: Optional[str] = None) -> Path:
    """Resolves the active program file path."""
    repo_root = Path(__file__).resolve().parent.parent

    # 1. Explicit path passed as argument
    if explicit_path:
        p = Path(explicit_path)
        if not p.is_absolute():
            if (Path.cwd() / p).exists():
                return (Path.cwd() / p).resolve()
            if (repo_root / p).exists():
                return (repo_root / p).resolve()
        if p.exists():
            return p.resolve()
        raise FileNotFoundError(f"Specified program file not found: {explicit_path}")

    # 2. Environment variable HEVY_PROGRAM (also honoured from the repo .env)
    _load_dotenv(repo_root / ".env")
    env_path = os.environ.get("HEVY_PROGRAM")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            if (Path.cwd() / p).exists():
                return (Path.cwd() / p).resolve()
            if (repo_root / p).exists():
                return (repo_root / p).resolve()
        if p.exists():
            return p.resolve()
        raise FileNotFoundError(f"Program specified in HEVY_PROGRAM not found: {env_path}")

    # 3. User's local private program.py
    user_prog = repo_root / "programs" / "program.py"
    if user_prog.exists():
        return user_prog

    # 4. Active program (keep in sync with render_program.DEFAULT_PROGRAM)
    default_active = repo_root / "programs" / "starter_full_body_2x.py"
    if default_active.exists():
        return default_active

    raise FileNotFoundError("No program file found in programs/ directory.")


def load_program(explicit_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads and validates a program file from disk."""
    path = resolve_program_path(explicit_path)
    spec = importlib.util.spec_from_file_location("active_program", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load python module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Only what the module defines: a misspelled name must fail as a missing key,
    # not silently become an empty default.
    prog_data = {k: getattr(module, k) for k in REQUIRED_ROOT_KEYS if hasattr(module, k)}
    prog_data["_file_path"] = str(path)

    errors = validate_program_schema(prog_data)
    if errors:
        raise ValueError(
            f"Program '{path}' has schema errors:\n"
            + "\n".join(f" - {e}" for e in errors)
        )

    return prog_data
