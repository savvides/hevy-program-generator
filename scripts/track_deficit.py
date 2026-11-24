#!/usr/bin/env python3
"""Deterministic Deficit & Body Composition Tracker.

Calculates nutritional targets and progress recommendations for body fat reduction.

Lean mass and resting energy are INDEPENDENT INPUTS: lean mass comes from a
body-composition estimate (weight and body-fat fraction), while resting energy
(RMR) comes from a separate estimate or measurement. The two are never derived
from one another.

The 1.18 g/lb estimated lean-mass protein multiplier, 70 g fat floor, and
0.50 lb/week default loss rate are illustrative coaching defaults, not
population-specific research prescriptions. See docs/nutrition_evidence_base.md
for scope and evidence limits.
"""
from __future__ import annotations

import argparse
from datetime import date
import math
import statistics

KG_TO_LB = 2.2046226218
# Weigh-in noise band around the target rate, in lb/wk.
RATE_TOLERANCE_LB = 0.10


def lbm_from_composition(weight_lb: float, bf_fraction: float) -> tuple[float, float]:
    """Estimated lean body mass in kg and lb from weight and a body-fat estimate."""
    if not math.isfinite(weight_lb) or weight_lb <= 0 or not math.isfinite(bf_fraction) or not 0 < bf_fraction < 1:
        raise ValueError("Weight must be finite and positive; body fat must be between 0 and 1")
    lbm_lb = weight_lb * (1.0 - bf_fraction)
    return lbm_lb / KG_TO_LB, lbm_lb


def required_weekly_rate(
    current_weight_lb: float,
    current_bf: float,
    target_bf: float,
    weeks_remaining: float,
) -> float:
    """Arithmetic rate to a deadline assuming fixed lean mass; not a recommendation."""
    if not math.isfinite(target_bf) or not 0 < target_bf < 1 or not math.isfinite(weeks_remaining):
        raise ValueError("Invalid target body fat or remaining weeks")
    if weeks_remaining <= 0:
        return 0.0
    _, lbm_lb = lbm_from_composition(current_weight_lb, current_bf)
    target_weight_lb = lbm_lb / (1.0 - target_bf)
    return max(0.0, (current_weight_lb - target_weight_lb) / weeks_remaining)


def weeks_until(deadline: date, today: date | None = None) -> float:
    """Whole-week runway to a deadline."""
    today = today or date.today()
    return max(0.0, (deadline - today).days / 7.0)


def calculate_targets(
    rmr: float = 1700.0,
    active_energy: float = 600.0,
    current_weight_lb: float = 180.0,
    current_bf: float = 0.20,
    target_bf: float = 0.15,
    weekly_loss_lb: float = 0.50,
) -> dict:
    """Compute arithmetic estimates, not validated physiological targets.

    rmr is estimated resting energy; current_weight_lb and current_bf come from a
    body-composition measurement. The two are not derived from one another.
    """
    if not all(math.isfinite(v) for v in (rmr, active_energy, target_bf, weekly_loss_lb)):
        raise ValueError("Nutrition inputs must be finite")
    if rmr <= 0 or active_energy < 0 or not 0 < target_bf < 1 or weekly_loss_lb < 0:
        raise ValueError("Invalid energy, body-fat target or loss rate")
    _, lbm_lb = lbm_from_composition(current_weight_lb, current_bf)

    target_weight_lb = lbm_lb / (1.0 - target_bf)
    fat_to_lose_lb = current_weight_lb - target_weight_lb
    if current_bf <= target_bf:
        target_weight_lb = current_weight_lb
        fat_to_lose_lb = 0.0
        weekly_loss_lb = 0.0

    tdee = rmr + active_energy
    daily_deficit = (weekly_loss_lb * 3500.0) / 7.0
    target_calories = tdee - daily_deficit

    # Planning default: 1.18 g/lb estimated LBM (~2.6 g/kg estimated LBM), not total-body-mass guidance.
    protein_g = round(lbm_lb * 1.18)
    fat_g = 70  # Planning default, not a research minimum.
    carb_g = round((target_calories - (protein_g * 4 + fat_g * 9)) / 4)
    if target_calories <= 0 or carb_g < 0:
        raise ValueError("Requested deficit cannot support the planned macros; review the rate and deadline")
    weeks_to_goal = fat_to_lose_lb / weekly_loss_lb if weekly_loss_lb > 0 else 0.0

    return {
        "lbm_lb": round(lbm_lb, 1),
        "current_weight_lb": round(current_weight_lb, 1),
        "target_weight_lb": round(target_weight_lb, 1),
        "fat_to_lose_lb": round(fat_to_lose_lb, 1),
        "tdee": round(tdee, 1),
        "daily_deficit": round(daily_deficit, 1),
        "target_calories": round(target_calories),
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carb_g": carb_g,
        "weeks_to_goal": round(weeks_to_goal, 1),
    }


def evaluate_progress(
    logs: list[tuple[str, float]],
    current_intake: float,
    target_weekly_loss_lb: float,
    tolerance_lb: float = RATE_TOLERANCE_LB,
) -> dict:
    """Describe a weight trend; never convert short-term scale noise into calorie changes.

    Three distinct dates over 14 days is a data-quality policy, not a physiological
    threshold. Median pairwise slopes use all observations and limit endpoint noise.
    Same-day observations are averaged before estimating the trend.
    """
    if not all(math.isfinite(v) for v in (current_intake, target_weekly_loss_lb, tolerance_lb)):
        raise ValueError("Progress inputs must be finite")
    if current_intake <= 0 or target_weekly_loss_lb < 0 or tolerance_lb < 0:
        raise ValueError("Invalid intake, planned loss rate or tolerance")
    by_day: dict[date, list[float]] = {}
    for day, weight in logs:
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Logged weights must be finite and positive")
        by_day.setdefault(date.fromisoformat(day), []).append(weight)
    points = sorted((day, statistics.mean(values)) for day, values in by_day.items())
    if len(points) < 3 or (points[-1][0] - points[0][0]).days < 14:
        return {
            "status": "INSUFFICIENT_DATA", "weekly_rate": 0.0,
            "target_weekly_rate": round(target_weekly_loss_lb, 2),
            "recommendation": "Log at least 3 distinct weigh-in dates spanning 14 days; keep measurement conditions consistent. No calorie adjustment calculated.",
        }
    slopes = [(w0 - w1) * 7 / (d1 - d0).days
              for i, (d0, w0) in enumerate(points) for d1, w1 in points[i + 1:]]
    weekly_rate = statistics.median(slopes)
    error = weekly_rate - target_weekly_loss_lb
    status = "ON_TRACK" if abs(error) <= tolerance_lb else "BEHIND" if error < 0 else "TOO_FAST"
    rec = (f"Trend {weekly_rate:.2f} vs planned {target_weekly_loss_lb:.2f} lb/wk. "
           "Review intake records, recovery, training performance and several weeks of trend before changing intake. "
           "No automatic calorie adjustment; a deadline does not establish a suitable loss rate.")
    return {"status": status, "weekly_rate": round(weekly_rate, 2),
            "target_weekly_rate": round(target_weekly_loss_lb, 2), "recommendation": rec}


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Deficit & Body Composition Tracker")
    parser.add_argument("--rmr", type=float, default=1700.0, help="Estimated resting energy in kcal/day (default: 1700.0)")
    parser.add_argument("--active-energy", type=float, default=600.0, help="Active energy burned in kcal (default: 600.0)")
    parser.add_argument("--current-weight", type=float, default=180.0, help="Measured bodyweight in lb (default: 180.0)")
    parser.add_argument("--current-bf", type=float, default=0.20, help="Current body fat fraction (default: 0.20)")
    parser.add_argument("--target-bf", type=float, default=0.15, help="Target body fat fraction (default: 0.15)")
    parser.add_argument("--weekly-loss", type=float, default=0.50, help="Explicit planned weekly loss in lb (default: 0.50; not increased by a deadline)")
    parser.add_argument("--deadline", type=str, default=None, help="Optional target date in YYYY-MM-DD format")
    parser.add_argument("--eval-logs", type=str, default=None, help="Comma-separated YYYY-MM-DD:weight_lb pairs to evaluate")
    parser.add_argument("--current-intake", type=float, default=None, help="Actual current intake in kcal for progress eval (default: the computed target)")
    args = parser.parse_args()

    deadline = date.fromisoformat(args.deadline) if args.deadline else None
    weekly_loss = 0.0 if args.current_bf <= args.target_bf else args.weekly_loss

    targets = calculate_targets(
        rmr=args.rmr,
        active_energy=args.active_energy,
        current_weight_lb=args.current_weight,
        current_bf=args.current_bf,
        target_bf=args.target_bf,
        weekly_loss_lb=weekly_loss,
    )
    if weekly_loss <= 0:
        reason = "target body fat already reached" if args.current_bf <= args.target_bf else "planned weekly loss is zero"
        print(f"=== No deficit planned: {reason} ===")
        print(f"Current Weight:     {args.current_weight} lbs at {args.current_bf*100:.1f}% body fat")
        print(f"Maintenance:        {args.rmr + args.active_energy:.0f} kcal/day")
        if args.eval_logs:
            print("--eval-logs not evaluated: no deficit is planned, so there is no loss target to compare against.")
        return

    print(f"=== Body Fat Reduction Targets ({args.current_bf*100:.1f}% -> {args.target_bf*100:.1f}%) ===")
    print(f"Current Weight:     {targets['current_weight_lb']} lbs ({targets['lbm_lb']} lbs Lean Mass, estimated)")
    print(f"Target Weight:      {targets['target_weight_lb']} lbs")
    print(f"Fat to Lose:        {targets['fat_to_lose_lb']} lbs over ~{targets['weeks_to_goal']} weeks")
    if deadline is not None:
        weeks_left = weeks_until(deadline)
        derived_rate = required_weekly_rate(args.current_weight, args.current_bf, args.target_bf, weeks_left)
        print(f"Runway:             {weeks_left:.1f} weeks to {deadline.isoformat()}")
        print(f"Required Rate:      {derived_rate:.2f} lb/wk (arithmetic only, not a recommended rate)")
    else:
        derived_rate = None
    print(f"Planned Rate:       {weekly_loss:.2f} lb/wk (coaching choice)")
    print(f"TDEE:               {targets['tdee']} kcal/day  (RMR {args.rmr:.0f} + active {args.active_energy:.0f})")
    print(f"Daily Deficit:      {targets['daily_deficit']} kcal/day")
    print(f"Target Calories:    {targets['target_calories']} kcal/day")
    print(f"Macros:             Protein: {targets['protein_g']}g | Fat: {targets['fat_g']}g | Carbs: {targets['carb_g']}g")
    print("Macro scope:        protein uses 1.18 g/lb estimated lean mass; fat is 70 g/day. Both are planning defaults.")
    if derived_rate is not None and weekly_loss < derived_rate - 0.005:
        print(f"Deadline review:    planned {weekly_loss:.2f} lb/wk is below the {derived_rate:.2f} lb/wk the runway requires.")

    if args.eval_logs:
        raw_pairs = [p.strip() for p in args.eval_logs.split(",") if p.strip()]
        logs = []
        for pair in raw_pairs:
            date_str, weight_str = pair.split(":")
            logs.append((date_str.strip(), float(weight_str.strip())))
        intake = args.current_intake if args.current_intake is not None else float(targets["target_calories"])
        eval_res = evaluate_progress(
            logs,
            current_intake=intake,
            target_weekly_loss_lb=weekly_loss,
        )
        print("\n=== Progress Evaluation ===")
        print(f"Status:             {eval_res['status']}")
        rate = "n/a" if eval_res["status"] == "INSUFFICIENT_DATA" else f"{eval_res['weekly_rate']:.2f} lb/wk"
        print(f"Weekly Rate:        {rate} (target {eval_res['target_weekly_rate']:.2f})")
        print(f"Recommendation:     {eval_res['recommendation']}")


if __name__ == "__main__":
    main()
