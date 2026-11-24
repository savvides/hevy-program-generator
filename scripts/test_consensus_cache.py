#!/usr/bin/env python3
"""Unit tests for Consensus local literature cache integrity."""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = REPO_ROOT / "data" / "consensus_cache.json"


class TestConsensusCache(unittest.TestCase):
    def test_cache_file_exists_and_valid_json(self):
        self.assertTrue(CACHE_FILE.exists(), f"Cache file {CACHE_FILE} missing")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("version", data)
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("queries", data)
        self.assertIsInstance(data["queries"], dict)
        self.assertIn("papers", data)
        self.assertIsInstance(data["papers"], dict)
        self.assertGreater(len(data["papers"]), 10, "Seed cache must contain baseline studies")

    def test_paper_schema(self):
        self.assertTrue(CACHE_FILE.exists(), f"Cache file {CACHE_FILE} missing")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for paper_id, paper in data["papers"].items():
            self.assertIn("title", paper, f"Paper {paper_id} missing title")
            self.assertIsInstance(paper["title"], str)
            self.assertTrue(paper["title"].strip())

            self.assertIn("authors", paper, f"Paper {paper_id} missing authors")
            self.assertIsInstance(paper["authors"], list)
            self.assertGreater(len(paper["authors"]), 0)

            self.assertIn("year", paper, f"Paper {paper_id} missing year")
            self.assertIsInstance(paper["year"], int)

            self.assertIn("citation_key", paper, f"Paper {paper_id} missing citation_key")
            self.assertIsInstance(paper["citation_key"], str)
            self.assertTrue(paper["citation_key"].strip())

            for key in paper:
                self.assertNotIn(
                    key.lower(),
                    {"abstract", "takeaway"},
                    f"Paper {paper_id} must not contain verbatim {key}",
                )
            raw_export = paper.get("raw_export")
            if isinstance(raw_export, dict):
                for key in raw_export:
                    self.assertNotIn(
                        key.lower(),
                        {"abstract", "takeaway"},
                        f"Paper {paper_id} raw_export must not contain verbatim {key}",
                    )

    def test_queries_are_empty_in_public_seed(self):
        self.assertTrue(CACHE_FILE.exists(), f"Cache file {CACHE_FILE} missing")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["queries"], {}, "Public seed cache must not carry personal query history")

    def test_required_seed_studies_present(self):
        self.assertTrue(CACHE_FILE.exists(), f"Cache file {CACHE_FILE} missing")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        citation_keys = {key for p in data["papers"].values()
                         for key in [p.get("citation_key"), *p.get("citation_aliases", [])]}

        required_seeds = [
            "Currier et al. 2026",
            "Polito et al. 2021",
            "Schumann et al. 2021",
            "Milanović et al. 2015",
            "Seiler 2010",
            "Maeo et al. 2021",
            "McGill 2010",
            "Grgic et al. 2021",
            "Nunes et al. 2022",
            "Moore et al. 2014",
        ]
        for key in required_seeds:
            self.assertIn(key, citation_keys, f"Missing required seed study citation key: '{key}'")


    def test_citation_keys_are_canonical_and_unique(self):
        """A degraded key is the symptom that 40 rows once carried silently."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from eval_evidence_grounding import CITATION_REGEX

        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        seen: dict[str, str] = {}
        for paper_id, paper in data["papers"].items():
            key = paper["citation_key"]
            self.assertNotEqual(
                key, paper["title"], f"{paper_id}: citation_key degraded to the title"
            )
            self.assertIsNotNone(
                CITATION_REGEX.match(key),
                f"{paper_id}: citation_key {key!r} is not 'Author et al. YYYY'",
            )
            self.assertNotIn(
                key, seen, f"{paper_id}: citation_key {key!r} duplicates {seen.get(key)}"
            )
            seen[key] = paper_id

    def test_paper_ids_are_canonical_lowercase_dois(self):
        """The writer and the case-insensitive reader must agree, or records fork."""
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        papers = data["papers"]
        self.assertEqual(
            len({pid.lower() for pid in papers}),
            len(papers),
            "paper ids differ only by case — the DOI fork has returned",
        )
        for paper_id, paper in papers.items():
            if paper.get("doi"):
                self.assertEqual(
                    paper_id,
                    f"doi:{paper['doi'].lower()}",
                    f"{paper_id}: id does not match its lowercased DOI",
                )


if __name__ == "__main__":
    unittest.main()
