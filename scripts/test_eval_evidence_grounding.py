#!/usr/bin/env python3
"""Unit tests for evidence grounding compiler gate."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from eval_evidence_grounding import (  # noqa: E402
    eval_program_evidence,
    parse_citation,
    resolve_citation,
    split_citations,
)

REPO_ROOT = SCRIPTS_DIR.parent
STARTER_PROG = str(REPO_ROOT / "programs" / "starter_full_body_2x.py")
THREE_DAY_PROG = str(REPO_ROOT / "programs" / "three_day_split_3x.py")


def _write_mock_program(exercises: list[dict], cardio: list[dict] | None = None) -> str:
    """Helper to write a schema-valid mock program."""
    exercises = [{"rpe": 8, "warmup_reps": [5, 5, 3], **ex} for ex in exercises]
    content = f"""
PROGRAM_METADATA = {{
    "title": "Test Prog",
    "session_time_cap_minutes": 60,
}}
ROUTINES = [
    {{
        "name": "Day 1",
        "day_key": "Tuesday",
        "exercises": {repr(exercises)},
    }}
]
CARDIO_SCHEDULE = {repr(cardio or [])}
"""
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(content)
    f.close()
    return f.name


class TestEvalEvidenceGrounding(unittest.TestCase):
    def test_starter_program_passes_evidence_gate(self):
        passed, diag = eval_program_evidence(STARTER_PROG)
        self.assertTrue(passed, f"Starter program failed evidence gate: {diag}")

    def test_three_day_program_passes_evidence_gate(self):
        passed, diag = eval_program_evidence(THREE_DAY_PROG)
        self.assertTrue(passed, f"Three-day program failed evidence gate: {diag}")

    def test_parse_citation_canonical(self):
        parsed = parse_citation("Polito et al. 2021 (RPE 8 submaximal strength)")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "Polito et al.")
        self.assertEqual(parsed["year"], 2021)
        self.assertEqual(parsed["claim"], "RPE 8 submaximal strength")
        self.assertEqual(parsed["citation_key"], "Polito et al. 2021")

    def test_parse_citation_single_author_and_claim(self):
        parsed = parse_citation("McGill 2010 (anti-rotation core stability)")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "McGill")
        self.assertEqual(parsed["year"], 2010)
        self.assertEqual(parsed["claim"], "anti-rotation core stability")
        self.assertEqual(parsed["citation_key"], "McGill 2010")

    def test_parse_citation_without_claim(self):
        parsed = parse_citation("Currier et al. 2026")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "Currier et al.")
        self.assertEqual(parsed["year"], 2026)
        self.assertIsNone(parsed["claim"])
        self.assertEqual(parsed["citation_key"], "Currier et al. 2026")

    def test_parse_citation_unicode_name(self):
        parsed = parse_citation("Milanović et al. 2015")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "Milanović et al.")
        self.assertEqual(parsed["year"], 2015)

    def test_parse_citation_surname_with_particle(self):
        parsed = parse_citation("van Loon et al. 2000 (glycogen resynthesis)")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "van Loon et al.")
        self.assertEqual(parsed["year"], 2000)
        self.assertEqual(parsed["claim"], "glycogen resynthesis")
        self.assertEqual(parsed["citation_key"], "van Loon et al. 2000")

    def test_parse_citation_invalid_format(self):
        self.assertIsNone(parse_citation("Random unformatted text"))
        self.assertIsNone(parse_citation(""))
        self.assertIsNone(parse_citation("Polito et al."))
        self.assertIsNone(parse_citation("2021"))

    def test_missing_citation_fails_evaluation(self):
        exercises = [
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "work_sets": 3,
                "reps": "5",
                "rest_seconds": 120,
                "muscle_groups": ["chest"],
            }
        ]
        tmp_path = _write_mock_program(exercises)
        try:
            passed, diag = eval_program_evidence(tmp_path)
            self.assertFalse(passed)
            self.assertTrue(
                "evidence_citation" in diag,
                f"Expected citation error in diag: {diag}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_invalid_citation_format_fails_evaluation(self):
        exercises = [
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "work_sets": 3,
                "reps": "5",
                "rest_seconds": 120,
                "muscle_groups": ["chest"],
                "evidence_citation": "Bro Science 101",
            }
        ]
        tmp_path = _write_mock_program(exercises)
        try:
            passed, diag = eval_program_evidence(tmp_path)
            self.assertFalse(passed)
            self.assertIn("Invalid citation format", diag)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_unresolved_citation_fails_evaluation(self):
        exercises = [
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "work_sets": 3,
                "reps": "5",
                "rest_seconds": 120,
                "muscle_groups": ["chest"],
                "evidence_citation": "NonexistentAuthor et al. 1920 (Fake Claim)",
            }
        ]
        tmp_path = _write_mock_program(exercises)
        try:
            passed, diag = eval_program_evidence(tmp_path)
            self.assertFalse(passed)
            self.assertIn("Unresolved citation", diag)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_cardio_citation_with_only_separators_fails(self):
        exercises = [
            {
                "name": "Bench Press (Barbell)",
                "compound": True,
                "work_sets": 3,
                "reps": "5",
                "rest_seconds": 120,
                "muscle_groups": ["chest"],
                "evidence_citation": "Currier et al. 2026 (resistance-training prescription)",
            }
        ]
        cardio = [
            {
                "day": "Monday",
                "modality": "Stationary Bike",
                "type": "Zone 2",
                "duration_minutes": 40,
                "evidence_citation": " ; ",
            }
        ]
        tmp_path = _write_mock_program(exercises, cardio)
        try:
            passed, diag = eval_program_evidence(tmp_path)
            self.assertFalse(passed, diag)
            self.assertIn("Invalid citation format on cardio 'Monday Zone 2'", diag)
            self.assertIn("FAIL: 1 evidence grounding violation", diag)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_verify_online_does_not_approve_uncached_citation(self):
        exercises = [
            {
                "name": "Bicep Curl",
                "compound": False,
                "work_sets": 3,
                "reps": "10",
                "rest_seconds": 60,
                "muscle_groups": ["biceps"],
                "evidence_citation": "Kraemer et al. 2004 (endocrine responses)",
            }
        ]
        tmp_path = _write_mock_program(exercises)
        try:
            with patch("eval_evidence_grounding.ConsensusClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.search.return_value = [
                    {
                        "id": "doi:10.1249/01.MSS.0000117111.00000.00",
                        "title": "Fundamentals of resistance training...",
                        "authors": ["Kraemer, W. J."],
                        "year": 2004,
                        "citation_key": "Kraemer et al. 2004",
                    }
                ]
                mock_client_cls.return_value = mock_client
                passed, diag = eval_program_evidence(tmp_path, verify_online=True)
                self.assertFalse(passed, f"Online discovery bypassed authority: {diag}")
                self.assertIn("Unresolved citation", diag)
                mock_client.search.assert_not_called()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_verify_online_rejects_matching_year_different_author(self):
        exercises = [
            {
                "name": "Bicep Curl",
                "compound": False,
                "work_sets": 3,
                "reps": "10",
                "rest_seconds": 60,
                "muscle_groups": ["biceps"],
                "evidence_citation": "UncachedAuthor et al. 2024 (novel stimulus)",
            }
        ]
        tmp_path = _write_mock_program(exercises)
        try:
            with patch("eval_evidence_grounding.ConsensusClient") as mock_client_cls:
                mock_client = MagicMock()
                # API returns a paper with matching year 2024, but completely different author
                mock_client.search.return_value = [
                    {
                        "id": "doi:10.1234/totally.different.2024",
                        "title": "A completely different study...",
                        "authors": ["TotallyDifferentAuthor, J."],
                        "year": 2024,
                        "citation_key": "TotallyDifferentAuthor et al. 2024",
                    }
                ]
                mock_client_cls.return_value = mock_client
                passed, diag = eval_program_evidence(tmp_path, verify_online=True)
                self.assertFalse(passed, "Expected validation failure for different author")
                self.assertIn("Unresolved citation", diag)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestCitationRegexSurnameForms(unittest.TestCase):
    """Widening _AUTHOR_NAME must admit compound surnames without admitting titles."""

    ACCEPT = [
        "Currier et al. 2026",
        "van Loon et al. 2000",
        "Buchheit & Laursen 2013",
        "O'Brien et al. 2019",
        "García-López et al. 2021",
        "Moore 2014",
        "Krause Neto et al. 2025",
        "Maia de Farias et al. 2024",
        "Stoll de Vargas et al. 2022",
    ]

    REJECT = [
        "Muscle forces and fascicle behavior during three hamstring exercises",
        "Eccentric And Concentric Motion Of Hamstring During The Leg Curl 2020",
        "Resistance training volume enhances muscle hypertrophy 2017",
        "Currier et al.",
        "et al. 2026",
    ]

    def test_accepts_every_real_surname_form(self):
        for citation in self.ACCEPT:
            with self.subTest(citation=citation):
                self.assertIsNotNone(
                    parse_citation(citation), f"should accept {citation!r}"
                )

    def test_still_rejects_titles_and_malformed_citations(self):
        for citation in self.REJECT:
            with self.subTest(citation=citation):
                self.assertIsNone(
                    parse_citation(citation), f"should reject {citation!r}"
                )



class TestSurnameYearFallback(unittest.TestCase):
    """The surname-and-year fallback must not resolve a key that no record carries."""

    CACHE = {"papers": {
        "doi:10.1/helms": {"id": "doi:10.1/helms", "doi": "10.1/helms", "year": 2025,
                           "authors": ["Helms, E.", "Smith, J."], "citation_key": "Helms et al. 2025"},
        "doi:10.1/kerr": {"id": "doi:10.1/kerr", "doi": "10.1/kerr", "year": 2019,
                          "authors": ["Kerr, D.", "Lee, F."], "citation_key": "Kerr et al. 2019b"},
    }}
    AUTHORITY = {"doi:10.1/helms": "primary", "doi:10.1/kerr": "primary"}

    def resolves(self, citation):
        return resolve_citation(parse_citation(citation), self.CACHE, authority=self.AUTHORITY)[0]

    def test_wrong_year_suffix_does_not_resolve(self):
        self.assertFalse(self.resolves("Helms et al. 2025q"))
        self.assertFalse(self.resolves("Kerr et al. 2019"))
        self.assertFalse(self.resolves("Kerr et al. 2019c"))

    def test_invented_coauthor_does_not_resolve(self):
        self.assertFalse(self.resolves("Helms & Nobody 2025"))

    def test_correct_keys_and_shorthand_still_resolve(self):
        for citation in ("Helms et al. 2025", "Helms 2025", "Helms & Smith 2025",
                         "Kerr et al. 2019b", "Kerr 2019b"):
            with self.subTest(citation=citation):
                self.assertTrue(self.resolves(citation))


class TestMultiSourceCitations(unittest.TestCase):
    """Every source in a multi-source citation must be resolved, not only the first."""

    def test_splits_on_semicolons_and_commas_outside_parentheses(self):
        self.assertEqual(
            split_citations("Polito et al. 2021 (a); Andersen et al. 2017 (b), McGill 2010"),
            ["Polito et al. 2021 (a)", "Andersen et al. 2017 (b)", "McGill 2010"],
        )

    def test_keeps_semicolons_and_commas_inside_a_claim(self):
        raw = "Polito et al. 2021 (sets that stop before failure; RPE 8, approximately)"
        self.assertEqual(split_citations(raw), [raw])

    def test_chained_citation_string_is_not_one_citation(self):
        self.assertIsNone(parse_citation("Polito et al. 2021 (a); Andersen et al. 2017 (b)"))

    def test_balanced_nested_parentheses_in_claim_still_parse(self):
        parsed = parse_citation("Seiler 2010 (polarized model (endurance athletes))")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["claim"], "polarized model (endurance athletes)")

    def test_starter_program_resolves_all_citations(self):
        passed, diag = eval_program_evidence(str(REPO_ROOT / "programs" / "starter_full_body_2x.py"))
        self.assertTrue(passed, diag)
        for key in ("Grgic et al. 2022", "Currier et al. 2026", "McGill 2010",
                    "Seiler 2010", "Milanović et al. 2015", "Schumann et al. 2022"):
            self.assertIn(f"({key})]", diag, f"{key} was never resolved")


if __name__ == "__main__":
    unittest.main()
