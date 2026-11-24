#!/usr/bin/env python3
"""Unit tests for the Hevy history analyzer (scripts/analyze_history.py)."""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_history import main  # noqa: E402

COVERAGE_HEADER = "=== Current-program lifts: history coverage ==="


def st(kind, kg, reps):
    return {"type": kind, "weight_kg": kg, "reps": reps}


def lift(title, sets):
    return {"title": title, "sets": sets}


def session(wid, start, exercises):
    return {"id": wid, "title": "Session", "start_time": start, "exercises": exercises}


def fake_build_routines(names):
    """Stand-in for build_routines so the tests never load the repo's active program."""
    return types.SimpleNamespace(
        ROUTINES=[{"exercises": [{"name": n} for n in names]}] if names else [],
        normalize=lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip(),
    )


def run(workouts, *args, routines=("Bench Press",), missing_build_routines=False):
    """Run main() against a temp data dir; return (exit code, stdout, stderr).

    An argparse rejection surfaces as exit code 2, as it would from the shell.
    """
    out, err = io.StringIO(), io.StringIO()
    # None in sys.modules makes `import build_routines` raise ImportError.
    module = None if missing_build_routines else fake_build_routines(routines)
    with tempfile.TemporaryDirectory() as directory:
        for w in workouts:
            (Path(directory) / f"{w['id']}.json").write_text(json.dumps(w))
        with mock.patch.dict(sys.modules, {"build_routines": module}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(["--data-dir", directory, *args])
            except SystemExit as exit_:
                code = exit_.code
    return code, out.getvalue(), err.getvalue()


def row(text, title):
    return next(line for line in text.splitlines() if line.startswith(title))


def coverage_line(text, name):
    section = text.split(COVERAGE_HEADER)[1]
    return next(line for line in section.splitlines() if line.strip().startswith(name))


class TestWorkSets(unittest.TestCase):
    def test_failure_and_dropset_count_and_warmup_does_not(self):
        sets = [st("warmup", 90, 3), st("normal", 60, 8), st("failure", 70, 5), st("dropset", 50, 12)]
        _, out, _ = run([session("w1", "2025-03-01T10:00:00Z", [lift("Bench Press", sets)])])
        line = row(out, "Bench Press")
        self.assertEqual(line.count("70.0 kg"), 2, line)  # last top set and best set
        self.assertNotIn("90.0 kg", line)  # the heaviest set is a warmup
        self.assertIn("82 kg/180 lb", line)  # Epley 70 x 5

    def test_failure_only_lift_has_a_best_set(self):
        _, out, _ = run([session("w1", "2025-03-01T10:00:00Z", [lift("Chin Up", [st("failure", 10, 6)])])])
        line = row(out, "Chin Up")
        self.assertEqual(line.count("10.0 kg"), 2, line)
        self.assertIn("2025-03-01", line)

    def test_untyped_set_counts_as_work_set(self):
        _, out, _ = run([session("w1", "2025-03-01T10:00:00Z", [lift("Row", [st(None, 40, 10)])])])
        self.assertEqual(row(out, "Row").count("40.0 kg"), 2)

    def test_warmup_only_lift_has_no_best_set(self):
        _, out, _ = run([session("w1", "2025-03-01T10:00:00Z", [lift("Squat", [st("warmup", 60, 5)])])])
        self.assertNotIn("kg", row(out, "Squat"))


class TestCoverageSection(unittest.TestCase):
    WORKOUTS = [
        session("w1", "2025-01-10T10:00:00Z", [lift("Back Squat", [st("normal", 100, 5)])]),
        session("w2", "2025-03-10T10:00:00Z", [lift("Bench Press", [st("normal", 60, 8)])]),
    ]
    ROUTINES = ("Back Squat", "Bench Press", "Deadlift")

    def test_never_logged_label_without_since(self):
        _, out, _ = run(self.WORKOUTS, routines=self.ROUTINES)
        self.assertIn("last=2025-01-10", coverage_line(out, "Back Squat"))
        self.assertIn("NEVER LOGGED", coverage_line(out, "Deadlift"))

    def test_lift_before_the_since_window_is_not_called_never_logged(self):
        _, out, _ = run(self.WORKOUTS, "--since", "2025-03-01", routines=self.ROUTINES)
        squat = coverage_line(out, "Back Squat")
        self.assertNotIn("NEVER LOGGED", squat)
        self.assertIn("not logged since 2025-03-01", squat)
        self.assertIn("n=  1", coverage_line(out, "Bench Press"))

    def test_unloadable_program_warns_on_stderr_and_still_exits_zero(self):
        code, out, err = run(self.WORKOUTS, missing_build_routines=True)
        self.assertEqual(code, 0)
        self.assertNotIn(COVERAGE_HEADER, out)
        self.assertIn("coverage", err)
        self.assertIn("skipped", err)

    def test_program_without_routines_warns_on_stderr_and_still_exits_zero(self):
        code, out, err = run(self.WORKOUTS, routines=())
        self.assertEqual(code, 0)
        self.assertNotIn(COVERAGE_HEADER, out)
        self.assertIn("coverage", err)
        self.assertIn("skipped", err)


class TestCliAndLoading(unittest.TestCase):
    def assert_argparse_error(self, *args, mention):
        code, out, err = run([session("w1", "2025-03-01T10:00:00Z", [lift("Bench Press", [st("normal", 60, 8)])])], *args)
        self.assertEqual(code, 2)
        self.assertIn(mention, err)
        self.assertEqual(out, "")

    def test_bad_since_date_is_an_argparse_error(self):
        self.assert_argparse_error("--since", "03/05/2025", mention="--since")

    def test_top_must_be_positive(self):
        for value in ("-2", "0"):
            with self.subTest(top=value):
                self.assert_argparse_error("--top", value, mention="--top")

    def test_null_exercises_and_null_sets_do_not_crash(self):
        workouts = [
            {"id": "w1", "start_time": "2025-03-01T10:00:00Z", "exercises": None},
            session("w2", "2025-03-02T10:00:00Z", [lift("Bench Press", None)]),
            session("w3", "2025-03-03T10:00:00Z", [lift("Bench Press", [st("normal", 60, 8)])]),
        ]
        code, out, _ = run(workouts)
        self.assertEqual(code, 0)
        self.assertIn("sessions:      3", out)
        self.assertEqual(row(out, "Bench Press").count("60.0 kg"), 2)


if __name__ == "__main__":
    unittest.main()
