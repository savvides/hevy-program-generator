"""Regression tests for dated DOI authority and fail-closed resolution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from consensus_client import ConsensusClient
from eval_evidence_grounding import parse_citation, resolve_citation, eval_program_evidence

ROOT = Path(__file__).resolve().parent.parent


class TestAuthority(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "data/evidence_authority.json").read_text(encoding="utf-8"))
        self.cache = json.loads((ROOT / "data/consensus_cache.json").read_text(encoding="utf-8"))

    def load(self, manifest=None, cache=None):
        from evidence_authority import load_authority
        if manifest is None:
            return load_authority(cache_data=cache or self.cache)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.json"
            manifest = copy.deepcopy(manifest)
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return load_authority(path, self.cache if cache is None else cache)

    def test_primary_and_supplemental_doi_coverage(self):
        self.assertIn("review_id", self.manifest)
        self.assertIn("review_date", self.manifest)
        self.assertIn("primary", self.manifest)
        self.assertIn("supplemental", self.manifest)
        self.assertGreaterEqual(len(self.manifest["primary"]), 100)
        self.assertEqual(len(self.manifest["supplemental"]), 8)

        roles = self.load()
        primary_dois = {"doi:" + entry["doi"].lower() for entry in self.manifest["primary"]}
        self.assertEqual({pid for pid, role in roles.items() if role == "primary"}, primary_dois)

        for entry in self.manifest["primary"]:
            pid = "doi:" + entry["doi"].lower()
            paper = self.cache["papers"].get(pid)
            self.assertIsNotNone(paper, f"Paper {pid} missing from cache")

    def test_supplements_have_a_limited_purpose(self):
        roles = self.load()
        self.assertEqual(len(self.manifest["supplemental"]), 8)
        for source in self.manifest["supplemental"]:
            self.assertTrue(source["purpose"].strip())
            self.assertEqual(roles["doi:" + source["doi"]], "supplemental")
        self.assertNotIn("doi:10.1080/02640414.2021.1924978", roles)

    def test_invalid_manifest_fields_fail(self):
        manifest_no_id = copy.deepcopy(self.manifest)
        del manifest_no_id["review_id"]
        with self.assertRaisesRegex(ValueError, "review_id"):
            self.load(manifest_no_id)

        manifest_empty_primary = copy.deepcopy(self.manifest)
        manifest_empty_primary["primary"] = []
        with self.assertRaisesRegex(ValueError, "primary"):
            self.load(manifest_empty_primary)

    def test_invalid_primary_doi_fails(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["primary"][0]["doi"] = "invalid_doi_without_prefix"
        with self.assertRaisesRegex(ValueError, "Missing or invalid DOI"):
            self.load(manifest)

    def test_missing_cache_paper_fails(self):
        del self.cache["papers"]["doi:10.1249/mss.0000000000003897"]
        with self.assertRaisesRegex(ValueError, "missing from cache"):
            self.load(cache=self.cache)

    def test_duplicate_doi_and_supplement_roles_fail(self):
        paper = self.cache["papers"]["doi:10.1249/mss.0000000000003897"]
        self.cache["papers"]["doi:10.1249/MSS.0000000000003897"] = copy.deepcopy(paper)
        with self.assertRaisesRegex(ValueError, "duplicate.*DOI"):
            self.load(cache=self.cache)

        manifest = copy.deepcopy(self.manifest)
        manifest["supplemental"].append(copy.deepcopy(manifest["supplemental"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load(manifest)

    def test_duplicate_primary_doi_fails(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["primary"].append(copy.deepcopy(manifest["primary"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate research DOI"):
            self.load(manifest)

    def test_evaluation_fails_closed_on_bad_authority(self):
        with patch("eval_evidence_grounding.load_authority", side_effect=ValueError("bad manifest authority")):
            passed, details = eval_program_evidence(str(ROOT / "programs/starter_full_body_2x.py"))
        self.assertFalse(passed)
        self.assertIn("bad manifest authority", details)

    def test_verified_year_variants_and_incorrect_export_metadata(self):
        variants = {
            "10.1136/bjsports-2017-097608": ("Morton et al. 2018", "Morton et al. 2017"),
            "10.1016/j.jshs.2021.01.007": ("Grgic et al. 2022", "Grgic et al. 2021"),
            "10.1007/s40279-020-01388-4": ("Jones et al. 2021", "Jones et al. 2020"),
            "10.1080/02640414.2020.1822595": ("Kneffel et al. 2021", "Kneffel et al. 2020"),
            "10.1007/s40279-023-01943-9": ("Huiberts et al. 2024", "Huiberts et al. 2023"),
            "10.1093/ajcn/nqab355": ("Kirwan et al. 2022", "Kirwan et al. 2021"),
            "10.1111/sms.14075": ("Murphy et al. 2022", "Murphy et al. 2021"),
            "10.1007/s40279-024-02130-0": ("Gallant et al. 2025", "Gallant et al. 2024"),
            "10.1007/s11357-025-01877-2": ("Jacob et al. 2026", "Jacob et al. 2025"),
            "10.1007/s40279-025-02344-w": ("Pelland et al. 2026", "Pelland et al. 2025"),
        }
        roles = self.load()
        for doi, (canonical, alias) in variants.items():
            paper = self.cache["papers"]["doi:" + doi]
            self.assertEqual(paper["citation_key"], canonical)
            self.assertIn(alias, paper["citation_aliases"])
            self.assertTrue(resolve_citation(parse_citation(alias), self.cache, authority=roles)[0])
        acsm = self.cache["papers"]["doi:10.1249/mss.0b013e3181915670"]
        self.assertEqual(acsm["year"], 2009)
        self.assertFalse(resolve_citation(parse_citation("Ratamess et al. 2011"), self.cache, authority=roles)[0])
        gielen = self.cache["papers"]["doi:10.1093/nutrit/nuaa011"]
        self.assertEqual(gielen["citation_key"], "Gielen et al. 2021")
        self.assertFalse(resolve_citation(parse_citation("Beckwée et al. 2020"), self.cache, authority=roles)[0])

    def test_canonical_key_collision_fails_loading(self):
        self.cache["papers"]["doi:10.1002/jcsm.12922"]["citation_key"] = "Currier et al. 2026"
        with self.assertRaisesRegex(ValueError, "duplicate canonical citation key"):
            self.load(cache=self.cache)

    def test_offline_repair_preserves_all_reviewed_records_and_corporate_authority(self):
        from repair_consensus_cache import repair_papers
        repaired, changed = repair_papers(self.cache["papers"])
        acsm_id = "doi:10.1249/mss.0b013e3181915670"
        self.assertEqual(repaired[acsm_id]["citation_key"], "ACSM 2009")
        self.assertEqual(changed, 0)
        roles = self.load()
        primary_ids = [pid for pid, role in roles.items() if role == "primary"]
        self.assertGreaterEqual(len(primary_ids), 100)
        for pid in primary_ids:
            with self.subTest(pid=pid):
                self.assertEqual(repaired[pid], self.cache["papers"][pid])
        self.assertEqual(repaired, self.cache["papers"])
        repaired_cache = {**self.cache, "papers": repaired}
        self.assertEqual(self.load(cache=repaired_cache), roles)
        resolved, source, _ = resolve_citation(parse_citation("ACSM 2009"), repaired_cache, authority=roles)
        self.assertTrue(resolved)
        self.assertIn("primary", source)
        self.assertFalse(resolve_citation(parse_citation("Medicine 2009"), repaired_cache, authority=roles)[0])


class TestResolutionAuthority(unittest.TestCase):
    def paper(self, doi, key="Smith et al. 2024", authors=None):
        return {"id": "doi:" + doi, "doi": doi, "citation_key": key,
                "year": 2024, "authors": authors or ["Smith, J.", "Brown, A."]}

    def resolve(self, papers, citation="Smith et al. 2024", authority=None, **kwargs):
        return resolve_citation(parse_citation(citation), {"papers": papers},
                                authority=authority or {"doi:10.1/a": "primary"}, **kwargs)

    def test_primary_and_supplemental_diagnostics(self):
        for role in ("primary", "supplemental"):
            ok, source, _ = self.resolve({"doi:10.1/a": self.paper("10.1/a")},
                                         authority={"doi:10.1/a": role})
            self.assertTrue(ok)
            self.assertIn(role, source)

    def test_background_and_document_cannot_promote_authority(self):
        ok, _, _ = self.resolve({"doi:10.1/b": self.paper("10.1/b")},
                               evidence_doc_text="Smith et al. 2024")
        self.assertFalse(ok)

    def test_online_cannot_promote_authority(self):
        client = MagicMock()
        client.search.return_value = [self.paper("10.1/b")]
        self.assertFalse(self.resolve({}, verify_online=True, consensus_client=client)[0])

    def test_exact_alias_resolves_to_same_identity(self):
        paper = self.paper("10.1/a", key="Smith et al. 2025")
        paper["citation_aliases"] = ["Smith et al. 2024"]
        self.assertTrue(self.resolve({paper["id"]: paper})[0])

    def test_duplicate_exact_keys_reject_instead_of_first_match(self):
        papers = {"doi:10.1/a": self.paper("10.1/a"), "doi:10.1/b": self.paper("10.1/b")}
        self.assertFalse(self.resolve(papers)[0])

    def test_canonical_alias_collision_is_ambiguous(self):
        other = self.paper("10.1/b", "Smith et al. 2025")
        other["citation_aliases"] = ["Smith et al. 2024"]
        self.assertFalse(self.resolve({"doi:10.1/a": self.paper("10.1/a"), "doi:10.1/b": other})[0])

    def test_surname_particles_are_not_dropped_in_fallback(self):
        paper = self.paper("10.1/a", "van Smith et al. 2024", ["van Smith, A."])
        self.assertFalse(self.resolve({"doi:10.1/a": paper})[0])

    def test_corporate_author_is_not_its_last_word(self):
        paper = self.paper("10.1/a", "ACSM 2024", ["American College of Sports Medicine"])
        self.assertFalse(self.resolve({"doi:10.1/a": paper}, citation="Medicine 2024")[0])

    def test_coauthor_is_not_a_first_author_match(self):
        papers = {"doi:10.1/a": self.paper("10.1/a", "Brown et al. 2024", ["Brown, A.", "Smith, J."])}
        self.assertFalse(self.resolve(papers)[0])

    def test_fallback_rejects_multiple_first_author_identities(self):
        papers = {"doi:10.1/a": self.paper("10.1/a", "Smith & Brown 2024"),
                  "doi:10.1/b": self.paper("10.1/b", "Smith & Jones 2024")}
        self.assertFalse(self.resolve(papers)[0])


class TestReviewedRefresh(unittest.TestCase):
    def refresh(self, existing, incoming, method):
        client = ConsensusClient(api_key="test", cache_path=None)
        client.cache = {"papers": {existing["id"]: copy.deepcopy(existing)}}
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"results": [incoming]}).encode()
        with patch("urllib.request.urlopen", return_value=response):
            result = getattr(client, method)(existing["doi"], refresh=True)
        return result[0] if method == "search" else result

    def test_aliases_survive_both_refresh_paths_without_review_markers(self):
        existing = {"id": "doi:10.1/a", "doi": "10.1/a", "citation_key": "Smith et al. 2025",
                    "citation_aliases": ["Smith et al. 2024"], "year": 2025,
                    "authors": ["Smith, A.", "Brown, B."]}
        incoming = {"doi": "10.1/a", "year": 2025, "authors": existing["authors"]}
        for method in ("search", "get_paper"):
            with self.subTest(method=method):
                paper = self.refresh(existing, incoming, method)
                self.assertEqual(paper.get("citation_aliases"), existing["citation_aliases"])

    def test_reviewed_interpretation_survives_without_provenance_markers(self):
        existing = {"id": "doi:10.1/a", "doi": "10.1/a", "citation_key": "Smith et al. 2025",
                    "reviewed_interpretation": "Limited applicability", "raw_export": {"Year": "2024"}}
        for method in ("search", "get_paper"):
            with self.subTest(method=method):
                paper = self.refresh(existing, {"doi": "10.1/a", "year": 2024}, method)
                self.assertEqual(paper.get("reviewed_interpretation"), existing["reviewed_interpretation"])
                self.assertEqual(paper.get("raw_export"), existing["raw_export"])

    def test_refresh_accepts_unprotected_live_metadata_on_reviewed_paper(self):
        existing = {"id": "doi:10.1/a", "doi": "10.1/a", "citation_key": "Smith et al. 2025",
                    "year": 2025, "authors": ["Smith, A.", "Brown, B."], "takeaway": "Reviewed finding",
                    "review_provenance": {"review_id": "test"}, "consensus_meter": {}, "consensus_url": "old",
                    "citation_count": 9}
        incoming = {"doi": "10.1/a", "year": 2024, "authors": ["Wrong, B."], "takeaway": "API finding",
                    "consensus_meter": {"yes": 7}, "consensus_url": "https://consensus.app/current",
                    "citation_count": 101}
        for method in ("search", "get_paper"):
            with self.subTest(method=method):
                paper = self.refresh(existing, incoming, method)
                for field in ("consensus_meter", "consensus_url", "citation_count"):
                    self.assertEqual(paper.get(field), incoming[field])
                for field in ("citation_key", "year", "authors", "takeaway", "review_provenance"):
                    self.assertEqual(paper.get(field), existing[field])

    def test_normalization_and_both_refresh_paths_preserve_reviewed_fields(self):
        reviewed = {"id": "doi:10.1/a", "doi": "10.1/a", "citation_key": "Smith et al. 2025",
                    "citation_aliases": ["Smith et al. 2024"], "year": 2025,
                    "authors": ["Smith, J.", "Brown, A."], "takeaway": "Reviewed conclusion",
                    "reviewed_interpretation": "Limited applicability", "raw_export": {"Year": "2024"},
                    "review_provenance": {"review_id": "2026-11-02-consensus-review", "row": 1}}
        client = ConsensusClient(api_key="test", cache_path=None)
        normalized = client._standardize_paper(reviewed)
        for field in ("citation_aliases", "reviewed_interpretation", "raw_export", "review_provenance"):
            self.assertEqual(normalized.get(field), reviewed[field])
        for method in ("search", "get_paper"):
            client.cache = {"papers": {reviewed["id"]: copy.deepcopy(reviewed)}}
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps({"results": [{"doi": "10.1/a", "year": 2024,
                "title": "API title", "authors": ["Different, A."], "takeaway": "API takeaway"}]}).encode()
            with patch("urllib.request.urlopen", return_value=response):
                result = getattr(client, method)("10.1/a", refresh=True)
            paper = result[0] if method == "search" else result
            for field, value in reviewed.items():
                self.assertEqual(paper.get(field), value)


if __name__ == "__main__":
    unittest.main()
