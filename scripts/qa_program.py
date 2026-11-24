#!/usr/bin/env python3
"""Master Program QA Engine: Configured Policy Checks & Pre-Flight Gatekeeper.

Orchestrates all test and evaluation suites across 8 dimensions:
  1. Catalog & Structural Invariants (test_build_routines.py)
  2. Session Duration & Fatigue Density <= cap min (estimate_session_time.py)
  3. Volume Floors/Ceilings & Frequency Tiers (eval_program_volume.py)
  4. Concurrent Recovery & Interference Spacing (eval_recovery_interference.py)
  5. Proximity to Failure & Spinal Safety (eval_recovery_interference.py)
  6. Evidence Grounding & Consensus Validation (eval_evidence_grounding.py)
  7. Cache Schema Integrity — citation keys, years, ids (check_cache_schema.py)
  8. Import Health — every module imports, every CLI parser builds (check_import_health.py)

Exits 0 if all gates pass; exits 1 with actionable diagnostic output if any gate fails.

Run: python3 scripts/qa_program.py [--program <path>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPTS_DIR))
from program_loader import load_program  # noqa: E402


def run_gate(
    name: str,
    script_name: str,
    program_path: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """Execute a python gate script and return (passed, stdout)."""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    if program_path:
        cmd.extend(["--program", program_path])
    if extra_args:
        cmd.extend(extra_args)
    res = subprocess.run(
        cmd,
        cwd=str(SCRIPTS_DIR),
        capture_output=True,
        text=True,
    )
    passed = (res.returncode == 0)
    output = res.stdout if passed else (res.stdout + "\n" + res.stderr)
    return passed, output.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None, help="Path to training program python file")
    args = parser.parse_args(argv)

    prog = load_program(args.program)
    metadata = prog.get("PROGRAM_METADATA", {})
    title = metadata.get("title", "Training Program")
    cap_min = metadata.get("session_time_cap_minutes", 60)
    file_path = prog.get("_file_path", args.program or "default")

    print("=" * 80)
    print("           PROGRAM QA SCORECARD")
    print(f"           Program: {title}")
    print(f"           Source:  {file_path}")
    print("           Evidence and policy limits: docs/evidence_base.md")
    print("=" * 80)

    scorecard: list[tuple[str, bool, str]] = []

    # 1. Structural & Catalog Invariants
    p1, out1 = run_gate("Catalog & Invariant Tests", "test_build_routines.py", file_path)
    scorecard.append(("1. CATALOG & STRUCTURAL INTEGRITY", p1, out1))

    # 2. Session Time Gate (<= cap min)
    p2, out2 = run_gate("Session Duration Gate", "estimate_session_time.py", file_path)
    scorecard.append((f"2. SESSION DURATION & TIME CAP (≤{cap_min:.0f} min)", p2, out2))

    # 3. Volume & Frequency Gate
    p3, out3 = run_gate("Volume & Frequency Eval", "eval_program_volume.py", file_path)
    scorecard.append(("3. CONFIGURED VOLUME & FREQUENCY", p3, out3))

    # 4. Concurrent Recovery & Interference Gate
    p4, out4 = run_gate("Recovery & Interference Eval", "eval_recovery_interference.py", file_path, extra_args=["--check", "spacing"])
    scorecard.append(("4. CONFIGURED SCHEDULING & CARDIO", p4, out4))

    # 5. Proximity to Failure & Submaximal Intensity (Polito 2021)
    p5, out5 = run_gate("Proximity to Failure Eval", "eval_recovery_interference.py", file_path, extra_args=["--check", "rpe"])
    scorecard.append(("5. CONFIGURED HEAVY-LIFT RPE CEILING", p5, out5))

    # 6. Evidence Grounding & Consensus Gate
    p6, out6 = run_gate("Evidence Grounding & Consensus Gate", "eval_evidence_grounding.py", file_path)
    scorecard.append(("6. CITATION RESOLUTION (not claim verification)", p6, out6))

    p7, out7 = run_gate("Cache Schema Integrity", "check_cache_schema.py")
    scorecard.append(("7. CACHE SCHEMA INTEGRITY (citation keys, years, ids)", p7, out7))

    p8, out8 = run_gate("Import Health", "check_import_health.py")
    scorecard.append(("8. IMPORT HEALTH (every module imports, every CLI builds)", p8, out8))

    p9, out9 = run_gate("Writing Standard", "check_writing_standard.py", file_path)
    scorecard.append(("9. WRITING STANDARD (ASD-STE100 rules + BLUF, if declared)", p9, out9))

    all_passed = True
    print()
    for gate_title, passed, out in scorecard:
        status = "[ PASS ]"
        if not passed:
            status = "[ FAIL ✗ ]"
        elif out.startswith("SKIP"):  # exited 0 but checked nothing: not a pass
            status = "[ SKIP ]"
        print(f"  {gate_title:58s} {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("  OVERALL STATUS: CONFIGURED CHECKS PASSED. Not proof of scientific validity or individual suitability.")
        print("=" * 80)
        return 0
    else:
        print("  OVERALL STATUS: QA FAILED. One or more configured checks failed.")
        print("=" * 80)
        for gate_title, passed, out in scorecard:
            if not passed:
                print(f"\n--- Diagnostic: {gate_title} ---")
                print(out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
