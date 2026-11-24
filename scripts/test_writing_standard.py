#!/usr/bin/env python3
"""Unit tests for check_writing_standard.py (ASD-STE100 mechanical rules + BLUF)."""
from __future__ import annotations

import contextlib
import copy
import io
import sys
import unittest
from pathlib import Path

import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_routines as br  # noqa: E402
import check_writing_standard as cws  # noqa: E402
import render_program  # noqa: E402
from program_loader import load_program  # noqa: E402

SAMPLE_STE_PROGRAM = {
    "PROGRAM_METADATA": {
        "title": "Sample STE Program",
        "version": "1.0.0",
        "target_demographic": "General Adult Strength",
        "session_time_cap_minutes": 60,
        "min_recovery_buffer_hours": 48,
        "writing_standard": "ASD-STE100",
        "description": "BLUF: Lift two days each week.\nRide easy on two days.",
        "general_notes": "BLUF: Keep good form on every set.\nStop before failure.",
    },
    "ROUTINES": [
        {
            "name": "Tuesday — Full Body A",
            "day_key": "Tuesday",
            "notes": "BLUF: Do three work sets per lift.\nRest two minutes between sets.",
            "exercises": [
                {
                    "name": "Bench Press (Barbell)",
                    "compound": True,
                    "warmup_reps": [5, 5, 3],
                    "work_sets": 3,
                    "reps": "6-8",
                    "rpe": 8,
                    "rest_seconds": 120,
                    "muscle_groups": ["chest", "triceps"],
                    "notes": "BLUF: Add load after 3 x 8 at RPE 8.\nThen start again at 6.",
                    "evidence_citation": "Grgic et al. 2022 (coaching choice); Currier et al. 2026; Andersen et al. 2017",
                }
            ],
        },
        {
            "name": "Saturday — Full Body B",
            "day_key": "Saturday",
            "notes": "BLUF: Do three work sets per lift.\nKeep back neutral.",
            "exercises": [
                {
                    "name": "Goblet Squat",
                    "compound": True,
                    "warmup_reps": [5, 5, 3],
                    "work_sets": 3,
                    "reps": "6-8",
                    "rpe": 8,
                    "rest_seconds": 120,
                    "muscle_groups": ["quads", "glutes"],
                    "notes": "BLUF: Add load after 3 x 8 at RPE 8.\nThen start again at 6.",
                    "evidence_citation": "Grgic et al. 2022 (coaching choice); Currier et al. 2026; Andersen et al. 2017",
                }
            ],
        },
    ],
    "CARDIO_SCHEDULE": [
        {
            "day": "Thursday",
            "modality": "Stationary Bike",
            "type": "Zone 2",
            "duration_minutes": 40,
            "notes": "BLUF: Ride at an easy pace for 40 minutes.",
            "evidence_citation": "Seiler 2010",
        }
    ],
}


class SentenceRules(unittest.TestCase):
    def test_citation_abbreviation_does_not_split_a_sentence(self):
        self.assertEqual(cws.sentences("Evidence: Polito et al. 2021; Currier et al. 2026."),
                         ["Evidence: Polito et al. 2021; Currier et al. 2026."])

    def test_list_items_and_steps_are_sentences(self):
        self.assertEqual(len(cws.sentences("- Do this.\n1. Do that. Then stop.")), 3)

    def test_long_sentence_fails(self):
        long = " ".join(["word"] * 21) + "."
        self.assertTrue(any("21 words" in p for p in cws.check_plain(long, "x")))

    def test_etc_does_not_split_a_long_sentence(self):
        t = ("Use the bar, the rack, the bench, the pins, the bands, etc. and the collars "
             "for every single lift in the gym today, always.")
        self.assertTrue(any("words (max 20)" in p for p in cws.check_plain(t, "x")))

    def test_capitalised_e_g_does_not_split_a_long_sentence(self):
        t = ("Keep the bar on the rack, E.g. during warmup, and keep the pins and the collars "
             "in the bin until the next set starts.")
        self.assertTrue(any("words (max 20)" in p for p in cws.check_plain(t, "x")))

    def test_short_sentence_with_e_g_passes(self):
        self.assertEqual(cws.check_plain("Use a cue, e.g. the bar, for each lift.", "x"), [])

    def test_ing_word_fails_but_technical_name_passes(self):
        self.assertTrue(cws.check_plain("Keep pushing the bar.", "x"))
        self.assertEqual(cws.check_plain("This is a coaching rule for the cycling session.", "x"), [])

    def test_banned_word_names_the_replacement(self):
        problems = cws.check_plain("Ensure that the pin is in.", "x")
        self.assertTrue(any("'make sure'" in p for p in problems))

    def test_passive_voice_fails(self):
        for text in ("The load is lifted by your partner.", "The bar is held at the top.",
                     "Warmup weights are not exported.", "Warmup weights are never exported to Hevy.",
                     "The weight isn’t exported.", "The set is cut short at RPE 9."):
            self.assertTrue(any("passive voice" in p for p in cws.check_plain(text, "x")), text)

    def test_be_with_adjective_name_or_state_is_not_passive(self):
        for text in ("Failure is not necessary.", "The goal is speed.", "The bed is red.",
                     "Thursday is the only full rest day.", "The first lift is Seated Cable Row.",
                     "If you are tired or sore, reduce the load.", "If you are untrained, start at RPE 6."):
            self.assertEqual(cws.check_plain(text, "x"), [], text)

    def test_two_instructions_in_one_sentence_fail(self):
        for text in ("Lift the bar and rack it.", "Do both sides, then record one set.",
                     "Do both sides then record one set.", "Ride easy and then stop.",
                     "Warm up; start the intervals.", "Warm up; then start the intervals.",
                     "Lift the bar and slowly return it.", "If the bar moves fast, lift the bar and rack it.",
                     "For “per side” sets, do both sides, then record one set.",
                     "Per side: do both sides, then record one set.",
                     # "before", "after" and "until" as prepositions do not end the main clause.
                     "Stop before failure and record the RPE.", "Ride easy after the warmup, then stop.",
                     "Lift the bar until RPE 8 and rack it."):
            self.assertTrue(any("one instruction per sentence" in p for p in cws.check_plain(text, "x")), text)

    def test_one_instruction_with_lists_conditions_or_descriptions_passes(self):
        for text in ("Bench Press and Pull-Up: stop at RPE 8.", "Heavy upper push and pull.",
                     "Upper body presses, then leg accessories.",
                     "Do a ramp test in week 1 and then each 6th week.",
                     "Record the power, the heart rate and the session RPE.",
                     "Evidence: Polito et al. 2021; Currier et al. 2026.",
                     # A condition clause holds no instruction.
                     "If you get all the reps and keep good technique, add load.",
                     "If you feel tired and do not sleep well, do a lighter week.",
                     # Descriptive sentences and relative clauses.
                     "You can talk and breathe easily at this effort.",
                     "The lift sessions start at 05:00 and finish before 06:00.",
                     "Easy rides add volume and keep fatigue low.",
                     "Use a target power that you can hold and repeat for all 6 bouts.",
                     "Start the work sets when your muscles are loose and warm.",
                     # Verbs used as nouns, and hyphenated nouns.
                     "Record the start and stop times of each session.", "Use tempo and pause reps.",
                     "Do the crunch and sit-up.", "Take the work and warm-up sets from the plan."):
            self.assertEqual(cws.check_plain(text, "x"), [], text)

class BlufRules(unittest.TestCase):
    def test_section_without_bluf_fails(self):
        self.assertTrue(any("must start with" in p for p in cws.check_block("Do the sets.", "x")))

    def test_each_section_needs_its_own_bluf(self):
        text = "BLUF: Do the sets.\n- Rest.\n\nAdd load."
        self.assertTrue(any("§2" in p for p in cws.check_block(text, "x")))

    def test_warning_section_is_allowed(self):
        self.assertEqual(cws.check_block("WARNING: Stop if you feel chest pain.", "x"), [])

    def test_more_than_six_sentences_after_bluf_fails(self):
        text = "BLUF: Short.\n" + "\n".join(f"- Do step {i}." for i in range(7))
        self.assertTrue(any("7 sentences" in p for p in cws.check_block(text, "x")))


class ProgramGate(unittest.TestCase):
    def test_sample_ste_program_declares_and_passes(self):
        prog = copy.deepcopy(SAMPLE_STE_PROGRAM)
        self.assertEqual(prog["PROGRAM_METADATA"]["writing_standard"], "ASD-STE100")
        self.assertEqual(cws.check_program(prog), [])
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(
                f"PROGRAM_METADATA = {prog['PROGRAM_METADATA']!r}\n"
                f"ROUTINES = {prog['ROUTINES']!r}\n"
                f"CARDIO_SCHEDULE = {prog['CARDIO_SCHEDULE']!r}\n"
            )
            tmp_path = tf.name
        try:
            self.assertEqual(cws.main(["--program", tmp_path]), 0)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_regression_in_session_notes_is_caught(self):
        prog = copy.deepcopy(SAMPLE_STE_PROGRAM)
        prog["ROUTINES"][0]["notes"] = "Bench 3x3-5 @ RPE 8; ensure you are performing controlled reps."
        problems = cws.check_program(prog)
        self.assertTrue(any("must start with" in p for p in problems))
        self.assertTrue(any("performing" in p for p in problems))

    def test_long_hevy_note_is_caught(self):
        prog = copy.deepcopy(SAMPLE_STE_PROGRAM)
        prog["ROUTINES"][0]["exercises"][0]["notes"] = "Use a very long cue. " * 15
        self.assertTrue(any("Hevy note" in p and "characters" in p for p in cws.check_program(prog)))

    def test_program_without_flag_is_skipped(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cws.main(["--program", "programs/starter_full_body_2x.py"])
        self.assertEqual(code, 0)
        self.assertTrue(out.getvalue().startswith("SKIP:"), out.getvalue())

    def test_rendered_plan_has_checked_total_sets_note(self):
        self.assertIn("TOTAL_SETS_NOTE", render_program.STATIC_NOTES)
        self.assertNotIn("Warmups are not included", render_program.render(copy.deepcopy(SAMPLE_STE_PROGRAM)))


class CompactHevyExport(unittest.TestCase):
    def test_compact_export_shows_citation_keys_not_claims(self):
        routine = copy.deepcopy(SAMPLE_STE_PROGRAM)["ROUTINES"][1]
        payload = br.build_routine_payload(routine, {e["name"]: 0 for e in routine["exercises"]}, compact=True)
        first = payload["routine"]["exercises"][0]["notes"]
        self.assertIn("Evidence: Grgic et al. 2022; Currier et al. 2026; Andersen et al. 2017.", first)
        self.assertNotIn("coaching choice)", first)
        self.assertTrue(first.startswith("BLUF:"))
        self.assertIn("Add load after 3 x 8 at RPE 8.", first)
        self.assertIn("Then start again at 6.", first)
        self.assertLessEqual(len(first), 250)

    def test_all_sample_exercises_have_bluf_under_250_chars(self):
        prog = copy.deepcopy(SAMPLE_STE_PROGRAM)
        for routine in prog["ROUTINES"]:
            payload = br.build_routine_payload(routine, {e["name"]: 0 for e in routine["exercises"]}, compact=True)
            for ex_payload, ex in zip(payload["routine"]["exercises"], routine["exercises"]):
                note = ex_payload["notes"]
                self.assertTrue(note.startswith("BLUF:"), f"{ex['name']} does not start with BLUF:")
                self.assertIn("Add load after", note, f"{ex['name']} missing progression rule")
                self.assertLessEqual(len(note), 250, f"{ex['name']} exceeds 250 chars ({len(note)} chars)")

    def test_citation_keys_ignore_semicolons_inside_claims(self):
        raw = "Polito et al. 2021 (a; b); Buchheit & Laursen 2013 (c)"
        self.assertEqual(br.citation_keys(raw), ["Polito et al. 2021", "Buchheit & Laursen 2013"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
