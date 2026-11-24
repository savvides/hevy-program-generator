#!/usr/bin/env python3
"""Unit tests for Consensus standard-library client with mocked HTTP responses."""
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from consensus_client import ConsensusClient, normalize_query


class TestConsensusClient(unittest.TestCase):
    def test_normalize_query(self):
        q1 = normalize_query("Seated Leg Curl Hypertrophy!!")
        q2 = normalize_query("hypertrophy seated leg curl")
        self.assertEqual(q1, q2)

    def test_normalize_query_stop_words_and_punctuation(self):
        q1 = normalize_query("The Seated Leg Curl vs Prone Leg Curl for Hypertrophy")
        q2 = normalize_query("seated prone leg curl hypertrophy")
        self.assertEqual(q1, q2)

    def test_cache_hit_makes_no_network_call(self):
        client = ConsensusClient(cache_path=None)
        client.cache = {
            "queries": {"leg curl seated": {"paper_ids": ["doi:10.1249/01"]}},
            "papers": {
                "doi:10.1249/01": {
                    "title": "Hamstring Hypertrophy",
                    "citation_key": "Maeo et al. 2021",
                    "takeaway": "Greater lengthened hypertrophy.",
                }
            },
        }
        with patch("urllib.request.urlopen") as mock_url:
            results = client.search("Seated Leg Curl", use_cache=True)
            mock_url.assert_not_called()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["citation_key"], "Maeo et al. 2021")

    def test_format_citation(self):
        client = ConsensusClient(cache_path=None)
        paper = {
            "citation_key": "Maeo et al. 2021",
            "takeaway": "Seated leg curl lengthened hypertrophy",
        }
        formatted = client.format_citation(paper)
        self.assertIn("Maeo et al. 2021", formatted)
        self.assertIn("lengthened hypertrophy", formatted)

    def test_format_citation_with_custom_claim(self):
        client = ConsensusClient(cache_path=None)
        paper = {
            "citation_key": "Maeo et al. 2021",
            "takeaway": "Seated leg curl lengthened hypertrophy",
        }
        formatted = client.format_citation(paper, claim="lengthened hamstring hypertrophy")
        self.assertEqual(formatted, "Maeo et al. 2021 (lengthened hamstring hypertrophy)")

    def test_cache_miss_with_mocked_network_call(self):
        client = ConsensusClient(cache_path=None, api_key="test-api-key")
        mock_response_data = {
            "results": [
                {
                    "doi": "10.1000/182",
                    "title": "Resistance Training Adaptations",
                    "authors": ["Smith, J.", "Doe, A."],
                    "year": 2023,
                    "citation_key": "Smith et al. 2023",
                    "takeaway": "Significant adaptations observed.",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
            results = client.search("Novel Training Adaptation", use_cache=True)
            mock_url.assert_called_once()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["citation_key"], "Smith et al. 2023")
            # Verify cached in memory
            self.assertIn("doi:10.1000/182", client.cache["papers"])

    def test_exhausted_key_suffixes_never_persist_a_duplicate_key(self):
        keys = ["Smith et al. 2025", "Smith et al. 2025b", "Smith et al. 2025c", "Smith et al. 2025d"]
        papers = {
            f"doi:10.1000/smith.{i}": {"id": f"doi:10.1000/smith.{i}", "doi": f"10.1000/smith.{i}",
                                       "title": f"Smith {i}", "authors": ["Smith, J.", "Doe, A."],
                                       "year": 2025, "citation_key": key}
            for i, key in enumerate(keys)
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": [
            {"doi": "10.1000/smith.fifth", "title": "Fifth Smith", "authors": ["Smith, J.", "Roe, B."],
             "year": 2025, "takeaway": "x"},
        ]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        with tempfile.TemporaryDirectory() as td:
            cache_path = Path(td) / "cache.json"
            cache_path.write_text(json.dumps({"version": "1.0.0", "queries": {}, "papers": papers}),
                                  encoding="utf-8")
            client = ConsensusClient(cache_path=cache_path, api_key="test-api-key")
            with patch("urllib.request.urlopen", return_value=mock_resp):
                results = client.search("smith fifth", use_cache=False)
            self.assertEqual(len(results), 1)
            saved = json.loads(cache_path.read_text(encoding="utf-8"))
        saved_keys = [p["citation_key"] for p in saved["papers"].values()]
        self.assertEqual(len(saved_keys), len(set(saved_keys)), saved_keys)
        for q in saved["queries"].values():
            for pid in q["paper_ids"]:
                self.assertIn(pid, saved["papers"])

    def test_cache_only_makes_no_network_call_on_miss(self):
        client = ConsensusClient(cache_path=None, api_key="test-api-key", cache_only=True)
        with patch("urllib.request.urlopen") as mock_url:
            results = client.search("Nonexistent query unknown 12345", use_cache=True)
            mock_url.assert_not_called()
            self.assertEqual(results, [])

    def test_get_paper_by_doi_cache_hit(self):
        client = ConsensusClient(cache_path=None)
        client.cache = {
            "queries": {},
            "papers": {
                "doi:10.1249/MSS.0000000000002523": {
                    "doi": "10.1249/MSS.0000000000002523",
                    "title": "Seated Leg Curl Study",
                    "citation_key": "Maeo et al. 2021",
                    "takeaway": "Lengthened position hypertrophy.",
                }
            },
        }
        # Lookup with doi: prefix
        p1 = client.get_paper("doi:10.1249/MSS.0000000000002523")
        self.assertIsNotNone(p1)
        self.assertEqual(p1["citation_key"], "Maeo et al. 2021")

        # Lookup without doi: prefix and case-insensitive
        p2 = client.get_paper("10.1249/mss.0000000000002523")
        self.assertIsNotNone(p2)
        self.assertEqual(p2["citation_key"], "Maeo et al. 2021")

    def test_get_paper_network_fetch_and_cache(self):
        client = ConsensusClient(cache_path=None, api_key="test-api-key")
        # The live API resolves a DOI through /v1/search and returns an envelope
        # of results, not a bare paper object.
        mock_paper_data = {
            "results": [
                {
                    "doi": "10.1016/j.jshs.2021.01.007",
                    "title": "Resistance Training to Failure",
                    "authors": ["Polito, M.", "Souza, D."],
                    "publish_year": 2021,
                    "takeaway": "Submaximal failure training yields similar gains.",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_paper_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        # 1. When a paper is not in cache and use_cache=True with API key set,
        # get_paper fetches from API via urlopen, caches it into self.cache["papers"], and returns it.
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
            paper = client.get_paper("10.1016/j.jshs.2021.01.007", use_cache=True)
            mock_url.assert_called_once()
            self.assertIsNotNone(paper)
            self.assertEqual(paper["citation_key"], "Polito et al. 2021")
            self.assertIn("doi:10.1016/j.jshs.2021.01.007", client.cache["papers"])
            self.assertEqual(
                client.cache["papers"]["doi:10.1016/j.jshs.2021.01.007"]["title"],
                "Resistance Training to Failure",
            )

        # 2. When cache_only=True, get_paper never calls urlopen on cache miss.
        with patch("urllib.request.urlopen") as mock_url:
            # Client-level cache_only=True
            client_cache_only = ConsensusClient(
                cache_path=None, api_key="test-api-key", cache_only=True
            )
            res_client = client_cache_only.get_paper("10.9999/uncached.1")
            self.assertIsNone(res_client)
            mock_url.assert_not_called()

            # Argument-level cache_only=True
            res_arg = client.get_paper("10.9999/uncached.2", cache_only=True)
            self.assertIsNone(res_arg)
            mock_url.assert_not_called()

    def test_find_in_cache_never_triggers_network(self):
        client = ConsensusClient(cache_path=None, api_key="test-api-key", cache_only=False)
        client.cache = {
            "queries": {
                "bench press rpe": {"paper_ids": ["doi:10.9999/missing_paper_1"]},
                "squat depth": {"paper_ids": ["doi:10.9999/missing_paper_2"]},
            },
            "papers": {},
        }
        with patch("urllib.request.urlopen") as mock_url:
            # Query exact match
            res1 = client._find_in_cache("bench press rpe")
            self.assertEqual(res1, [])

            # Query fuzzy overlap match
            res2 = client._find_in_cache("squat depth knee")
            self.assertEqual(res2, [])

            mock_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
