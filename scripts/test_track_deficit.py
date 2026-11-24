import contextlib
import io
import sys
from datetime import date
from pathlib import Path
import unittest
from unittest import mock

# Ensure scripts directory is in sys.path when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from track_deficit import (
    calculate_targets,
    evaluate_progress,
    lbm_from_composition,
    main,
    required_weekly_rate,
    weeks_until,
)


class TestBodyComposition(unittest.TestCase):
    def test_lbm_comes_from_measurement_not_from_rmr(self):
        """Lean mass is computed from measured weight and body-fat fraction, never RMR."""
        lbm_kg, lbm_lb = lbm_from_composition(180.0, 0.20)
        self.assertAlmostEqual(lbm_lb, 144.0, delta=0.1)
        self.assertAlmostEqual(lbm_kg, 65.3, delta=0.1)

    def test_lean_mass_is_independent_of_resting_energy(self):
        """Changing RMR must move TDEE and nothing else about body composition."""
        low = calculate_targets(rmr=1500.0)
        high = calculate_targets(rmr=1700.0)
        self.assertEqual(low["lbm_lb"], high["lbm_lb"])
        self.assertEqual(low["current_weight_lb"], high["current_weight_lb"])
        self.assertEqual(low["target_weight_lb"], high["target_weight_lb"])
        self.assertAlmostEqual(high["tdee"] - low["tdee"], 200.0, places=1)


class TestTargets(unittest.TestCase):
    def test_calculate_targets_from_measured_inputs(self):
        targets = calculate_targets(
            rmr=1700.0,
            active_energy=600.0,
            current_weight_lb=180.0,
            current_bf=0.20,
            target_bf=0.15,
            weekly_loss_lb=0.50,
        )
        self.assertAlmostEqual(targets["tdee"], 2300.0, places=1)
        self.assertAlmostEqual(targets["lbm_lb"], 144.0, delta=0.1)
        self.assertAlmostEqual(targets["current_weight_lb"], 180.0, delta=0.1)
        self.assertAlmostEqual(targets["target_weight_lb"], 169.4, delta=0.2)
        self.assertAlmostEqual(targets["fat_to_lose_lb"], 10.6, delta=0.2)
        self.assertAlmostEqual(targets["daily_deficit"], 250.0, places=1)
        self.assertAlmostEqual(targets["target_calories"], 2050.0, delta=1.0)
        # Macros from the planning constants in track_deficit.py (1.18 g/lb LBM, 70 g fat):
        # lean mass 180.0 * (1 - 0.20) = 144.0 lb; protein round(144.0 * 1.18) = 170 g;
        # carbs round((2050 - (170 * 4 + 70 * 9)) / 4) = round(740 / 4) = 185 g.
        self.assertEqual(targets["protein_g"], 170)
        self.assertEqual(targets["fat_g"], 70)
        self.assertEqual(targets["carb_g"], 185)


class TestDerivedRate(unittest.TestCase):
    def test_required_rate_from_runway(self):
        """10.59 lb over 20.0 weeks = 0.529 lb/wk."""
        rate = required_weekly_rate(180.0, 0.20, 0.15, 20.0)
        self.assertAlmostEqual(rate, 0.529, places=2)

    def test_rate_rises_as_runway_shrinks(self):
        """Time spent off-rate raises the arithmetic rate the remainder demands."""
        early = required_weekly_rate(180.0, 0.20, 0.15, 40.0)
        later = required_weekly_rate(180.0, 0.20, 0.15, 25.0)
        self.assertGreater(later, early)

    def test_rate_is_zero_once_target_reached(self):
        self.assertEqual(required_weekly_rate(170.0, 0.15, 0.15, 20.0), 0.0)

    def test_no_runway_does_not_divide_by_zero(self):
        self.assertEqual(required_weekly_rate(180.0, 0.20, 0.15, 0.0), 0.0)

    def test_zero_rate_does_not_crash_calculate_targets(self):
        """required_weekly_rate returns 0.0 at goal or past a deadline."""
        targets = calculate_targets(weekly_loss_lb=0.0)
        self.assertEqual(targets["weeks_to_goal"], 0.0)

    def test_target_at_or_below_current_bf_does_not_crash(self):
        targets = calculate_targets(current_bf=0.15, target_bf=0.15, weekly_loss_lb=0.0)
        self.assertEqual(targets["weeks_to_goal"], 0.0)

    def test_weeks_until_deadline(self):
        sample_deadline = date(2027, 6, 1)
        self.assertAlmostEqual(weeks_until(sample_deadline, today=date(2026, 9, 1)), 39.0, places=1)
        self.assertEqual(weeks_until(sample_deadline, today=date(2027, 8, 1)), 0.0)


class TestProgressEvaluation(unittest.TestCase):
    def test_on_track_against_the_target_rate(self):
        logs = [("2026-08-01", 180.0), ("2026-08-08", 179.5), ("2026-08-15", 179.0)]  # 0.50 lb/wk
        result = evaluate_progress(logs, current_intake=2050.0, target_weekly_loss_lb=0.50)
        self.assertEqual(result["status"], "ON_TRACK")

    def test_behind_target(self):
        logs = [("2026-08-01", 180.0), ("2026-08-08", 179.8), ("2026-08-15", 179.6)]  # 0.20 lb/wk
        result = evaluate_progress(logs, current_intake=2050.0, target_weekly_loss_lb=0.50)
        self.assertEqual(result["status"], "BEHIND")
        self.assertIn("No automatic calorie adjustment", result["recommendation"])

    def test_too_fast(self):
        logs = [("2026-08-01", 180.0), ("2026-08-08", 178.5), ("2026-08-15", 177.0)]  # 1.50 lb/wk
        result = evaluate_progress(logs, current_intake=2050.0, target_weekly_loss_lb=0.50)
        self.assertEqual(result["status"], "TOO_FAST")
        self.assertIn("No automatic calorie adjustment", result["recommendation"])

    def test_bands_follow_the_target_not_a_fixed_range(self):
        """0.50 lb/wk is ON_TRACK against a 0.50 target but BEHIND against a 1.00 target."""
        logs = [("2026-08-01", 180.0), ("2026-08-08", 179.5), ("2026-08-15", 179.0)]
        self.assertEqual(
            evaluate_progress(logs, 2050.0, target_weekly_loss_lb=0.50)["status"], "ON_TRACK"
        )
        self.assertEqual(
            evaluate_progress(logs, 2050.0, target_weekly_loss_lb=1.00)["status"], "BEHIND"
        )

    def test_logs_are_sorted_before_measuring(self):
        """Entries pasted out of order must sort chronologically before slope estimation."""
        ordered = [("2026-08-01", 184.0), ("2026-08-15", 181.0), ("2026-09-01", 179.0)]
        shuffled = [("2026-08-15", 181.0), ("2026-08-01", 184.0), ("2026-09-01", 179.0)]
        self.assertEqual(
            evaluate_progress(ordered, 2050.0, 0.50)["weekly_rate"],
            evaluate_progress(shuffled, 2050.0, 0.50)["weekly_rate"],
        )
        self.assertAlmostEqual(evaluate_progress(shuffled, 2050.0, 0.50)["weekly_rate"], 1.13, places=2)

    def test_insufficient_data(self):
        self.assertEqual(
            evaluate_progress([("2026-08-01", 180.0)], 2050.0, 0.50)["status"], "INSUFFICIENT_DATA"
        )
        self.assertEqual(
            evaluate_progress(
                [("2026-08-01", 180.0), ("2026-08-01", 179.6)], 2050.0, 0.50
            )["status"],
            "INSUFFICIENT_DATA",
        )

    def test_insufficient_data_boundaries(self):
        """The rule is at least 3 distinct dates AND a span of at least 14 days."""
        cases = {
            "2 dates over 30 days": [("2026-08-01", 180.0), ("2026-08-31", 178.6)],
            "3 dates over 10 days": [("2026-08-01", 180.0), ("2026-08-05", 179.7), ("2026-08-11", 179.5)],
            "3 dates over 13 days": [("2026-08-01", 180.0), ("2026-08-07", 179.7), ("2026-08-14", 179.5)],
        }
        for label, logs in cases.items():
            with self.subTest(label):
                self.assertEqual(evaluate_progress(logs, 2050.0, 0.50)["status"], "INSUFFICIENT_DATA")
        at_boundary = [("2026-08-01", 180.0), ("2026-08-08", 179.5), ("2026-08-15", 179.0)]  # 14 days
        self.assertNotEqual(evaluate_progress(at_boundary, 2050.0, 0.50)["status"], "INSUFFICIENT_DATA")


def run_main(*args):
    out = io.StringIO()
    with mock.patch.object(sys, "argv", ["track_deficit.py", *args]), contextlib.redirect_stdout(out):
        main()
    return out.getvalue()


class TestMainOutput(unittest.TestCase):
    TOO_SHORT = "2026-08-01:180.0,2026-08-08:179.6"
    ENOUGH = "2026-08-01:180.0,2026-08-08:179.5,2026-08-15:179.0"

    def test_insufficient_data_does_not_print_a_measured_rate(self):
        out = run_main("--eval-logs", self.TOO_SHORT)
        self.assertIn("INSUFFICIENT_DATA", out)
        self.assertIn("Weekly Rate:        n/a", out)
        self.assertNotIn("0.0 lb/wk", out)

    def test_sufficient_data_still_prints_the_rate(self):
        out = run_main("--eval-logs", self.ENOUGH)
        self.assertIn("Status:             ON_TRACK", out)
        self.assertIn("Weekly Rate:        0.50 lb/wk (target 0.50)", out)

    def test_eval_logs_is_not_silently_dropped_when_no_deficit_is_planned(self):
        for label, extra in (("zero planned loss", ["--weekly-loss", "0"]),
                             ("target already reached", ["--current-bf", "0.15", "--target-bf", "0.15"])):
            with self.subTest(label):
                out = run_main("--eval-logs", self.ENOUGH, *extra)
                self.assertIn("No deficit planned", out)
                self.assertIn("--eval-logs not evaluated", out)

    def test_no_deficit_without_eval_logs_prints_no_eval_note(self):
        self.assertNotIn("--eval-logs", run_main("--weekly-loss", "0"))

    def test_optional_deadline_prints_runway(self):
        out = run_main("--deadline", "2027-06-01")
        self.assertIn("Runway:", out)
        self.assertIn("Required Rate:", out)


if __name__ == "__main__":
    unittest.main()
