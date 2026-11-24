import json
import unittest
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import build_routines as br
import eval_evidence_grounding as eeg
from movement_patterns import MOVEMENT_REGISTRY, MovementPattern, filter_candidates


class TestMovementPatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache_file = SCRIPTS_DIR.parent / "data" / "exercise_templates.json"
        cls.templates = json.loads(cache_file.read_text())

    def test_all_registry_exercises_resolve_in_hevy_catalog(self):
        for pattern_name, exercises in MOVEMENT_REGISTRY.items():
            for ex in exercises:
                template = br.find_template(self.templates, ex.name)
                self.assertIsNotNone(
                    template,
                    f"Exercise '{ex.name}' in pattern '{pattern_name}' failed to resolve in Hevy catalog",
                )

    def test_all_registry_exercises_have_canonical_citations(self):
        for _pattern_name, exercises in MOVEMENT_REGISTRY.items():
            for ex in exercises:
                self.assertTrue(ex.evidence_citation, f"{ex.name} missing evidence_citation")
                parsed = eeg.parse_citation(ex.evidence_citation)
                self.assertIsNotNone(
                    parsed,
                    f"Citation '{ex.evidence_citation}' for '{ex.name}' failed canonical parse",
                )

    def test_filter_candidates_by_equipment(self):
        candidates = filter_candidates(
            pattern=MovementPattern.SQUAT,
            allowed_equipment={"dumbbell"},
            joint_profile="standard",
            tier="returning",
        )
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertIn("dumbbell", c.equipment)
            self.assertNotIn("barbell", c.equipment)
    def test_all_registry_citations_resolve_in_grounding_eval(self):
        cache = json.loads((SCRIPTS_DIR.parent / "data" / "consensus_cache.json").read_text())
        doc = (SCRIPTS_DIR.parent / "docs" / "evidence_base.md").read_text()

        for _pattern_name, exercises in MOVEMENT_REGISTRY.items():
            for ex in exercises:
                parsed = eeg.parse_citation(ex.evidence_citation)
                self.assertIsNotNone(parsed, f"Could not parse citation '{ex.evidence_citation}' for {ex.name}")
                ok, src, detail = eeg.resolve_citation(parsed, cache, doc,
                                                       authority=eeg.load_authority(cache_data=cache))
                self.assertTrue(ok, f"Citation '{ex.evidence_citation}' for {ex.name} could not be resolved: {detail}")

    def test_filter_candidates_excludes_exercises_not_allowed_for_the_tier(self):
        def names(tier, equipment):
            return [c.name for c in filter_candidates(MovementPattern.SQUAT, equipment, "standard", tier)]

        # Goblet Squat is registered for returning and intermediate lifters only.
        self.assertIn("Goblet Squat", names("intermediate", {"all"}))
        self.assertNotIn("Goblet Squat", names("advanced", {"all"}))
        self.assertIn("Box Squat (Barbell)", names("advanced", {"all"}))
        self.assertEqual(names("advanced", {"dumbbell"}), [])

    def test_filter_candidates_only_returns_exercises_registered_for_the_tier(self):
        for tier in ("returning", "intermediate", "advanced"):
            for pattern in MovementPattern:
                for c in filter_candidates(pattern, {"all"}, "standard", tier):
                    self.assertIn(tier, c.tiers, f"{c.name} returned for tier {tier}")


if __name__ == "__main__":
    unittest.main()

