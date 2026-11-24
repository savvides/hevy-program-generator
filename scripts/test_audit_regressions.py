"""Regression cases from the September 2026 workout audit."""
from __future__ import annotations

import copy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import build_routines as br
import check_cache_schema
import fetch_workouts
import install_hooks
import qa_program
from program_loader import load_program, validate_program_schema
from suggest_program import generate_program_code
from track_deficit import calculate_targets, evaluate_progress
from eval_recovery_interference import check_cardio_distribution, check_recovery_spacing
from estimate_session_time import (
    exec_seconds, routine_seconds, main as session_time_main,
    WARMUP_SET, REST_OVERRUN, SETUP_COMPOUND, SETUP_OTHER,
)
from calibrate_session_time import as_routine
from render_program import render
from eval_program_volume import compute_volume, main as volume_main


class TestAuditRegressions(unittest.TestCase):
    def test_volume_reports_unknown_context_without_title_inference(self):
        prog = load_program("programs/starter_full_body_2x.py")
        prog["PROGRAM_METADATA"]["title"] = "Men 40+ Hypertrophy"
        for field in ("age_years", "sex", "primary_goal"):
            prog["PROGRAM_METADATA"].pop(field, None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            path.write_text("\n".join(f"{key} = {value!r}" for key, value in prog.items()))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(volume_main(["--program", str(path)]), 0)
        self.assertIn("Age (reported years): unknown", output.getvalue())
        self.assertIn("Sex (reported): unknown", output.getvalue())
        self.assertIn("Primary goal: unknown", output.getvalue())

    def test_volume_context_does_not_change_passing_or_failing_gates(self):
        prog = load_program("programs/starter_full_body_2x.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.py"
            for excessive, expected_rc in ((False, 0), (True, 1)):
                if excessive:
                    prog["ROUTINES"][0]["exercises"][0]["work_sets"] = 100
                expected_table = None
                for age, sex, goal in ((18, "female", "hypertrophy"), (90, "nonbinary", "aerobic support")):
                    with self.subTest(excessive=excessive, age=age, sex=sex):
                        prog["PROGRAM_METADATA"].update(age_years=age, sex=sex, primary_goal=goal)
                        path.write_text("\n".join(f"{key} = {value!r}" for key, value in prog.items()))
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            rc = volume_main(["--program", str(path)])
                        text = output.getvalue()
                        self.assertEqual(rc, expected_rc)
                        self.assertIn(f"Age (reported years): {age}", text)
                        self.assertIn(f"Sex (reported): {sex}", text)
                        self.assertIn(f"Primary goal: {goal}", text)
                        self.assertIn("not suitability validation", text)
                        self.assertIn("Hypertrophy", text)
                        self.assertIn("aerobic support", text)
                        table = text[text.index("  Floor:"):]
                        if expected_table is None:
                            expected_table = table
                        self.assertEqual(table, expected_table)

    def test_session_instructions_use_supported_exercise_notes(self):
        ex = {"name": "Bench", "work_sets": 1, "reps": "5", "notes": "Exercise cue."}
        routine = {"name": "Tuesday", "notes": "Progression and warmup guidance.", "exercises": [ex, ex]}
        exported = br.build_routine_payload(routine, {"Bench": 1})["routine"]
        self.assertNotIn("notes", exported)
        self.assertIn("Exercise cue.", exported["exercises"][0]["notes"])
        self.assertIn("Session instructions:\n" + routine["notes"], exported["exercises"][0]["notes"])
        self.assertNotIn(routine["notes"], exported["exercises"][1]["notes"])

    def test_compact_session_notes_are_self_contained_bluf(self):
        ex = {"name": "Bench", "work_sets": 3, "reps": "3-5", "rpe": 8, "notes": "Exercise cue."}
        routine = {"name": "Tuesday", "notes": "Progression and warmup guidance.", "exercises": [ex, ex]}
        exported = br.build_routine_payload(routine, {"Bench": 1}, compact=True)["routine"]
        self.assertNotIn("Session instructions:", exported["exercises"][0]["notes"])
        self.assertTrue(exported["exercises"][0]["notes"].startswith("BLUF:"))
        self.assertIn("Add load after 3 x 5 at RPE 8.", exported["exercises"][0]["notes"])
        self.assertIn("Exercise cue.", exported["exercises"][0]["notes"])

    def test_step_up_range_survives_export_with_side_instruction(self):
        ex = {"name": "Step Up", "work_sets": 3, "reps": "6-8 per side"}
        payload = br.build_routine_payload({"name": "Friday", "exercises": [ex]}, {"Step Up": 1})
        exercise = payload["routine"]["exercises"][0]
        self.assertEqual(exercise["sets"][0]["rep_range"], {"start": 6, "end": 8})
        self.assertIn("per side", exercise["notes"])

    def test_invalid_prescription_never_defaults_to_five(self):
        for reps in ("unknown", "8-6", "0", "30 seconds maybe"):
            with self.subTest(reps=reps), self.assertRaises(ValueError):
                br.parse_work_sets({"work_sets": 3, "reps": reps})

    def test_supported_reps_and_durations_remain_unchanged(self):
        self.assertEqual(br.parse_work_sets({"work_sets": 1, "reps": "3-5"}),
                         [{"reps_min": 3, "reps_max": 5, "reps": 3}])
        self.assertEqual(br.parse_work_sets({"work_sets": 1, "reps": "30-45s"}),
                         [{"duration_seconds": 45}])

    def test_one_day_weight_change_cannot_trigger_calorie_adjustment(self):
        result = evaluate_progress([("2026-09-19", 180.0), ("2026-09-20", 181.0)], 2050, .45)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertNotIn("Reduce intake", result["recommendation"])

    def test_infeasible_deficit_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_targets(weekly_loss_lb=10)

    def test_nonfinite_nutrition_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_targets(current_weight_lb=float("nan"))

    def test_reaching_bodyfat_goal_does_not_keep_default_deficit(self):
        for current_bf in (.15, .14):
            with self.subTest(current_bf=current_bf):
                targets = calculate_targets(current_bf=current_bf, target_bf=.15)
                self.assertEqual(targets["daily_deficit"], 0)
                self.assertEqual(targets["fat_to_lose_lb"], 0)
                self.assertEqual(targets["target_weight_lb"], targets["current_weight_lb"])

    def test_deficit_cli_reports_goal_reached_below_target(self):
        result = subprocess.run([sys.executable, "scripts/track_deficit.py", "--current-bf", ".14", "--target-bf", ".15"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("target body fat already reached", result.stdout)
        self.assertIn("Maintenance:", result.stdout)

    def test_bodyweight_request_cannot_fall_back_to_gym_equipment(self):
        with self.assertRaisesRegex(ValueError, "equipment"):
            generate_program_code(days=2, equipment="bodyweight", joint_profile="fai_safe", tier="returning")

    def test_missing_rpe_and_unknown_weekday_are_schema_errors(self):
        prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
        prog["ROUTINES"][1]["day_key"] = "Frday"
        prog["ROUTINES"][0]["exercises"][0].pop("rpe")
        errors = validate_program_schema(prog)
        self.assertTrue(any("day_key" in e for e in errors))
        self.assertTrue(any("rpe" in e for e in errors))

    def test_impossible_interval_duration_is_rejected(self):
        prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
        vo2_idx = next(i for i, c in enumerate(prog["CARDIO_SCHEDULE"]) if "vo2" in c["type"].lower())
        prog["CARDIO_SCHEDULE"][vo2_idx]["duration_minutes"] = 5
        self.assertTrue(any("interval" in e for e in validate_program_schema(prog)))

    def test_threshold_session_is_not_counted_as_easy(self):
        easy, _, errors = check_cardio_distribution([{"type": "Threshold", "duration_minutes": 60}])
        self.assertEqual(easy, 0)
        self.assertTrue(errors)

    def test_actual_clock_times_control_recovery_gap(self):
        routines = [{"name": "Friday", "day_key": "Friday", "start_time": "07:00",
                     "exercises": [{"name": "Deadlift", "compound": True}]}]
        cardio = [{"day": "Wednesday", "type": "VO2 Max 4x4", "start_time": "19:00"}]
        errors, _ = check_recovery_spacing(routines, cardio)
        self.assertTrue(any("36h" in e for e in errors))

    def test_partial_clock_times_do_not_assume_the_missing_session_is_midnight(self):
        routines = [{"name": "Friday", "day_key": "Friday",
                     "exercises": [{"name": "Deadlift", "compound": True}]}]
        cardio = [{"day": "Wednesday", "type": "VO2 Max 4x4", "start_time": "19:00"}]
        errors, logs = check_recovery_spacing(routines, cardio)
        self.assertEqual(errors, [])
        self.assertTrue(any("unverified" in line for line in logs))
        self.assertTrue(any("48h" in line for line in logs))

    def test_malformed_constraint_profile_returns_schema_errors(self):
        for fields in ({"joint_profile": {}, "tier": "intermediate"}, {"joint_profile": "standard"}, {"tier": "intermediate"}):
            with self.subTest(fields=fields):
                prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
                prog["PROGRAM_METADATA"]["constraints"] = {"equipment": ["all"], **fields}
                self.assertTrue(any("constraints" in error for error in validate_program_schema(prog)))

    def test_carry_export_is_per_side_and_timing_counts_both(self):
        ex = {"name": "Carry", "work_sets": 3, "reps": "30-45s per side", "compound": False}
        specs = br.parse_work_sets(ex)
        self.assertEqual(exec_seconds(ex, specs[0]), 90)
        payload = br.build_routine_payload({"exercises": [ex]}, {"Carry": 1})
        exported = payload["routine"]["exercises"][0]
        self.assertEqual(exported["sets"][0]["duration_seconds"], 45)
        self.assertIn("both sides", exported["notes"])

    def test_reps_affect_time_and_last_set_has_no_extra_rest(self):
        ex = {"name": "Curl", "compound": False, "work_sets": 2, "reps": "10", "rest_seconds": 60}
        self.assertEqual(routine_seconds({"exercises": [ex]}), SETUP_OTHER + 2 * (30 + REST_OVERRUN) + 60)
        self.assertEqual(exec_seconds(ex, {"reps": 20}), 60)
        self.assertEqual(exec_seconds(ex, {"reps": 10, "sides": 2}), 60)
        with_warmups = {**ex, "warmup_reps": [5, 5, 3]}
        self.assertEqual(routine_seconds({"exercises": [with_warmups]}) - routine_seconds({"exercises": [ex]}), 3 * WARMUP_SET)

    def test_schema_rejects_boolean_sets_nonfinite_rest_and_invalid_time(self):
        for field, value in (("work_sets", True), ("rest_seconds", float("inf")), ("rpe", float("nan"))):
            prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
            prog["ROUTINES"][0]["exercises"][0][field] = value
            self.assertTrue(validate_program_schema(prog), field)
        prog["ROUTINES"][0]["start_time"] = "25:00"
        self.assertTrue(any("start_time" in error for error in validate_program_schema(prog)))

    def test_cardio_citation_required(self):
        prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
        prog["CARDIO_SCHEDULE"][0].pop("evidence_citation")
        self.assertTrue(any("evidence_citation" in error for error in validate_program_schema(prog)))

    def test_calibration_uses_prescribed_role_rest_and_logged_supersets(self):
        planned = {"exercises": [{"name": "Bench", "compound": True, "rest_seconds": 120,
                                  "work_sets": 1, "reps": "5", "warmup_reps": [5, 5, 3]}]}
        logged = {"exercises": [{"exercise_template_id": "bench", "superset_id": 7,
                                 "sets": [{"type": "normal", "reps": 5}]}]}
        templates = [{"title": "Bench", "id": "bench"}]
        ex = as_routine(logged, planned, templates)["exercises"][0]
        self.assertTrue(ex["compound"])
        self.assertEqual(ex["rest_seconds"], 120)
        self.assertEqual(ex["superset"], 7)
        self.assertEqual(ex["warmup_reps"], [])
        logged["exercises"][0]["exercise_template_id"] = "other"
        with self.assertRaises(ValueError):
            as_routine(logged, planned, templates)

    def test_readable_plan_includes_all_sets_and_detects_drift(self):
        prog = load_program("programs/starter_full_body_2x.py")
        html = render(prog)
        total_sets = sum(e["work_sets"] for r in prog["ROUTINES"] for e in r["exercises"])
        self.assertIn(f"Total weekly working sets: {total_sets}", html)
        self.assertIn("Box Squat (Barbell)", html)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.html"
            cmd = [sys.executable, "scripts/render_program.py", "--program", "programs/starter_full_body_2x.py", "--output", str(path), "--check"]
            path.write_text("stale")
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 1)
            path.write_text(html)
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_reviewed_reference_identifiers_and_unproven_scores(self):
        cache = json.loads(br.REPO_ROOT.joinpath("data/consensus_cache.json").read_text())
        papers = {p["citation_key"]: p for p in cache["papers"].values()}
        self.assertEqual(papers["Milanović et al. 2015"]["doi"], "10.1007/s40279-015-0365-0")
        self.assertEqual(papers["Wyckelsma et al. 2025"]["doi"], "10.1113/jp288638")
        self.assertEqual(papers["Currier et al. 2026"]["consensus_meter"], {})

    def test_readable_plan_accepts_legacy_cardio_duration(self):
        prog = load_program("programs/starter_full_body_2x.py")
        expected = render(prog)
        for cardio in prog["CARDIO_SCHEDULE"]:
            cardio["duration_min"] = cardio.pop("duration_minutes")
        self.assertEqual(validate_program_schema(prog), [])
        self.assertEqual(render(prog), expected)

    def test_dry_run_previews_payloads_without_api_writes(self):
        templates = json.loads(br.CACHE_PATH.read_text())
        output = io.StringIO()
        with patch.object(br, "fetch_templates", return_value=templates), \
             patch.object(br, "find_folder", return_value="folder"), \
             patch.object(br, "fetch_routines", return_value=[]), \
             patch.object(br, "http_request", side_effect=AssertionError("Unexpected API call")), \
             contextlib.redirect_stdout(output):
            rc = br.main(["--program", "programs/starter_full_body_2x.py", "--dry-run", "--skip-qa"])
        self.assertEqual(rc, 0)
        self.assertIn('"rep_range"', output.getvalue())
        self.assertIn("no API writes", output.getvalue())


REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_program(path: Path, prog: dict) -> Path:
    path.write_text("\n".join(f"{k} = {v!r}" for k, v in prog.items() if k != "_file_path"))
    return path


class TestQaGateFailurePaths(unittest.TestCase):
    """A gate that cannot fail is not a gate: each failure path must be exercised."""

    def _qa(self, program):
        return subprocess.run(
            [sys.executable, "scripts/qa_program.py", "--program", str(program)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def _gate9_line(self, result):
        return next(ln for ln in result.stdout.splitlines() if ln.lstrip().startswith("9. WRITING"))

    def test_valid_programs_exit_zero_and_a_skipped_gate_is_not_shown_as_pass(self):
        starter = self._qa(REPO_ROOT / "programs/starter_full_body_2x.py")
        self.assertEqual(starter.returncode, 0, starter.stdout)
        self.assertIn("[ SKIP ]", self._gate9_line(starter))  # does not declare the writing standard
        three_day = self._qa(REPO_ROOT / "programs/three_day_split_3x.py")
        self.assertEqual(three_day.returncode, 0, three_day.stdout)
        upper_lower = self._qa(REPO_ROOT / "programs/upper_lower_4x.py")
        self.assertEqual(upper_lower.returncode, 0, upper_lower.stdout)

    def test_program_that_loads_but_fails_a_gate_exits_nonzero(self):
        prog = load_program("programs/starter_full_body_2x.py")
        prog["ROUTINES"][1]["name"] = prog["ROUTINES"][0]["name"]  # two routines, one name
        with tempfile.TemporaryDirectory() as directory:
            result = self._qa(_write_program(Path(directory) / "dup.py", prog))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OVERALL STATUS: QA FAILED", result.stdout)
        self.assertIn("[ FAIL", result.stdout)

    def test_program_without_cardio_schedule_is_rejected_not_read_as_no_cardio(self):
        prog = load_program("programs/starter_full_body_2x.py")
        del prog["CARDIO_SCHEDULE"]
        with tempfile.TemporaryDirectory() as directory:
            result = self._qa(_write_program(Path(directory) / "no_cardio.py", prog))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing root key: 'CARDIO_SCHEDULE'", result.stderr)

    def test_run_gate_reports_failure_for_a_script_that_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "gate_fail.py").write_text(
                "import sys\nprint('out')\nprint('boom', file=sys.stderr)\nsys.exit(1)\n")
            (Path(directory) / "gate_ok.py").write_text("print('fine')\n")
            with patch.object(qa_program, "SCRIPTS_DIR", Path(directory)):
                passed, output = qa_program.run_gate("failing", "gate_fail.py")
                self.assertFalse(passed)
                self.assertIn("boom", output)
                self.assertEqual(qa_program.run_gate("passing", "gate_ok.py"), (True, "fine"))


class TestEvaluatorGateFailurePaths(unittest.TestCase):
    """The volume and session-time gates must fail on a bad program and pin their arithmetic."""

    def _bench_only_program(self, directory, name="program.py", cap=60):
        prog = copy.deepcopy(load_program("programs/starter_full_body_2x.py"))
        routine = prog["ROUTINES"][0]
        bench = next(ex for ex in routine["exercises"] if ex["name"] == "Bench Press (Barbell)")
        prog["ROUTINES"] = [{**routine, "exercises": [{**bench, "work_sets": 3}]}]
        prog["PROGRAM_METADATA"]["session_time_cap_minutes"] = cap
        return _write_program(Path(directory) / name, prog)

    def _run(self, main, path):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = main(["--program", str(path)])
        return rc, output.getvalue()

    def test_weighted_volume_counts_secondary_muscles_at_half(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._bench_only_program(directory)
            # Bench Press: chest primary, triceps and shoulders secondary in the cached catalog.
            self.assertEqual(compute_volume(str(path)), {"chest": 3.0, "triceps": 1.5, "shoulders": 1.5})

    def test_volume_gate_fails_for_prime_movers_below_the_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            rc, text = self._run(volume_main, self._bench_only_program(directory))
        self.assertEqual(rc, 1)
        # The frequency gate also returns 1 here, so assert the floor message itself.
        floor_line = next((ln for ln in text.splitlines() if "below configured floor" in ln), "")
        self.assertIn("quadriceps", floor_line)
        self.assertIn("triceps", floor_line)  # 1.5 weighted sets
        self.assertNotIn("chest", floor_line)  # exactly 3.0, at the floor

    def test_session_time_gate_fails_over_the_cap_and_passes_under_it(self):
        with tempfile.TemporaryDirectory() as directory:
            rc, text = self._run(session_time_main, self._bench_only_program(directory, "tiny_cap.py", cap=1))
            self.assertEqual(rc, 1)
            self.assertIn("OVER", text)
            self.assertIn("FAIL: sessions over 1 min", text)
            rc, text = self._run(session_time_main, self._bench_only_program(directory, "roomy_cap.py", cap=600))
            self.assertEqual(rc, 0)
            self.assertIn("PASS", text)

    def test_compound_execution_has_a_45_second_floor(self):
        compound = {"compound": True, "work_sets": 1, "reps": "5", "rest_seconds": 60}
        self.assertEqual(exec_seconds(compound, {"reps": 5}), 45)  # 5 reps x 3 s = 15 s, raised to the floor
        self.assertEqual(exec_seconds(compound, {"reps": 20}), 60)  # above the floor, unchanged
        self.assertEqual(exec_seconds({**compound, "compound": False}, {"reps": 5}), 15)  # isolation has no floor
        self.assertEqual(routine_seconds({"exercises": [compound]}), SETUP_COMPOUND + 45 + REST_OVERRUN)


class TestCacheSchemaGate(unittest.TestCase):
    def test_gate_passes_on_the_real_cache_tests(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_cache_schema.main(), 0)

    def test_gate_fails_when_no_tests_ran(self):
        """A renamed or missing test file must not pass the gate vacuously."""
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(check_cache_schema, "SCRIPTS_DIR", Path(directory)), \
                patch.object(sys, "path", list(sys.path)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_cache_schema.main(), 1)


class TestInstallHooks(unittest.TestCase):
    """Run the installer against throwaway repositories, never this one."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name).resolve()
        # No GIT_DIR/GIT_INDEX_FILE from an enclosing hook, no global core.hooksPath.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                              text=True).stdout.strip()

    def _repo(self, name="repo"):
        repo = self.tmp / name
        repo.mkdir()
        self._git(repo, "init", "-q")
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com"),
                           ("commit.gpgsign", "false")):
            self._git(repo, "config", key, value)
        self._git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        return repo

    def _hooks_dir_git_reads(self, repo):
        path = Path(self._git(repo, "rev-parse", "--git-path", "hooks"))
        return (path if path.is_absolute() else repo / path).resolve()

    def test_plain_repo_gets_an_executable_hook(self):
        repo = self._repo()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.install_hooks(repo), 0)
            self.assertEqual(install_hooks.install_hooks(repo), 0)  # re-install over its own hook
        hook = repo / ".git" / "hooks" / "pre-commit"
        self.assertEqual(hook.read_text(), install_hooks.HOOK_CONTENT)
        self.assertTrue(os.access(hook, os.X_OK))

    def test_linked_worktree_installs_where_git_reads_hooks(self):
        main = self._repo("main")
        linked = self.tmp / "linked"
        self._git(main, "worktree", "add", "-q", str(linked))
        self.assertTrue((linked / ".git").is_file())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.install_hooks(linked), 0)
        hook = self._hooks_dir_git_reads(linked) / "pre-commit"
        self.assertEqual(hook.read_text(), install_hooks.HOOK_CONTENT)
        self.assertEqual(hook, (main / ".git" / "hooks" / "pre-commit").resolve())

    def test_core_hooks_path_is_honoured(self):
        for index, configured in enumerate(("custom-hooks", str(self.tmp / "absolute-hooks"))):
            with self.subTest(core_hooksPath=configured):
                repo = self._repo(f"repo{index}")
                self._git(repo, "config", "core.hooksPath", configured)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(install_hooks.install_hooks(repo), 0)
                hook = self._hooks_dir_git_reads(repo) / "pre-commit"
                self.assertEqual(hook.read_text(), install_hooks.HOOK_CONTENT)
                self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())

    def test_foreign_hook_is_not_overwritten(self):
        repo = self._repo()
        hook = repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho my own hook\n")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.install_hooks(repo), 1)
        self.assertEqual(hook.read_text(), "#!/bin/sh\necho my own hook\n")
        self.assertIn("pre-commit", stderr.getvalue())
        self.assertIn("merge", stderr.getvalue().lower())


FAKE_KEY = "fake-hevy-key-for-tests-0000"
ACTIVE_PROGRAM = "programs/starter_full_body_2x.py"


class _FakeHevy:
    """In-memory stand-in for the Hevy API, passed in as build_routines.http_request."""

    PAGE_SIZE = 2  # small, so the sync must paginate

    def __init__(self):
        self.folders = [{"id": 1, "title": "Someone Else's Folder"}]
        # More than one page of unrelated routines in another folder. They share weekday keys
        # with the program, so the folder filter matters too.
        self.routines = [{"id": f"old{i}", "title": f"Tuesday — unrelated {i}", "folder_id": 1}
                         for i in range(5)]
        self.calls = []
        self.next_id = 100
        self.read_error = None      # raised by every GET
        self.folder_error = None    # raised by the folder POST
        self.write_error = None     # raised by routine write number write_error_on
        self.write_error_on = 2
        self.routine_writes = 0

    def writes(self, method=None):
        return [c for c in self.calls if c[0] in ((method,) if method else ("POST", "PUT"))]

    def _page(self, key, items, query):
        page = int(query["page"][0])
        size = self.PAGE_SIZE
        return {"page": page, "page_count": max(1, -(-len(items) // size)),
                key: copy.deepcopy(items[(page - 1) * size:page * size])}

    def __call__(self, api_key, method, path, body=None):
        assert api_key == FAKE_KEY, "the sync must use only the key the test supplied"
        self.calls.append((method, path, copy.deepcopy(body)))
        url = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qs(url.query)
        if method == "GET":
            if self.read_error is not None:
                raise self.read_error
            if url.path == "/routines":
                return self._page("routines", self.routines, query)
            if url.path == "/routine_folders":
                return self._page("routine_folders", self.folders, query)
        elif (method, url.path) == ("POST", "/routine_folders"):
            if self.folder_error is not None:
                raise self.folder_error
            folder = {"id": self._new_id(), **body["routine_folder"]}
            self.folders.append(folder)
            return {"routine_folder": folder}
        elif url.path.startswith("/routines"):
            if method == "POST" and url.path == "/routines":
                routine = {"id": f"r{self._new_id()}", **copy.deepcopy(body["routine"])}
                self.routines.append(routine)
            else:
                assert method == "PUT", (method, path)
                routine = next(r for r in self.routines if r["id"] == url.path.rsplit("/", 1)[1])
                routine.update(copy.deepcopy(body["routine"]))
            self.routine_writes += 1
            # The worst case: Hevy applied the write, but the response never arrived.
            if self.write_error is not None and self.routine_writes == self.write_error_on:
                raise self.write_error
            return {"routine": [routine]}
        raise AssertionError(f"unexpected Hevy call: {method} {path}")

    def _new_id(self):
        self.next_id += 1
        return self.next_id


class TestHevySyncEndToEnd(unittest.TestCase):
    """Runs build_routines.main() against _FakeHevy. Nothing here can reach the real API,
    the real key, or the tracked exercise cache."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.cache = self.root / "data" / "exercise_templates.json"
        self.cache.parent.mkdir()
        self.cache.write_bytes(br.CACHE_PATH.read_bytes())
        self.fake = _FakeHevy()
        self.n_routines = len(load_program(ACTIVE_PROGRAM)["ROUTINES"])

    def _sync(self, *extra, key=FAKE_KEY, program=ACTIVE_PROGRAM):
        env = {k: v for k, v in os.environ.items() if k != "HEVY_API_KEY"}
        if key:
            env["HEVY_API_KEY"] = key
        out = io.StringIO()
        with patch.object(br, "http_request", side_effect=self.fake), \
             patch("urllib.request.urlopen", side_effect=AssertionError("live network call")), \
             patch.object(br, "load_dotenv"), \
             patch.dict(os.environ, env, clear=True), \
             patch.object(br, "REPO_ROOT", self.root), \
             patch.object(br, "CACHE_PATH", self.cache), \
             patch.object(br.time, "sleep"), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = br.main(["--program", str(program), "--skip-qa", *extra])
        self.assertNotIn(FAKE_KEY, out.getvalue())
        return rc, out.getvalue()

    def _program_routines(self):
        return [r for r in self.fake.routines if r["folder_id"] != 1]

    def test_first_sync_creates_and_second_sync_updates_in_place(self):
        rc, _ = self._sync("--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake.writes(), [])

        rc, _ = self._sync()
        self.assertEqual(rc, 0)
        posts = self.fake.writes("POST")
        self.assertEqual([c[1] for c in posts], ["/routine_folders"] + ["/routines"] * self.n_routines)
        self.assertEqual(self.fake.writes("PUT"), [])
        folder_id = self.fake.folders[-1]["id"]
        for _, _, body in posts[1:]:
            self.assertEqual(body["routine"]["folder_id"], str(folder_id))
        created = [r["id"] for r in self._program_routines()]
        counts = (len(self.fake.folders), len(self.fake.routines))
        self.assertEqual(counts, (2, 5 + self.n_routines))

        self.fake.calls.clear()
        rc, text = self._sync("--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake.writes(), [])
        self.assertNotIn("NOT checked", text)
        self.assertEqual(text.count("UPDATE"), self.n_routines)

        rc, _ = self._sync()
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake.writes("POST"), [])
        puts = self.fake.writes("PUT")
        self.assertEqual([c[1] for c in puts], [f"/routines/{rid}" for rid in created])
        for _, _, body in puts:
            self.assertNotIn("folder_id", body["routine"])
        self.assertEqual((len(self.fake.folders), len(self.fake.routines)), counts)

    def test_two_routines_with_one_key_abort_before_any_write(self):
        prog = load_program(ACTIVE_PROGRAM)
        prog["ROUTINES"][0]["name"] = "Tuesday — AM Upper"
        prog["ROUTINES"][1].update(name="Tuesday — PM Lower", day_key="Tuesday")
        program = _write_program(self.root / "two_tuesdays.py", prog)
        for extra, key in (((), FAKE_KEY), (("--dry-run",), FAKE_KEY), (("--dry-run",), None)):
            with self.subTest(extra=extra, key=bool(key)):
                rc, text = self._sync(*extra, key=key, program=program)
                self.assertNotEqual(rc, 0)
                self.assertIn("Tuesday — AM Upper", text)
                self.assertIn("Tuesday — PM Lower", text)
                self.assertNotIn("Reconcile plan", text)
        self.assertEqual(self.fake.writes(), [])

    def test_dry_run_never_refetches_or_rewrites_a_stale_cache(self):
        os.utime(self.cache, (0, 0))  # far older than the 30-day limit
        before = self.cache.read_bytes()
        rc, _ = self._sync("--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual([c for c in self.fake.calls if "exercise_templates" in c[1]], [])
        self.assertEqual(self.cache.read_bytes(), before)
        self.assertEqual(self.cache.stat().st_mtime, 0)

    def test_dry_run_says_when_the_plan_was_not_checked_against_hevy(self):
        rejected = urllib.error.HTTPError("https://example.invalid", 401, "Unauthorized", None, None)
        for label, key, error, wanted, unwanted in (
            ("no key", None, None, "NOT checked", "unreachable"),
            ("key rejected", FAKE_KEY, rejected, "rejected", "unreachable"),
            ("network down", FAKE_KEY, urllib.error.URLError("no route to host"), "unreachable", "rejected"),
        ):
            with self.subTest(label):
                self.fake.read_error = error
                rc, text = self._sync("--dry-run", key=key)
                self.assertEqual(rc, 0)
                self.assertIn("NOT checked", text)
                self.assertIn(wanted, text)
                self.assertNotIn(unwanted, text)
                self.assertNotIn("WILL BE CREATED", text)
                self.assertNotIn("CREATE ", text)
        self.assertEqual(self.fake.writes(), [])

    def test_failure_in_the_middle_of_a_sync_is_a_clean_error_and_a_rerun_converges(self):
        for error in (urllib.error.URLError("connection reset"), TimeoutError("timed out"),
                      json.JSONDecodeError("Expecting value", "<html>", 0)):
            with self.subTest(error=type(error).__name__):
                self.fake = _FakeHevy()
                self.fake.write_error = error
                rc, text = self._sync()  # must return, not raise
                self.assertNotEqual(rc, 0)
                self.assertIn("re-run", text)
                self.assertEqual(self.fake.routine_writes, 2)  # stopped at the failure

                self.fake.write_error = None
                rc, _ = self._sync()
                self.assertEqual(rc, 0)
                titles = [r["title"] for r in self._program_routines()]
                self.assertEqual(len(titles), self.n_routines)
                self.assertEqual(len(set(titles)), self.n_routines)
                self.assertEqual(len(self.fake.folders), 2)

    def test_folder_create_failure_is_a_clean_error(self):
        self.fake.folder_error = TimeoutError("timed out")
        rc, text = self._sync()  # must return, not raise
        self.assertNotEqual(rc, 0)
        self.assertIn("re-run", text)
        self.assertEqual(len(self.fake.writes()), 1)  # the folder POST only; no routine written


class TestFetchWorkoutsFailure(unittest.TestCase):
    def test_network_failure_on_page_two_is_a_clean_error(self):
        def fetch_page(api_key, page):
            assert api_key == FAKE_KEY
            if page == 2:
                raise urllib.error.URLError("connection reset")
            return {"page_count": 3, "workouts": [{"id": "w1"}]}

        env = {k: v for k, v in os.environ.items() if k not in ("HEVY_API_KEY", "HEVY_DATA_DIR")}
        env["HEVY_API_KEY"] = FAKE_KEY
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(fetch_workouts, "fetch_page", side_effect=fetch_page), \
                patch("urllib.request.urlopen", side_effect=AssertionError("live network call")), \
                patch.object(fetch_workouts, "load_dotenv"), \
                patch.dict(os.environ, env, clear=True), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = fetch_workouts.main(["--data-dir", directory])  # must return, not raise
            written = sorted(f.name for f in Path(directory).iterdir())
        self.assertNotEqual(rc, 0)
        self.assertEqual(written, ["w1.json"])
        self.assertIn("re-run", out.getvalue())
        self.assertNotIn(FAKE_KEY, out.getvalue())


if __name__ == "__main__":
    unittest.main()
