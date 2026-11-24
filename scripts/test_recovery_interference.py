"""Recovery policy and cardio accounting regressions."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from eval_recovery_interference import (
    check_cardio_distribution, check_cardio_modality, check_compound_rpe_bounds,
    check_recovery_spacing, interval_minutes, is_heavy_lower_routine,
)
from program_loader import load_program


class TestCardioAccounting(unittest.TestCase):
    def test_zero_interval_work_is_flagged_only_for_vo2_goal(self):
        cardio = [{"type": "Zone 2", "duration_minutes": 60}]
        self.assertTrue(check_cardio_distribution(cardio, "vo2max")[2])
        self.assertEqual(check_cardio_distribution(cardio, "strength")[2], [])

    def test_standard_protocols_are_not_rejected_by_arbitrary_minimum(self):
        for protocol in ("4x4", "5x3"):
            cardio = [{"type": f"VO2 Max {protocol}", "duration_minutes": 40},
                      {"type": "Zone 2", "duration_minutes": 60}]
            self.assertEqual(check_cardio_distribution(cardio, "vo2max")[2], [])

    def test_interval_recovery_is_not_automatically_zone2(self):
        cardio = [{"type": "VO2 Max 6x4", "duration_minutes": 54, "interval_work_min": 24},
                  {"type": "Zone 2", "duration_minutes": 120}]
        easy, work, errors = check_cardio_distribution(cardio, "vo2max")
        self.assertAlmostEqual(easy, 120 / 174)
        self.assertAlmostEqual(work, 24 / 174)
        self.assertEqual(errors, [])
        self.assertLess(easy + work, 1)

    def test_unknown_protocol_requires_explicit_dose(self):
        self.assertTrue(check_cardio_distribution([{"type": "HIIT", "duration_minutes": 40}])[2])

    def test_configured_ceiling_remains_a_policy(self):
        errors = check_cardio_distribution([{"type": "VO2 Max 6x4", "duration_minutes": 30, "interval_work_min": 24}])[2]
        self.assertTrue(any("coaching policy" in e for e in errors))

    def test_program_schedules_pass(self):
        for path in Path(__file__).resolve().parent.parent.glob("programs/*.py"):
            prog = load_program(str(path))
            self.assertEqual(check_cardio_distribution(prog["CARDIO_SCHEDULE"], prog["PROGRAM_METADATA"].get("primary_goal", ""))[2], [], path.name)

    def test_custom_recovery_buffer_is_honored(self):
        routines = [{"name": "Lower", "day_key": "Friday", "exercises": [{"name": "Squat", "compound": True}]}]
        cardio = [{"day": "Wednesday", "type": "HIIT"}]
        self.assertEqual(check_recovery_spacing(routines, cardio, 48)[0], [])
        errors, logs = check_recovery_spacing(routines, cardio, 60)
        self.assertTrue(errors)
        self.assertTrue(any("unverified" in line for line in logs))


class TestGoalSpelling(unittest.TestCase):
    """primary_goal is free text: every spelling of VO2 max must reach the VO2-primary checks."""

    VARIANTS = ("vo2max", "VO2max", "VO2 max", "VO2 Max", "vo2_max", "vo2-max", " VO2  Max ")

    def test_spelling_variants_trigger_the_no_cardio_check(self):
        for goal in self.VARIANTS:
            with self.subTest(goal=goal):
                self.assertEqual(check_cardio_distribution([], goal)[2], ["No cardio duration scheduled."])

    def test_spelling_variants_trigger_the_no_interval_work_check(self):
        cardio = [{"type": "Zone 2", "duration_minutes": 60}]
        for goal in self.VARIANTS:
            with self.subTest(goal=goal):
                self.assertEqual(check_cardio_distribution(cardio, goal)[2],
                                 ["VO2-primary schedule has no interval work; review goal coverage."])

    def test_other_goals_do_not_trigger_the_vo2_checks(self):
        cardio = [{"type": "Zone 2", "duration_minutes": 60}]
        for goal in ("", "strength", "aerobic support", "vo2 max strength"):
            with self.subTest(goal=goal):
                self.assertEqual(check_cardio_distribution([], goal)[2], [])
                self.assertEqual(check_cardio_distribution(cardio, goal)[2], [])


class TestIntervalProtocolMatching(unittest.TestCase):
    """A protocol name earns its dose only as a whole token, never as a substring of a longer label."""

    def test_named_protocols_carry_their_dose(self):
        self.assertEqual(interval_minutes({"type": "VO2 Max 4x4"}), 16.0)
        self.assertEqual(interval_minutes({"type": "VO2 Max 5x3"}), 15.0)
        self.assertEqual(interval_minutes({"type": "HIIT 5x3 min"}), 15.0)

    def test_labels_that_only_contain_a_protocol_are_not_credited_its_dose(self):
        for label in ("VO2 Max 14x4", "VO2 Max 15x3", "HIIT 5x30s", "VO2 Max 4x45s"):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "Unknown interval protocol"):
                    interval_minutes({"type": label})
                errors = check_cardio_distribution([{"type": label, "duration_minutes": 90}])[2]
                self.assertIn("Unknown interval protocol requires interval_work_min", errors)

    def test_explicit_dose_still_wins_for_a_longer_label(self):
        self.assertEqual(interval_minutes({"type": "VO2 Max 14x4", "interval_work_min": 56}), 56.0)


class TestCardioModality(unittest.TestCase):
    def _violations(self, modality):
        return check_cardio_modality([{"day": "Friday", "modality": modality}])

    def test_cycling_modalities_pass(self):
        for modality in ("Stationary Bike", "Cycling", "Outdoor Cycle", "BikeErg", "Bike Erg"):
            with self.subTest(modality=modality):
                self.assertEqual(self._violations(modality), [])

    def test_other_modalities_are_flagged_even_when_they_contain_erg(self):
        for modality in ("Treadmill", "Overground Running", "Rowing Ergometer", "Energy Jam"):
            with self.subTest(modality=modality):
                violations = self._violations(modality)
                self.assertEqual(len(violations), 1)
                self.assertIn("Modality violation on Friday", violations[0])
                self.assertIn(modality, violations[0])


class TestCompoundRpeBound(unittest.TestCase):
    def _routines(self, **exercise):
        return [{"name": "Lift A", "exercises": [{"name": "Squat", "compound": True, **exercise}]}]

    def test_compound_lift_above_rpe_8_is_flagged(self):
        for rpe in (9, 8.5):
            with self.subTest(rpe=rpe):
                errors = check_compound_rpe_bounds(self._routines(rpe=rpe))
                self.assertEqual(len(errors), 1)
                self.assertIn("Proximity to failure violation", errors[0])
                self.assertIn(f"RPE {rpe}", errors[0])

    def test_compound_at_the_ceiling_and_isolation_at_rpe_10_pass(self):
        self.assertEqual(check_compound_rpe_bounds(self._routines(rpe=8)), [])
        self.assertEqual(check_compound_rpe_bounds(self._routines(rpe=10, compound=False)), [])


def _lower(name, day, start_time=None):
    routine = {"name": name, "day_key": day, "exercises": [{"name": "Squat", "compound": True}]}
    if start_time:
        routine["start_time"] = start_time
    return routine


class TestSpacingFailurePaths(unittest.TestCase):
    def test_two_heavy_lower_days_too_close_are_flagged(self):
        errors, _ = check_recovery_spacing([_lower("Lower A", "Monday"), _lower("Lower B", "Tuesday")], [])
        # Monday to Tuesday is 24h; Tuesday to Monday (144h) is fine.
        self.assertEqual(errors, ["Scheduling policy: Lower A → Lower B is 24h, below configured 48h."])

    def test_heavy_lower_days_with_enough_gap_pass(self):
        errors, _ = check_recovery_spacing([_lower("Lower A", "Monday"), _lower("Lower B", "Thursday")], [])
        self.assertEqual(errors, [])

    def test_timed_gap_wraps_across_the_sunday_monday_boundary(self):
        interval = {"name": "VO2", "day": "Monday", "type": "VO2 Max 4x4", "start_time": "07:00"}
        errors, _ = check_recovery_spacing([_lower("Lower", "Sunday", "18:00")], [interval])
        # Exact text: without the weekly wrap the gap would read as -155h, which is also below 48h.
        self.assertEqual(errors, ["Scheduling policy: Lower → VO2 is 13h, below configured 48h."])

    def test_timed_schedule_that_only_looks_early_in_the_week_is_not_flagged(self):
        interval = {"name": "VO2", "day": "Wednesday", "type": "VO2 Max 4x4", "start_time": "08:00"}
        errors, _ = check_recovery_spacing([_lower("Lower", "Sunday", "08:00")], [interval])
        self.assertEqual(errors, [])  # Sunday to Wednesday is 72h across the week boundary


class TestHeavyLowerDetection(unittest.TestCase):
    """The week structure depends on this: only compound=True lower work forces 48h clearance."""

    def test_compound_lower_is_heavy(self):
        self.assertTrue(is_heavy_lower_routine({"exercises": [
            {"name": "Deadlift (Trap bar)", "compound": True, "muscle_groups": ["hamstrings"]},
        ]}))

    def test_isolation_lower_is_not_heavy(self):
        self.assertFalse(is_heavy_lower_routine({"exercises": [
            {"name": "Leg Extension (Machine)", "compound": False, "muscle_groups": ["quads"]},
        ]}))


if __name__ == "__main__":
    unittest.main()
