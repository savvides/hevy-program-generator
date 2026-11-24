#!/usr/bin/env python3
"""Unit tests for scripts/update_literature.py."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_literature  # noqa: E402
from update_literature import (
    refresh_approved_dois,
    discover_new_papers,
    render_review_markdown,
)

ROOT = Path(__file__).resolve().parent.parent


class TestUpdateLiterature(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "review_id": "test-review-2026",
            "review_date": "2026-11-02",
            "queries": ["resistance training hypertrophy"],
            "primary": [
                {
                    "doi": "10.1249/mss.0000000000003897",
                    "topic": "Adult resistance-training prescription",
                    "policy_use": "Primary prescription synthesis",
                    "verification_depth": "A",
                }
            ],
            "supplemental": [
                {
                    "doi": "10.1007/s40279-015-0365-0",
                    "purpose": "HIIT versus continuous endurance",
                }
            ],
        }
        self.cache = {
            "version": "1.0.0",
            "queries": {},
            "papers": {
                "doi:10.1249/mss.0000000000003897": {
                    "id": "doi:10.1249/mss.0000000000003897",
                    "doi": "10.1249/mss.0000000000003897",
                    "title": "ACSM Position Stand",
                    "authors": ["Currier, B."],
                    "year": 2026,
                    "citation_key": "Currier et al. 2026",
                    "citation_count": 10,
                    "review_provenance": {"review_id": "test-review-2026"},
                },
                "doi:10.1007/s40279-015-0365-0": {
                    "id": "doi:10.1007/s40279-015-0365-0",
                    "doi": "10.1007/s40279-015-0365-0",
                    "title": "Interval Training",
                    "authors": ["Milanović, Z."],
                    "year": 2015,
                    "citation_key": "Milanović et al. 2015",
                    "citation_count": 50,
                },
            },
        }

    def test_refresh_approved_dois_preserves_provenance_and_key(self):
        mock_client = MagicMock()
        mock_client.get_paper.side_effect = lambda doi, **kw: {
            "id": f"doi:{doi}",
            "doi": doi,
            "title": f"Updated {doi}",
            "authors": ["Currier, B."],
            "year": 2026,
            "citation_key": "Currier et al. 2026",
            "citation_count": 999,
        }

        with tempfile.TemporaryDirectory():
            cache_copy = copy.deepcopy(self.cache)
            refreshed = refresh_approved_dois(mock_client, self.manifest, cache_copy, dry_run=True)
            self.assertEqual(refreshed, 2)
            currier = cache_copy["papers"]["doi:10.1249/mss.0000000000003897"]
            self.assertEqual(currier["citation_count"], 999)
            self.assertEqual(currier["review_provenance"], {"review_id": "test-review-2026"})
            self.assertEqual(currier["citation_key"], "Currier et al. 2026")

    def test_discover_new_papers_filters_preprints_and_missing_year(self):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            # 1. Valid new 2025 paper
            {
                "id": "doi:10.1000/new.2025",
                "doi": "10.1000/new.2025",
                "title": "Novel Hypertrophy Findings",
                "authors": ["Tester, T."],
                "year": 2025,
                "journal": "Journal of Sports Science",
                "citation_key": "Tester et al. 2025",
            },
            # 2. Preprint (should be skipped)
            {
                "id": "doi:10.1000/preprint",
                "doi": "10.1000/preprint",
                "title": "Preprint Paper",
                "authors": ["Bio, B."],
                "year": 2025,
                "journal": "bioRxiv",
            },
            # 3. Missing year (should be skipped)
            {
                "id": "doi:10.1000/noyear",
                "doi": "10.1000/noyear",
                "title": "No Year Paper",
                "authors": ["Unknown, U."],
                "year": None,
                "journal": "Sports Medicine",
            },
            # 4. Older than min_year (should be skipped)
            {
                "id": "doi:10.1000/old",
                "doi": "10.1000/old",
                "title": "Old Paper",
                "authors": ["Old, O."],
                "year": 2020,
                "journal": "Sports Medicine",
            },
        ]

        manifest_copy = copy.deepcopy(self.manifest)
        cache_copy = copy.deepcopy(self.cache)
        count, new_entries = discover_new_papers(
            mock_client,
            manifest_copy,
            cache_copy,
            min_year=2025,
            dry_run=True,
        )

        self.assertEqual(count, 1)
        self.assertEqual(new_entries[0]["doi"], "10.1000/new.2025")
        self.assertIn("doi:10.1000/new.2025", cache_copy["papers"])
        self.assertEqual(cache_copy["papers"]["doi:10.1000/new.2025"]["citation_key"], "Tester et al. 2025")

    def test_discover_new_papers_disambiguates_key_collisions(self):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "id": "doi:10.1000/currier.second",
                "doi": "10.1000/currier.second",
                "title": "Another Currier Paper",
                "authors": ["Currier, B."],
                "year": 2026,
                "journal": "MSSE",
                "citation_key": "Currier et al. 2026",
            }
        ]

        manifest_copy = copy.deepcopy(self.manifest)
        cache_copy = copy.deepcopy(self.cache)
        count, new_entries = discover_new_papers(
            mock_client,
            manifest_copy,
            cache_copy,
            min_year=2025,
            dry_run=True,
        )

        self.assertEqual(count, 1)
        disambiguated_key = cache_copy["papers"]["doi:10.1000/currier.second"]["citation_key"]
        self.assertEqual(disambiguated_key, "Currier et al. 2026b")

    def test_refresh_keeps_curated_fields_the_api_does_not_return(self):
        curated = {
            "review_note": "Checked against the journal PDF.",
            "reviewed_on": "2026-11-02",
            "source_url": "https://doi.org/10.1249/mss.0000000000003897",
            "journal_sjr_quartile": "Q1",
            "review_provenance": {"review_id": "test-review-2026"},
        }
        cache_copy = copy.deepcopy(self.cache)
        cache_copy["papers"]["doi:10.1249/mss.0000000000003897"].update(curated)
        mock_client = MagicMock()
        mock_client.get_paper.side_effect = lambda doi, **kw: {
            "id": f"doi:{doi}", "doi": doi, "title": "ACSM Position Stand",
            "authors": ["Currier, B."], "year": 2026,
            "citation_key": "Currier et al. 2026", "citation_count": 999,
        }
        refresh_approved_dois(mock_client, self.manifest, cache_copy, dry_run=True)
        currier = cache_copy["papers"]["doi:10.1249/mss.0000000000003897"]
        for field, value in curated.items():
            self.assertEqual(currier.get(field), value, f"refresh dropped {field}")
        self.assertEqual(currier["citation_count"], 999)
        self.assertEqual(currier["citation_key"], "Currier et al. 2026")

    def _write_inputs(self, td):
        """Compact JSON, so any rewrite by save_json (indent=2) changes the bytes."""
        cache_path = Path(td) / "cache.json"
        manifest_path = Path(td) / "manifest.json"
        cache_path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return cache_path, manifest_path

    def test_discover_dry_run_with_real_client_writes_nothing(self):
        search_payload = {"results": [
            {"doi": "10.1000/new.2025", "title": "Novel Findings", "authors": ["Tester, T.", "B, C."],
             "year": 2025, "journal": "Journal of Sports Science"},
            {"doi": "10.1000/preprint", "title": "Preprint", "authors": ["Bio, B."],
             "year": 2025, "journal": "bioRxiv"},
            {"doi": "10.1000/old", "title": "Old Paper", "authors": ["Old, O."],
             "year": 2020, "journal": "Sports Medicine"},
        ]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(search_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        with tempfile.TemporaryDirectory() as td:
            cache_path, manifest_path = self._write_inputs(td)
            before = (cache_path.read_bytes(), manifest_path.read_bytes())
            with patch.dict("os.environ", {"CONSENSUS_API_KEY": "test-api-key"}), \
                    patch("urllib.request.urlopen", return_value=mock_resp) as urlopen, \
                    patch("time.sleep"), \
                    patch("update_literature.CACHE_PATH", Path(td) / "default_cache.json"), \
                    patch("update_literature.MANIFEST_PATH", Path(td) / "default_manifest.json"):
                rc = update_literature.main([
                    "--discover", "--dry-run", "--delay", "0",
                    "--cache-path", str(cache_path), "--manifest-path", str(manifest_path),
                ])
            self.assertEqual(rc, 0)
            urlopen.assert_called_once()
            self.assertEqual((cache_path.read_bytes(), manifest_path.read_bytes()), before)
            self.assertFalse((Path(td) / "default_cache.json").exists())

    def test_cli_paths_are_used_for_writing(self):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_client.get_paper.return_value = None
        with tempfile.TemporaryDirectory() as td:
            cache_path, manifest_path = self._write_inputs(td)
            before = (cache_path.read_bytes(), manifest_path.read_bytes())
            default_cache = Path(td) / "default_cache.json"
            default_manifest = Path(td) / "default_manifest.json"
            with patch("update_literature.ConsensusClient", return_value=mock_client), \
                    patch("update_literature.CACHE_PATH", default_cache), \
                    patch("update_literature.MANIFEST_PATH", default_manifest):
                rc = update_literature.main([
                    "--refresh-existing", "--discover", "--delay", "0",
                    "--cache-path", str(cache_path), "--manifest-path", str(manifest_path),
                ])
            self.assertEqual(rc, 0)
            self.assertFalse(default_cache.exists(), "wrote the default cache path")
            self.assertFalse(default_manifest.exists(), "wrote the default manifest path")
            self.assertNotEqual(cache_path.read_bytes(), before[0])
            self.assertNotEqual(manifest_path.read_bytes(), before[1])
            self.assertEqual(json.loads(cache_path.read_text(encoding="utf-8"))["papers"].keys(),
                             self.cache["papers"].keys())

    def test_render_review_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "review.md"
            content = render_review_markdown(self.manifest, self.cache, out_file, dry_run=False)
            self.assertTrue(out_file.exists())
            self.assertIn("test-review-2026", content)
            self.assertIn("Currier et al. 2026", content)
            self.assertIn("10.1249/mss.0000000000003897", content)
            self.assertIn("10.1007/s40279-015-0365-0", content)


if __name__ == "__main__":
    unittest.main()
