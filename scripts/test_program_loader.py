"""Unit tests for pluggable program loader and schema validator."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import program_loader


def _valid_program():
    return {
        "PROGRAM_METADATA": {
            "title": "Test Program",
            "version": "1.0.0",
            "target_demographic": "General Lifter",
            "session_time_cap_minutes": 60,
            "min_recovery_buffer_hours": 48,
        },
        "ROUTINES": [
            {
                "name": "Full-Body A",
                "day_key": "Tuesday",
                "notes": "Test notes",
                "exercises": [
                    {
                        "name": "Squat (Barbell)",
                        "compound": True,
                        "warmup_reps": [5, 5, 3],
                        "work_sets": 3,
                        "reps": "5",
                        "rpe": 8,
                        "rest_seconds": 120,
                        "muscle_groups": ["quads", "glutes"],
                        "evidence_citation": "Polito et al. 2021",
                    }
                ],
            }
        ],
        "CARDIO_SCHEDULE": [
            {
                "day": "Thursday",
                "modality": "Stationary Bike",
                "type": "VO2 Max 4x4",
                "duration_minutes": 40,
                "evidence_citation": "Milanović et al. 2015",
            }
        ],
    }


def _exercise(prog):
    return prog["ROUTINES"][0]["exercises"][0]


class TestProgramLoader(unittest.TestCase):

    def test_optional_context_preserves_unknown_and_reported_values(self):
        prog = program_loader.load_program("programs/starter_full_body_2x.py")
        for field in ("age_years", "sex", "primary_goal"):
            prog["PROGRAM_METADATA"].pop(field, None)
        self.assertEqual(program_loader.validate_program_schema(prog), [])
        for sex in ("nonbinary", "unspecified", " female "):
            with self.subTest(sex=sex):
                prog["PROGRAM_METADATA"].update(age_years=17, sex=sex, primary_goal="aerobic support")
                self.assertEqual(program_loader.validate_program_schema(prog), [])
                self.assertEqual(prog["PROGRAM_METADATA"]["sex"], sex)

    def test_invalid_optional_context_returns_schema_errors(self):
        invalid = {
            "age_years": (True, False, 0, -1, 40.5, float("inf"), float("nan"), "40", None),
            "sex": ("", " \t\n", 1, None),
            "primary_goal": ("", " \t\n", 1, None),
        }
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    prog = program_loader.load_program("programs/starter_full_body_2x.py")
                    prog["PROGRAM_METADATA"][field] = value
                    errors = program_loader.validate_program_schema(prog)
                    self.assertTrue(any(field in error for error in errors), errors)

    def test_validate_valid_program(self):
        errors = program_loader.validate_program_schema(_valid_program())
        self.assertEqual(errors, [])

    def test_validate_missing_keys(self):
        invalid_prog = {"ROUTINES": []}
        errors = program_loader.validate_program_schema(invalid_prog)
        self.assertIn("Missing root key: 'PROGRAM_METADATA'", errors)

    def test_validate_invalid_exercise_fields(self):
        bad_prog = {
            "PROGRAM_METADATA": {"title": "Bad", "session_time_cap_minutes": 60},
            "ROUTINES": [
                {
                    "name": "A",
                    "day_key": "Monday",
                    "exercises": [
                        {
                            "name": "Bench Press (Barbell)",
                            "compound": "yes",  # should be bool
                            "work_sets": -1,  # should be > 0
                        }
                    ],
                }
            ],
            "CARDIO_SCHEDULE": [],
        }
        errors = program_loader.validate_program_schema(bad_prog)
        self.assertIn("Exercise 'Bench Press (Barbell)' field 'compound' must be bool", errors)
        self.assertIn(
            "Exercise 'Bench Press (Barbell)' field 'work_sets' must be a positive integer", errors
        )

    def test_load_from_filepath(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(
                'PROGRAM_METADATA = {"title": "Temp", "session_time_cap_minutes": 50}\n'
                'ROUTINES = [{"name": "A", "day_key": "Mon", "exercises": [{"name": "Curl", "compound": False, "work_sets": 3, "reps": 10, "rpe": 9, "warmup_reps": None, "rest_seconds": 60, "muscle_groups": ["biceps"], "evidence_citation": "Currier 2026"}]}]\n'
                'CARDIO_SCHEDULE = []\n'
            )
            temp_path = f.name

        try:
            prog = program_loader.load_program(temp_path)
            self.assertEqual(prog["PROGRAM_METADATA"]["title"], "Temp")
            self.assertEqual(len(prog["ROUTINES"]), 1)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_hevy_program_env_not_found_raises(self):
        old_env = os.environ.get("HEVY_PROGRAM")
        try:
            os.environ["HEVY_PROGRAM"] = "programs/does_not_exist_xyz.py"
            with self.assertRaises(FileNotFoundError):
                program_loader.resolve_program_path()
        finally:
            if old_env is not None:
                os.environ["HEVY_PROGRAM"] = old_env
            else:
                os.environ.pop("HEVY_PROGRAM", None)

    def test_hevy_program_env_valid(self):
        old_env = os.environ.get("HEVY_PROGRAM")
        try:
            os.environ["HEVY_PROGRAM"] = "programs/starter_full_body_2x.py"
            resolved = program_loader.resolve_program_path()
            self.assertTrue(resolved.exists())
            self.assertTrue(str(resolved).endswith("starter_full_body_2x.py"))
        finally:
            if old_env is not None:
                os.environ["HEVY_PROGRAM"] = old_env
            else:
                os.environ.pop("HEVY_PROGRAM", None)

    def test_load_dotenv_sets_hevy_program_without_overriding(self):
        old_env = os.environ.pop("HEVY_PROGRAM", None)
        fd, temp_path = tempfile.mkstemp(suffix=".env")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("# comment\nHEVY_PROGRAM=programs/upper_lower_4x.py\n")
            program_loader._load_dotenv(Path(temp_path))
            self.assertEqual(os.environ["HEVY_PROGRAM"], "programs/upper_lower_4x.py")
            os.environ["HEVY_PROGRAM"] = "explicit.py"
            program_loader._load_dotenv(Path(temp_path))
            self.assertEqual(os.environ["HEVY_PROGRAM"], "explicit.py")
        finally:
            os.remove(temp_path)
            if old_env is not None:
                os.environ["HEVY_PROGRAM"] = old_env
            else:
                os.environ.pop("HEVY_PROGRAM", None)


# Each case breaks exactly one thing in an otherwise valid program and names the
# message that break must produce. Messages are matched as whole list entries so a
# neighbouring error (for example "'PROGRAM_METADATA' must be a dictionary") cannot
# satisfy the wrong case.
SCHEMA_CASES = (
    ("compound not bool", lambda p: _exercise(p).update(compound="yes"),
     "Exercise 'Squat (Barbell)' field 'compound' must be bool"),
    ("warmup_reps not positive ints", lambda p: _exercise(p).update(warmup_reps=[5, 0]),
     "Exercise 'Squat (Barbell)' warmup_reps must be positive integers or None"),
    ("warmup_reps not a list", lambda p: _exercise(p).update(warmup_reps="5,5,3"),
     "Exercise 'Squat (Barbell)' warmup_reps must be positive integers or None"),
    ("blank exercise name", lambda p: _exercise(p).update(name=" "),
     "Exercise 0: name must be nonempty text"),
    ("blank exercise citation", lambda p: _exercise(p).update(evidence_citation=""),
     "Exercise 0: evidence_citation must be nonempty text"),
    ("empty muscle_groups", lambda p: _exercise(p).update(muscle_groups=[]),
     "Exercise 0: muscle_groups must be a nonempty text list"),
    ("non-text muscle_groups entry", lambda p: _exercise(p).update(muscle_groups=["quads", 3]),
     "Exercise 0: muscle_groups must be a nonempty text list"),
    ("bad session_time_cap_minutes", lambda p: p["PROGRAM_METADATA"].update(session_time_cap_minutes=0),
     "session_time_cap_minutes must be finite and positive"),
    ("bad min_recovery_buffer_hours", lambda p: p["PROGRAM_METADATA"].update(min_recovery_buffer_hours=169),
     "min_recovery_buffer_hours must be between 0 and 168"),
    ("missing routine key", lambda p: p["ROUTINES"][0].pop("day_key"),
     "Routine 'Full-Body A' missing key: 'day_key'"),
    ("missing exercise key", lambda p: _exercise(p).pop("rest_seconds"),
     "Exercise 'Squat (Barbell)' missing key: 'rest_seconds'"),
    ("missing metadata title", lambda p: p["PROGRAM_METADATA"].pop("title"),
     "PROGRAM_METADATA missing required key: 'title'"),
    ("missing metadata session cap", lambda p: p["PROGRAM_METADATA"].pop("session_time_cap_minutes"),
     "PROGRAM_METADATA missing required key: 'session_time_cap_minutes'"),
    ("missing root PROGRAM_METADATA", lambda p: p.pop("PROGRAM_METADATA"),
     "Missing root key: 'PROGRAM_METADATA'"),
    ("missing root ROUTINES", lambda p: p.pop("ROUTINES"),
     "Missing root key: 'ROUTINES'"),
    ("missing root CARDIO_SCHEDULE", lambda p: p.pop("CARDIO_SCHEDULE"),
     "Missing root key: 'CARDIO_SCHEDULE'"),
    ("bad cardio duration", lambda p: p["CARDIO_SCHEDULE"][0].update(duration_minutes=0),
     "Cardio duration_minutes must be finite and positive"),
    ("blank cardio type", lambda p: p["CARDIO_SCHEDULE"][0].update(type=" "),
     "Cardio type must be nonempty text"),
    ("blank cardio modality", lambda p: p["CARDIO_SCHEDULE"][0].update(modality=""),
     "Cardio modality must be nonempty text"),
    ("cardio day not a weekday", lambda p: p["CARDIO_SCHEDULE"][0].update(day="Funday"),
     "Invalid day: 'Funday'"),
    ("title is None", lambda p: p["PROGRAM_METADATA"].update(title=None),
     "title must be nonblank text"),
    ("title is blank", lambda p: p["PROGRAM_METADATA"].update(title=""),
     "title must be nonblank text"),
    ("title is whitespace", lambda p: p["PROGRAM_METADATA"].update(title=" \t"),
     "title must be nonblank text"),
    ("title is a number", lambda p: p["PROGRAM_METADATA"].update(title=123),
     "title must be nonblank text"),
)


class TestSchemaGuards(unittest.TestCase):

    def test_base_program_is_valid(self):
        """Without this, the negative cases below would prove nothing."""
        self.assertEqual(program_loader.validate_program_schema(_valid_program()), [])

    def test_each_broken_field_reports_its_own_message(self):
        for label, break_it, expected in SCHEMA_CASES:
            with self.subTest(label):
                prog = _valid_program()
                break_it(prog)
                self.assertIn(expected, program_loader.validate_program_schema(prog))

    def test_routine_name_weekday_must_agree_with_day_key(self):
        cases = (
            ("Saturday — Lower B", "Friday", True),
            ("saturday: lower b", "FRIDAY", True),
            ("Saturday—Lower B", "Friday", True),
            ("Thurs — Upper", "Friday", True),
            ("Friday — Lower B", "Friday", False),
            ("Tues. — Upper", "Tuesday", False),
            ("Weds — Upper", "Wednesday", False),
            ("Thur — Upper", "Thu", False),
            ("Sunrise Session", "Tuesday", False),
            ("Monster Legs", "Friday", False),
            ("Full-Body A", "Tuesday", False),
        )
        for name, day_key, flagged in cases:
            with self.subTest(name=name, day_key=day_key):
                prog = _valid_program()
                prog["ROUTINES"][0].update(name=name, day_key=day_key)
                errors = program_loader.validate_program_schema(prog)
                if flagged:
                    self.assertIn(
                        f"Routine '{name}' starts with a weekday that disagrees with day_key '{day_key}'",
                        errors,
                    )
                else:
                    self.assertEqual(errors, [])

    def test_misspelled_cardio_schedule_is_not_read_as_no_cardio(self):
        prog = _valid_program()
        prog["CARDIO_SCHEDUL"] = prog.pop("CARDIO_SCHEDULE")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "typo.py"
            path.write_text("\n".join(f"{key} = {value!r}" for key, value in prog.items()))
            with self.assertRaises(ValueError) as caught:
                program_loader.load_program(str(path))
        self.assertIn("Missing root key: 'CARDIO_SCHEDULE'", str(caught.exception))

    def test_explicit_empty_cardio_schedule_is_valid(self):
        prog = _valid_program()
        prog["CARDIO_SCHEDULE"] = []
        self.assertEqual(program_loader.validate_program_schema(prog), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no_cardio.py"
            path.write_text("\n".join(f"{key} = {value!r}" for key, value in prog.items()))
            self.assertEqual(program_loader.load_program(str(path))["CARDIO_SCHEDULE"], [])


    def test_interval_protocol_is_matched_as_a_whole_token(self):
        unknown = "Unknown interval protocol requires interval_work_min"
        for label, flagged in (("VO2 Max 4x4", False), ("VO2 Max 5x3", False), ("VO2 Max 14x4", True),
                               ("VO2 Max 15x3", True), ("HIIT 5x30s", True), ("VO2 Max 4x45s", True)):
            with self.subTest(label=label):
                prog = _valid_program()
                prog["CARDIO_SCHEDULE"][0]["type"] = label
                errors = program_loader.validate_program_schema(prog)
                self.assertEqual(unknown in errors, flagged, errors)


if __name__ == "__main__":
    unittest.main()
