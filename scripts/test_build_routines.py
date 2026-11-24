#!/usr/bin/env python3
"""Unit tests for build_routines.py — reconcile helpers, payload/superset
emission, and program integrity. Stdlib only.

Covers: (1) idempotent reconcile — a routine is matched by its *weekday* (so a
descriptive-title change updates in place) or, for non-weekday routines, by normalized title;
(2) superset_id emission — paired exercises share a group id, solo exercises emit None;
(3) a regression guard that every program exercise still resolves against the cached Hevy catalog before a live build.

Run: python3 scripts/test_build_routines.py [--program <path>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_routines as br  # noqa: E402
from program_loader import load_program  # noqa: E402

# Parse optional --program from CLI args
def _parse_program_path() -> Optional[str]:
    for i, arg in enumerate(sys.argv[:-1]):
        if arg == "--program":
            return sys.argv[i + 1]
    return None

PROGRAM_PATH = _parse_program_path()
ACTIVE_PROG = load_program(PROGRAM_PATH)
METADATA = ACTIVE_PROG.get("PROGRAM_METADATA", {})
ROUTINES = ACTIVE_PROG.get("ROUTINES", [])


def _fake_resolved(routine: dict) -> dict[str, str]:
    """Dummy name→id map so build_routine_payload can run without the catalog."""
    return {ex["name"]: f"id_{i}" for i, ex in enumerate(routine["exercises"])}


def _lift_routines() -> list[dict]:
    return ROUTINES


def test_day_key_variants():
    assert br.day_key("Tue — Lower (Machine-Based, Spine Deload Version)") == "tue"
    assert br.day_key("Tue — Lower (Hinge, Back-Friendly)") == "tue"
    assert br.day_key("Mon — Upper-A (Push Focus)") == "mon"
    assert br.day_key("Fri — Lower Unilateral + Calves") == "fri"
    assert br.day_key("Thursday Upper") == "thu"
    assert br.day_key("v3.0 — Session B (Lower)") is None
    assert br.day_key("") is None
    assert br.day_key("   ") is None


def test_plan_reconcile_matches_by_day_despite_title_drift():
    desired = [
        {"title": "Mon — Upper-A (Push Focus)"},
        {"title": "Tue — Lower (Machine-Based, Spine Deload Version)"},
        {"title": "Thu — Upper-B (Pull Focus)"},
        {"title": "Fri — Lower Unilateral + Calves"},
    ]
    existing = [
        {"id": "m1", "title": "Mon — Upper-A (Push Focus)"},
        {"id": "t1", "title": "Tue — Lower (Hinge, Back-Friendly)"},  # title drifted
        {"id": "h1", "title": "Thu — Upper-B (Pull Focus)"},
        {"id": "f1", "title": "Fri — Lower Unilateral + Calves"},
    ]
    actions, extras = br.plan_reconcile(desired, existing)
    by_title = {a["routine"]["title"]: a for a in actions}
    tue = by_title["Tue — Lower (Machine-Based, Spine Deload Version)"]
    assert tue["action"] == "update", "drifted Tuesday must update, not create"
    assert tue["routine_id"] == "t1"
    assert all(a["action"] == "update" for a in actions)
    assert extras == []


def test_plan_reconcile_creates_when_folder_empty():
    desired = [{"title": "Tue — Lower (X)"}]
    actions, extras = br.plan_reconcile(desired, [])
    assert len(actions) == 1
    assert actions[0]["action"] == "create"
    assert actions[0]["routine_id"] is None
    assert extras == []


def test_plan_reconcile_flags_stale_day_as_extra():
    desired = [{"title": "Mon — Upper"}]
    existing = [
        {"id": "m1", "title": "Mon — Upper"},
        {"id": "x1", "title": "Sat — Old Conditioning"},  # weekday not in desired
    ]
    actions, extras = br.plan_reconcile(desired, existing)
    assert [a["action"] for a in actions] == ["update"]
    assert len(extras) == 1 and extras[0]["id"] == "x1"


def test_plan_reconcile_flags_duplicate_day_as_extra():
    # Two Mondays in the folder: first updates, the duplicate is flagged for deletion.
    desired = [{"title": "Mon — Upper"}]
    existing = [
        {"id": "m1", "title": "Mon — Upper"},
        {"id": "m2", "title": "Mon — Upper (dupe)"},
    ]
    actions, extras = br.plan_reconcile(desired, existing)
    assert [a["action"] for a in actions] == ["update"]
    assert actions[0]["routine_id"] == "m1"  # first wins
    assert len(extras) == 1 and extras[0]["id"] == "m2"


def test_plan_reconcile_rejects_two_desired_routines_with_one_key():
    # Both would match the same existing routine: the second PUT would overwrite the first.
    desired = [{"title": "Tuesday — AM Upper"}, {"title": "Tuesday — PM Lower"}]
    for existing in ([], [{"id": "t1", "title": "Tue — Upper"}]):
        try:
            br.plan_reconcile(desired, existing)
        except ValueError as e:
            assert "Tuesday — AM Upper" in str(e) and "Tuesday — PM Lower" in str(e), str(e)
        else:
            raise AssertionError("two desired routines sharing a routine_key must be rejected")


def test_routine_key_falls_back_to_normalized_title():
    assert br.routine_key("Tue — Lower (X)") == "tue"
    daily = br.routine_key("Daily — Core (anti-movement)")
    assert daily == br.normalize("Daily — Core (anti-movement)")
    assert daily not in br.WEEKDAYS.values()  # never collides with a weekday key


def test_plan_reconcile_non_weekday_matches_by_title():
    # A non-weekday routine has day_key None; without the title fallback every
    # sync would create a duplicate instead of updating it.
    desired = [{"title": "Daily — Core (anti-movement)"}]
    actions, _ = br.plan_reconcile(desired, [])
    assert actions[0]["action"] == "create"  # first run: folder empty

    existing = [{"id": "core1", "title": "Daily — Core (anti-movement)"}]
    actions, extras = br.plan_reconcile(desired, existing)
    assert actions[0]["action"] == "update"  # second run: update, not duplicate
    assert actions[0]["routine_id"] == "core1"
    assert extras == []


def test_plan_reconcile_mixed_weekday_and_daily():
    desired = [
        {"title": "Tue — Lower (Machine-Based, Spine Deload Version)"},
        {"title": "Daily — Core (anti-movement)"},
    ]
    existing = [
        {"id": "t1", "title": "Tue — Lower (Hinge, Back-Friendly)"},  # weekday drift
        {"id": "c1", "title": "Daily — Core (anti-movement)"},        # non-weekday
    ]
    actions, extras = br.plan_reconcile(desired, existing)
    by_title = {a["routine"]["title"]: a for a in actions}
    assert by_title["Tue — Lower (Machine-Based, Spine Deload Version)"]["routine_id"] == "t1"
    assert by_title["Daily — Core (anti-movement)"]["routine_id"] == "c1"
    assert all(a["action"] == "update" for a in actions)
    assert extras == []


def test_fullbody_routines_reconcile_by_title():
    desired = [{"title": r.get("title") or r.get("name", "")} for r in ROUTINES]
    actions, extras = br.plan_reconcile(desired, [])
    assert [a["action"] for a in actions] == ["create"] * len(desired)
    assert extras == []

    existing = [{"id": f"r{i}", "title": r.get("title") or r.get("name", "")}
                for i, r in enumerate(ROUTINES)]
    actions, extras = br.plan_reconcile(desired, existing)
    assert all(a["action"] == "update" for a in actions), \
        "second sync of identical titles must update, not duplicate"
    assert extras == []


def test_program_structure():
    lifts = _lift_routines()
    assert len(lifts) >= 1, "expected at least 1 lift routine"
    for r in lifts:
        r_title = r.get("title") or r.get("name", "Routine")
        n = len(r["exercises"])
        assert n >= 2, f"{r_title} should have ≥2 exercises, has {n}"
        compounds = [ex for ex in r["exercises"] if ex.get("compound")]
        assert len(compounds) >= 1, f"{r_title} needs ≥1 compound, has {len(compounds)}"


def test_compounds_are_solo_straight_sets_with_flat_warmup():
    # Compounds are done straight (never in a superset) and carry a formal warmup ramp.
    for r in _lift_routines():
        for ex in r["exercises"]:
            if ex.get("compound"):
                assert ex.get("superset") is None, \
                    f"{ex['name']} is a compound but sits in a superset"
                wu = ex.get("warmup_reps")
                assert wu is not None and len(wu) >= 2, \
                    f"{ex['name']} is a compound and must carry a warm-up ramp"


def test_isolations_have_no_warmups():
    for r in _lift_routines():
        for ex in r["exercises"]:
            if not ex.get("compound"):
                assert ex.get("warmup_reps") in (None, []), \
                    f"{ex['name']} is isolation and must carry no warm-up sets"


def test_exercise_notes_are_concise():
    CAP = 140
    over = []
    for r in ROUTINES:
        r_title = r.get("title") or r.get("name", "")
        for ex in r["exercises"]:
            notes = ex.get("notes") or ""
            n = len(notes)
            if n > CAP:
                over.append(f"{r_title} / {ex['name']}: {n} chars (cap {CAP})")
    assert not over, "exercise notes over the concise cap:\n" + "\n".join(over)


def test_no_superset_contains_a_compound():
    # Supersets only pair isolation work, and each superset has ≥2 members.
    for r in _lift_routines():
        r_title = r.get("title") or r.get("name", "")
        groups: dict[int, list[dict]] = {}
        for ex in r["exercises"]:
            sid = ex.get("superset")
            if sid is not None:
                groups.setdefault(sid, []).append(ex)
        for sid, members in groups.items():
            assert len(members) >= 2, f"{r_title} superset {sid} has a lone member"
            assert all(not m.get("compound") for m in members), \
                f"{r_title} superset {sid} contains a compound"


def test_sessions_under_time_cap():
    import estimate_session_time as est
    cap_min = float(METADATA.get("session_time_cap_minutes", est.CAP_MIN))
    for r in _lift_routines():
        r_title = r.get("title") or r.get("name", "")
        secs = est.routine_seconds(r)
        assert secs <= cap_min * 60, \
            f"{r_title} is {secs / 60:.1f} min, over the {cap_min:.0f}-min cap"


def test_time_no_internal_rest_in_trailing_superset_round():
    import estimate_session_time as est
    routine = {"title": "T", "exercises": [
        {"name": "X", "compound": False, "superset": 9, "rest_seconds": 60,
         "warmup_reps": [], "work_sets": [{"reps": 10}] * 2},
        {"name": "Y", "compound": False, "superset": 9, "rest_seconds": 60,
         "warmup_reps": [], "work_sets": [{"reps": 10}] * 3},
    ]}
    iso, setup, ss, rest = (30, est.SETUP_OTHER,
                            est.SUPERSET_INTERNAL_REST, 60)
    over = est.REST_OVERRUN
    expected = (2 * setup
                + 2 * (2 * iso + ss + rest + over)
                + (iso + over))
    assert est.routine_seconds(routine) == expected, est.routine_seconds(routine)


def test_group_exercises_is_consecutive_and_order_preserving():
    import estimate_session_time as est

    def ex(name, sid):
        return {"name": name, "compound": False, "superset": sid,
                "rest_seconds": 60, "warmup_reps": [], "work_sets": [{"reps": 8}]}

    def names(routine):
        return [[e["name"] for e in g] for g in est._group_exercises(routine)]

    assert names({"exercises": [ex("a", 0), ex("b", 0), ex("s", None),
                                ex("c", 1), ex("d", 1)]}) == [["a", "b"], ["s"], ["c", "d"]]
    assert names({"exercises": [ex("a", 5), ex("s", None), ex("b", 5)]}) == \
        [["a"], ["s"], ["b"]]
    assert names({"exercises": [ex("s1", None), ex("s2", None)]}) == [["s1"], ["s2"]]


def test_prescribed_rest_survives_export():
    for routine in ROUTINES:
        built = br.build_routine_payload(routine, _fake_resolved(routine))
        for prescribed, exported in zip(routine["exercises"], built["routine"]["exercises"]):
            assert exported["rest_seconds"] == prescribed["rest_seconds"]
    # Longer recovery is allowed; timing must account for it rather than clamp it.
    routine = {"exercises": [{"name": "Bench", "work_sets": 3, "reps": "5", "rest_seconds": 180}]}
    assert br.build_routine_payload(routine, {"Bench": 1})["routine"]["exercises"][0]["rest_seconds"] == 180


def test_superset_id_emitted_and_grouped():
    for routine in ROUTINES:
        built = br.build_routine_payload(routine, _fake_resolved(routine))
        for spec, ex in zip(routine["exercises"], built["routine"]["exercises"]):
            assert ex["superset_id"] == spec.get("superset")


def test_payload_warmup_then_work_sets():
    routine = ROUTINES[0]
    payload = br.build_routine_payload(routine, _fake_resolved(routine))
    comp_ex = next((ex for ex in routine["exercises"] if ex.get("compound") and ex.get("warmup_reps")), None)
    if comp_ex:
        comp_i = routine["exercises"].index(comp_ex)
        ex_payload = payload["routine"]["exercises"][comp_i]
        types = [s["type"] for s in ex_payload["sets"]]
        n_wu = len(comp_ex["warmup_reps"])
        assert types[:n_wu] == ["warmup"] * n_wu
        assert all(t == "normal" for t in types[n_wu:])
        assert [s["reps"] for s in ex_payload["sets"][:n_wu]] == comp_ex["warmup_reps"]


def test_all_program_exercises_resolve():
    templates = json.loads(br.CACHE_PATH.read_text())
    unresolved = [ex["name"] for r in ROUTINES for ex in r["exercises"]
                  if br.find_template(templates, ex["name"]) is None]
    assert not unresolved, f"unresolved exercise names: {unresolved}"


def test_find_template_exact_match_is_order_independent():
    builtin = {"id": "7757171F", "is_custom": False, "title": "Sled Push"}
    custom = {"id": "6e609374-ffb6-4ea0-ac49-b5679d9cff59", "is_custom": True,
              "title": "Sled Push"}
    for templates in ([builtin, custom], [custom, builtin]):
        result = br.find_template(templates, "Sled Push")
        assert result is builtin, \
            f"expected the built-in template regardless of list order, got {result}"


def test_find_template_fuzzy_tie_is_order_independent():
    # Equal top scores (0.75 each): same tie-break as the exact branch, not list order.
    dumbbell = {"id": "B5D3A742", "is_custom": False, "title": "Bulgarian Split Squat (Dumbbell)"}
    barbell = {"id": "0F24286A", "is_custom": False, "title": "Bulgarian Split Squat (Barbell)"}
    custom = {"id": "00000000-custom", "is_custom": True, "title": "Bulgarian Split Squat (Kettlebell)"}
    for templates in ([dumbbell, barbell, custom], [custom, barbell, dumbbell], [barbell, custom, dumbbell]):
        result = br.find_template(templates, "Bulgarian Split Squat")
        assert result is barbell, \
            f"expected built-in, lowest id regardless of list order, got {result}"
    assert br.find_template([dumbbell, barbell], "Leg Press") is None  # below the 0.55 floor


def test_every_prime_mover_meets_volume_and_frequency():
    import eval_program_volume as ev
    vol = ev.compute_volume(PROGRAM_PATH)
    freq = ev.compute_frequency(PROGRAM_PATH)
    low_vol = [m for m in ev.GATED if vol.get(m, 0) < ev.MIN_SETS]
    low_freq = [m for m in ev.GATED if freq.get(m, 0) < ev.MIN_FREQ]
    assert not low_vol, f"under {ev.MIN_SETS:.0f} sets/week: {low_vol}"
    assert not low_freq, f"trained < {ev.MIN_FREQ}×/week: {low_freq}"


def test_friday_vo2_and_sunday_strength_schedule():
    """Verify schedule conforms to Friday VO2 Max and Sunday Strength architecture."""
    prog = load_program(PROGRAM_PATH)
    if "starter_full_body_2x" not in prog.get("_file_path", "") and prog.get("PROGRAM_METADATA", {}).get("title", "") != "Full-Body 2x — Strength + Polarized Cardio":
        return
    routines = prog["ROUTINES"]
    cardio = prog["CARDIO_SCHEDULE"]

    day_keys = [r.get("day_key") for r in routines]
    assert "Sunday" in day_keys, f"Sunday missing from {day_keys}"
    assert "Tuesday" in day_keys, f"Tuesday missing from {day_keys}"
    assert "Saturday" not in day_keys, f"Saturday should not be in {day_keys}"

    sun_routine = next(r for r in routines if r.get("day_key") == "Sunday")
    sun_ex_names = [e["name"] for e in sun_routine["exercises"]]
    assert "Dumbbell Step Up" in sun_ex_names, f"Dumbbell Step Up missing from Sunday exercises: {sun_ex_names}"
    assert "Bulgarian Split Squat" not in sun_ex_names, f"Bulgarian Split Squat should be replaced in Sunday: {sun_ex_names}"

    vo2_entries = [c for c in cardio if "vo2" in c.get("type", "").lower()]
    assert len(vo2_entries) == 1, f"Expected 1 VO2 entry, got {len(vo2_entries)}"
    assert vo2_entries[0]["day"] == "Friday", f"Expected Friday VO2, got {vo2_entries[0]['day']}"


def test_three_day_split_schedule():
    """Verify 3-day split schedule conforms to Wednesday VO2 and Tue/Fri/Sun strength architecture."""
    prog = load_program(PROGRAM_PATH)
    if "three_day_split" not in prog.get("_file_path", "") and prog.get("PROGRAM_METADATA", {}).get("title", "") != "Three-Day Split 3x — Strength & Polarized Cardio":
        return
    routines = prog["ROUTINES"]
    cardio = prog["CARDIO_SCHEDULE"]

    assert prog["PROGRAM_METADATA"]["session_time_cap_minutes"] == 60

    day_keys = [r.get("day_key") for r in routines]
    assert "Tuesday" in day_keys, f"Tuesday missing from {day_keys}"
    assert "Friday" in day_keys, f"Friday missing from {day_keys}"
    assert "Sunday" in day_keys, f"Sunday missing from {day_keys}"
    assert len(routines) == 3

    # Tuesday Upper
    tue = next(r for r in routines if r.get("day_key") == "Tuesday")
    tue_ex = [e["name"] for e in tue["exercises"]]
    assert "Bench Press (Barbell)" in tue_ex
    assert "Pull Up (Weighted)" in tue_ex
    assert "Seated Shoulder Press (Machine)" in tue_ex

    # Friday Anterior Lower
    fri = next(r for r in routines if r.get("day_key") == "Friday")
    fri_ex = [e["name"] for e in fri["exercises"]]
    assert "Box Squat (Barbell)" in fri_ex
    assert "Dumbbell Step Up" in fri_ex
    assert "Leg Extension (Machine)" in fri_ex
    assert "Hip Abduction (Machine)" in fri_ex

    # Sunday Posterior Full-Body
    sun = next(r for r in routines if r.get("day_key") == "Sunday")
    sun_ex = [e["name"] for e in sun["exercises"]]
    assert "Deadlift (Trap Bar - High Handles)" in sun_ex
    assert "Lat Pulldown (Cable)" in sun_ex
    assert "Seated Leg Curl (Machine)" in sun_ex
    assert "Single Arm Lateral Raise (Cable)" in sun_ex

    # Cardio
    vo2_entries = [c for c in cardio if "vo2" in c.get("type", "").lower()]
    assert len(vo2_entries) == 1, f"Expected 1 VO2 entry, got {len(vo2_entries)}"
    assert vo2_entries[0]["day"] == "Wednesday", f"Expected Wednesday VO2, got {vo2_entries[0]['day']}"
    assert "5x3" in vo2_entries[0]["type"], f"Expected 5x3 in VO2 type, got {vo2_entries[0]['type']}"


def test_parse_work_sets_seconds_suffix_is_duration():
    # "45-60s" is a timed hold, not a rep range; "6" and "3-5" stay reps.
    assert br.parse_work_sets({"work_sets": 1, "reps": "45-60s"}) == [{"duration_seconds": 60}]
    assert br.parse_work_sets({"work_sets": 1, "reps": "30s"}) == [{"duration_seconds": 30}]
    assert br.parse_work_sets({"work_sets": 1, "reps": "6"}) == [{"reps": 6}]
    assert br.parse_work_sets({"work_sets": 1, "reps": "3-5"}) == [{"reps_min": 3, "reps_max": 5, "reps": 3}]


def test_duration_templates_emit_duration_seconds():
    # An exercise whose Hevy template is duration-type (Plank) must sync as seconds, not reps.
    templates = json.loads(br.CACHE_PATH.read_text())
    for r in ROUTINES:
        payload = br.build_routine_payload(r, _fake_resolved(r))
        for ex, ex_payload in zip(r["exercises"], payload["routine"]["exercises"]):
            t = br.find_template(templates, ex["name"])
            if not t or t.get("type") != "duration":
                continue
            work = [s for s in ex_payload["sets"] if s["type"] == "normal"]
            for s in work:
                assert "duration_seconds" in s and "reps" not in s and "rep_range" not in s, \
                    f"{ex['name']} is a duration template but emits {s}"


def run() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
