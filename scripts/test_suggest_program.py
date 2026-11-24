#!/usr/bin/env python3
"""Unit tests for evidence-based program suggester."""
from __future__ import annotations

import ast
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import suggest_program  # noqa: E402
from suggest_program import generate_program_code  # noqa: E402
from program_loader import load_program  # noqa: E402


class TestSuggestProgram(unittest.TestCase):
    def test_reported_context_survives_generated_program_load(self):
        code = generate_program_code(days=2, age_years=18, sex=" nonbinary ", primary_goal="aerobic support")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            path.write_text(code)
            metadata = load_program(str(path))["PROGRAM_METADATA"]
        self.assertEqual(metadata["age_years"], 18)
        self.assertEqual(metadata["sex"], " nonbinary ")
        self.assertEqual(metadata["primary_goal"], "aerobic support")

    def test_omitted_context_is_not_inferred_from_focus(self):
        namespace = {}
        exec(generate_program_code(days=2, focus="Men 40+ Hypertrophy"), namespace)
        for field in ("age_years", "sex", "primary_goal"):
            self.assertNotIn(field, namespace["PROGRAM_METADATA"])

    def test_context_does_not_change_prescriptions_or_constraints(self):
        for days in (2, 3, 4):
            baseline = {}
            exec(generate_program_code(days=days), baseline)
            for age, sex, goal in ((18, "female", "hypertrophy"), (65, "male", "strength"),
                                   (90, "nonbinary", "aerobic support"), (40, "unspecified", "unknown")):
                with self.subTest(days=days, age=age, sex=sex):
                    reported = {}
                    exec(generate_program_code(days=days, age_years=age, sex=sex, primary_goal=goal), reported)
                    self.assertEqual(reported["ROUTINES"], baseline["ROUTINES"])
                    self.assertEqual(reported["CARDIO_SCHEDULE"], baseline["CARDIO_SCHEDULE"])
                    self.assertEqual(reported["PROGRAM_METADATA"]["constraints"], baseline["PROGRAM_METADATA"]["constraints"])

    def test_invalid_generator_context_raises_clear_error(self):
        for age in (True, False, 0, -1, 40.5, float("inf"), float("nan"), "40"):
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, "age_years"):
                generate_program_code(days=2, age_years=age)
        for field in ("sex", "primary_goal"):
            for value in ("", " \t", 1):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                    generate_program_code(days=2, **{field: value})

    def test_adult_generator_rejects_under_18(self):
        for age in (1, 17):
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, "[Aa]dult.*18"):
                generate_program_code(days=2, age_years=age)

    def test_invalid_cli_context_creates_no_output_or_parent(self):
        cases = (("--age-years", "17", "adult"), ("--age-years", "0", "age_years"),
                 ("--age-years", "40.5", "--age-years"), ("--sex", " ", "sex"),
                 ("--primary-goal", "", "primary_goal"))
        with tempfile.TemporaryDirectory() as directory:
            for option, value, diagnostic in cases:
                with self.subTest(option=option, value=value):
                    path = Path(directory) / "new-parent" / "program.py"
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS_DIR / "suggest_program.py"), "--days", "2",
                         option, value, "--output", str(path), "--no-qa"],
                        capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(path.exists())
                    self.assertFalse(path.parent.exists())

    def test_generate_3day_program(self):
        code = generate_program_code(days=3, time_cap=60, focus="Men 40+ Joint Health")
        self.assertIn("PROGRAM_METADATA", code)
        self.assertIn("ROUTINES", code)
        self.assertIn("CARDIO_SCHEDULE", code)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            prog = load_program(temp_path)
            self.assertEqual(prog["PROGRAM_METADATA"]["session_time_cap_minutes"], 60)
            self.assertEqual(len(prog["ROUTINES"]), 3)

            # Run full QA gatekeeper on generated code
            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "qa_program.py"), "--program", temp_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"QA failed for 3-day program:\n{res.stdout}\n{res.stderr}")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_generate_2day_program(self):
        code = generate_program_code(days=2, time_cap=60, focus="Men 40+ Joint Health")
        self.assertIn("PROGRAM_METADATA", code)
        self.assertIn("ROUTINES", code)
        self.assertIn("CARDIO_SCHEDULE", code)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            prog = load_program(temp_path)
            self.assertEqual(prog["PROGRAM_METADATA"]["session_time_cap_minutes"], 60)
            self.assertEqual(len(prog["ROUTINES"]), 2)

            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "qa_program.py"), "--program", temp_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"QA failed for 2-day program:\n{res.stdout}\n{res.stderr}")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_generate_4day_program(self):
        code = generate_program_code(days=4, time_cap=60, focus="Men 40+ Joint Health")
        self.assertIn("PROGRAM_METADATA", code)
        self.assertIn("ROUTINES", code)
        self.assertIn("CARDIO_SCHEDULE", code)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            prog = load_program(temp_path)
            self.assertEqual(prog["PROGRAM_METADATA"]["session_time_cap_minutes"], 60)
            self.assertEqual(len(prog["ROUTINES"]), 4)

            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "qa_program.py"), "--program", temp_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"QA failed for 4-day program:\n{res.stdout}\n{res.stderr}")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_invalid_days_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_program_code(days=5, time_cap=60)
        with self.assertRaises(ValueError):
            generate_program_code(days=1, time_cap=60)

    def test_cli_execution_and_qa_preflight(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            temp_path = f.name
        try:
            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "suggest_program.py"),
                    "--days",
                    "3",
                    "--time-cap",
                    "60",
                    "--focus",
                    "Men 40+ Joint Health",
                    "--age-years",
                    "65",
                    "--sex",
                    "unspecified",
                    "--primary-goal",
                    "aerobic support",
                    "--output",
                    temp_path,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"CLI runner failed:\n{res.stdout}\n{res.stderr}")
            self.assertTrue(Path(temp_path).exists())
            self.assertGreater(Path(temp_path).stat().st_size, 100)
            metadata = load_program(temp_path)["PROGRAM_METADATA"]
            self.assertEqual(metadata["age_years"], 65)
            self.assertEqual(metadata["sex"], "unspecified")
            self.assertEqual(metadata["primary_goal"], "aerobic support")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_incomplete_equipment_registry_fails_closed(self):
        for equipment in ("dumbbell", "bodyweight"):
            with self.subTest(equipment=equipment), self.assertRaisesRegex(ValueError, "equipment"):
                generate_program_code(days=2, equipment=equipment)

    def test_incomplete_joint_profile_registry_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "joint_profile"):
            generate_program_code(days=2, joint_profile="fai_safe", tier="advanced")

    def test_generated_constraints_survive_and_detect_tampering(self):
        from program_loader import validate_program_schema
        namespace = {}
        exec(generate_program_code(days=2), namespace)
        namespace["PROGRAM_METADATA"]["constraints"]["equipment"] = ["bodyweight"]
        errors = validate_program_schema(namespace)
        self.assertTrue(any("constraints" in error for error in errors))


class TestGeneratedProgramSafety(unittest.TestCase):
    # Every (days, tier) the registry can fill with the standard joint profile.
    COMBINATIONS = ((2, "returning"), (2, "intermediate"), (2, "advanced"),
                    (3, "intermediate"), (3, "advanced"), (4, "intermediate"), (4, "advanced"))

    def test_time_cap_reaches_metadata(self):
        for days in (2, 3, 4):
            with self.subTest(days=days):
                namespace = {}
                exec(generate_program_code(days=days, time_cap=45), namespace)
                self.assertEqual(namespace["PROGRAM_METADATA"]["session_time_cap_minutes"], 45)

    def test_no_routine_repeats_an_exercise(self):
        for days, tier in self.COMBINATIONS:
            with self.subTest(days=days, tier=tier):
                namespace = {}
                exec(generate_program_code(days=days, tier=tier), namespace)
                for routine in namespace["ROUTINES"]:
                    names = [exercise["name"] for exercise in routine["exercises"]]
                    self.assertEqual(len(names), len(set(names)), f"{routine['name']}: {names}")

    def test_non_positive_time_cap_is_rejected(self):
        for time_cap in (0, -30):
            with self.subTest(time_cap=time_cap), self.assertRaisesRegex(ValueError, "time_cap"):
                generate_program_code(days=2, time_cap=time_cap)

    def test_non_positive_time_cap_writes_nothing_from_the_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "suggest_program.py"), "--days", "2",
                 "--time-cap=-30", "--output", str(path), "--no-qa"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("time_cap", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(path.exists())

    def test_focus_text_cannot_break_or_inject_into_the_generated_file(self):
        focuses = (
            r"Home gym C:\users\new",
            'Gym """\nINJECTED = True\n"""',
            "Gym '''\nINJECTED = True\n'''",
            'Gym\nINJECTED = True',
        )
        for focus in focuses:
            with self.subTest(focus=focus):
                code = generate_program_code(days=2, focus=focus)
                ast.parse(code)
                namespace = {}
                exec(code, namespace)
                self.assertNotIn("INJECTED", namespace)
                metadata = namespace["PROGRAM_METADATA"]
                self.assertEqual(metadata["title"], f"Full-Body 2x \u2014 {focus}")
                self.assertEqual(metadata["target_demographic"], focus)
                self.assertIn(focus, metadata["description"])

    def run_cli(self, path):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = suggest_program.main(["--days", "2", "--output", str(path)])
        return code

    def test_failed_qa_leaves_no_file_at_the_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            with mock.patch.object(suggest_program, "run_qa_preflight", return_value=False):
                self.assertEqual(self.run_cli(path), 1)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_failed_qa_does_not_clobber_an_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            path.write_text("PREVIOUS GOOD PROGRAM\n")
            with mock.patch.object(suggest_program, "run_qa_preflight", return_value=False):
                self.assertEqual(self.run_cli(path), 1)
            self.assertEqual(path.read_text(), "PREVIOUS GOOD PROGRAM\n")
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["program.py"])

    def test_passing_qa_installs_the_program_that_was_checked(self):
        checked = {}

        def fake_qa(program_file):
            checked["text"] = Path(program_file).read_text(encoding="utf-8")
            return True

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            path.write_text("PREVIOUS PROGRAM\n")
            with mock.patch.object(suggest_program, "run_qa_preflight", side_effect=fake_qa):
                self.assertEqual(self.run_cli(path), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), checked["text"])
            self.assertIn("PROGRAM_METADATA", checked["text"])
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["program.py"])


if __name__ == "__main__":
    unittest.main()

