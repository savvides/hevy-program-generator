#!/usr/bin/env python3
"""Unit tests for Consensus paper normalization and citation key derivation."""
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from consensus_client import _surname, derive_citation_key  # noqa: E402


class TestSurname(unittest.TestCase):
    def test_comma_form_takes_left_of_comma(self):
        self.assertEqual(_surname("Currier, B. S."), "Currier")
        self.assertEqual(_surname("Milanović, Z."), "Milanović")

    def test_given_name_form_takes_last_token(self):
        self.assertEqual(_surname("Sumiaki Maeo"), "Maeo")
        self.assertEqual(_surname("B. Macdonald"), "Macdonald")

    def test_middle_initial_is_not_a_surname(self):
        self.assertEqual(_surname("Gabriela M. Cadeo"), "Cadeo")
        self.assertEqual(_surname("Daniel L. Plotkin"), "Plotkin")
        self.assertEqual(_surname("Michael J. Williams"), "Williams")

    def test_lowercase_particle_is_part_of_surname(self):
        self.assertEqual(_surname("Bas van Hooren"), "van Hooren")

    def test_generational_suffix_is_part_of_surname(self):
        self.assertEqual(_surname("Walter Krause Neto"), "Krause Neto")

    def test_three_token_name_without_particle_takes_last(self):
        self.assertEqual(_surname("Adinda Zahrunnisa Hasibuan"), "Hasibuan")
        self.assertEqual(_surname("Danielle Lobato Araújo"), "Araújo")


class TestDeriveCitationKey(unittest.TestCase):
    def test_multiple_authors_use_et_al(self):
        self.assertEqual(
            derive_citation_key(["Sumiaki Maeo", "Meng Huang"], 2021),
            "Maeo et al. 2021",
        )

    def test_single_author_omits_et_al(self):
        self.assertEqual(derive_citation_key(["Moore, D. R."], 2014), "Moore 2014")

    def test_missing_year_falls_back_to_title(self):
        self.assertEqual(
            derive_citation_key(["Sumiaki Maeo"], None, title="Some Paper Title"),
            "Some Paper Title",
        )

    def test_missing_authors_with_year_uses_unknown(self):
        self.assertEqual(derive_citation_key([], 2020), "Unknown et al. 2020")


class TestPaperIdCanonicalization(unittest.TestCase):
    def setUp(self):
        from consensus_client import ConsensusClient
        self.client = ConsensusClient(cache_path=None)

    def test_uppercase_doi_yields_lowercase_id(self):
        paper = self.client._standardize_paper(
            {"doi": "10.1249/MSS.0000000000002523", "title": "T", "authors": ["A B"]}
        )
        self.assertEqual(paper["id"], "doi:10.1249/mss.0000000000002523")

    def test_preexisting_id_does_not_bypass_canonicalization(self):
        """A raw row carrying its own uppercase 'doi:' id must still be lowercased."""
        paper = self.client._standardize_paper(
            {
                "id": "doi:10.1249/MSS.0000000000002523",
                "doi": "10.1249/MSS.0000000000002523",
                "title": "T",
                "authors": ["A B"],
            }
        )
        self.assertEqual(paper["id"], "doi:10.1249/mss.0000000000002523")
        self.assertEqual(paper["id"], f"doi:{paper['doi'].lower()}")

    def test_row_without_a_doi_keeps_its_existing_id(self):
        paper = self.client._standardize_paper(
            {"id": "some-legacy-id", "title": "T", "authors": ["A B"]}
        )
        self.assertEqual(paper["id"], "some-legacy-id")

    def test_mixed_case_dois_collapse_to_one_id(self):
        upper = self.client._standardize_paper({"doi": "10.1249/MSS.123", "title": "T"})
        lower = self.client._standardize_paper({"doi": "10.1249/mss.123", "title": "T"})
        self.assertEqual(upper["id"], lower["id"])


class TestLiveApiShapeFixture(unittest.TestCase):
    """Pins the live Consensus API response shape.

    If Consensus renames a field, this fails at authoring time instead of
    silently writing degraded rows into data/consensus_cache.json.
    """

    FIXTURE = (
        SCRIPTS_DIR.parent / "data" / "fixtures" / "consensus_search_item.json"
    )

    def setUp(self):
        import json
        from consensus_client import ConsensusClient
        with open(self.FIXTURE, "r", encoding="utf-8") as f:
            self.raw = json.load(f)
        self.paper = ConsensusClient(cache_path=None)._standardize_paper(self.raw)

    def test_year_resolves_from_publish_year(self):
        self.assertEqual(self.paper["year"], 2021)

    def test_journal_resolves_from_journal_name(self):
        self.assertEqual(
            self.paper["journal"], "Medicine and Science in Sports and Exercise"
        )

    def test_citation_key_is_surname_form(self):
        self.assertEqual(self.paper["citation_key"], "Maeo et al. 2021")

    def test_id_is_lowercase_doi(self):
        self.assertEqual(self.paper["id"], "doi:10.1249/mss.0000000000002523")

    def test_citation_key_parses_as_a_valid_citation(self):
        from eval_evidence_grounding import parse_citation
        self.assertIsNotNone(parse_citation(self.paper["citation_key"]))

    def test_takeaway_is_populated(self):
        self.assertTrue(self.paper["takeaway"].strip())


class TestRepairIsSelective(unittest.TestCase):
    """The repair must not touch rows whose keys are already valid."""

    def test_explicit_reviewed_identity_is_not_derived_from_corporate_last_word(self):
        from repair_consensus_cache import repair_papers
        for marker in ("review_provenance", "bibliographic_verification", "reviewed_interpretation", "raw_export"):
            with self.subTest(marker=marker):
                paper = {"id": "doi:10.1/acsm", "doi": "10.1/acsm", "year": 2009,
                         "authors": ["American College of Sports Medicine"], "citation_key": "ACSM 2009",
                         "citation_aliases": ["ACSM 2009"], marker: {}}
                repaired, changed = repair_papers({paper["id"]: paper})
                self.assertEqual(repaired[paper["id"]], paper)
                self.assertEqual(changed, 0)

    def test_curated_ampersand_key_is_preserved(self):
        from repair_consensus_cache import repair_papers
        papers = {
            "doi:10.1007/s40279-013-0029-x": {
                "id": "doi:10.1007/s40279-013-0029-x",
                "title": "High-intensity interval training",
                "authors": ["Buchheit, M.", "Laursen, P. B."],
                "year": 2013, "journal": "", "doi": "10.1007/s40279-013-0029-x",
                "consensus_url": "", "takeaway": "", "consensus_meter": {},
                "citation_key": "Buchheit & Laursen 2013",
            }
        }
        repaired, changed = repair_papers(papers)
        self.assertEqual(
            repaired["doi:10.1007/s40279-013-0029-x"]["citation_key"],
            "Buchheit & Laursen 2013",
        )
        self.assertEqual(changed, 0)

    def test_title_key_is_regenerated(self):
        from repair_consensus_cache import repair_papers
        papers = {
            "doi:10.1249/mss.123": {
                "id": "doi:10.1249/mss.123",
                "title": "Muscle forces during three hamstring exercises",
                "authors": ["Bas van Hooren", "A. Other"],
                "year": 2020, "journal": "", "doi": "10.1249/mss.123",
                "consensus_url": "", "takeaway": "", "consensus_meter": {},
                "citation_key": "Muscle forces during three hamstring exercises",
            }
        }
        repaired, changed = repair_papers(papers)
        self.assertEqual(
            repaired["doi:10.1249/mss.123"]["citation_key"], "van Hooren et al. 2020"
        )
        self.assertEqual(changed, 1)

    def test_full_name_key_is_regenerated_even_when_regex_passes(self):
        """A three-word given+surname key satisfies the widened regex but is still wrong."""
        from repair_consensus_cache import repair_papers
        papers = {
            "doi:10.1/x": {
                "id": "doi:10.1/x", "doi": "10.1/x", "title": "T",
                "authors": ["Matheus Barbalho", "A. Other"], "year": 2020,
                "journal": "", "consensus_url": "", "takeaway": "",
                "consensus_meter": {}, "citation_key": "Matheus Barbalho et al. 2020",
            }
        }
        repaired, changed = repair_papers(papers)
        self.assertEqual(repaired["doi:10.1/x"]["citation_key"], "Barbalho et al. 2020")
        self.assertEqual(changed, 1)

    def test_curated_two_author_ampersand_form_survives_regeneration(self):
        """'Buchheit & Laursen 2013' is hand-curated and must not become 'et al.'."""
        from repair_consensus_cache import repair_papers
        papers = {
            "doi:10.1/y": {
                "id": "doi:10.1/y", "doi": "10.1/y", "title": "T",
                "authors": ["Schoenfeld, B. J.", "Aragon, A. A."], "year": 2018,
                "journal": "", "consensus_url": "", "takeaway": "",
                "consensus_meter": {}, "citation_key": "Schoenfeld & Aragon 2018",
            }
        }
        repaired, changed = repair_papers(papers)
        self.assertEqual(
            repaired["doi:10.1/y"]["citation_key"], "Schoenfeld & Aragon 2018"
        )
        self.assertEqual(changed, 0)

    def test_preprint_duplicate_is_dropped_for_published_version(self):
        """A bioRxiv preprint and its published version are one paper."""
        from repair_consensus_cache import drop_preprint_duplicates
        papers = {
            "doi:10.3389/x": {
                "id": "doi:10.3389/x", "doi": "10.3389/x",
                "title": "Hip thrust and back squat training",
                "authors": ["Daniel L. Plotkin"], "year": 2023,
                "journal": "Frontiers in Physiology", "consensus_url": "",
                "takeaway": "", "consensus_meter": {}, "citation_key": "Plotkin 2023",
            },
            "doi:10.1101/y": {
                "id": "doi:10.1101/y", "doi": "10.1101/y",
                "title": "Hip thrust and back squat training",
                "authors": ["Daniel L Plotkin"], "year": 2023,
                "journal": "bioRxiv", "consensus_url": "",
                "takeaway": "", "consensus_meter": {}, "citation_key": "Plotkin 2023",
            },
        }
        kept, remap = drop_preprint_duplicates(papers)
        self.assertEqual(list(kept), ["doi:10.3389/x"])
        self.assertEqual(remap, {"doi:10.1101/y": "doi:10.3389/x"})

    def test_distinct_titles_are_never_dropped(self):
        from repair_consensus_cache import drop_preprint_duplicates
        papers = {
            "doi:a": {"id": "doi:a", "title": "Paper One", "journal": "J", "year": 2020},
            "doi:b": {"id": "doi:b", "title": "Paper Two", "journal": "J", "year": 2020},
        }
        kept, remap = drop_preprint_duplicates(papers)
        self.assertEqual(len(kept), 2)
        self.assertEqual(remap, {})

    def test_unrepairable_row_is_dropped(self):
        """A row with no DOI and no year can never satisfy the schema guard."""
        from repair_consensus_cache import drop_unrepairable
        papers = {
            "eccentric and concentric motion of hamstring": {
                "id": "eccentric and concentric motion of hamstring", "doi": "",
                "title": "Eccentric and concentric motion of hamstring",
                "authors": [], "year": None, "journal": "", "consensus_url": "",
                "takeaway": "", "consensus_meter": {},
                "citation_key": "Eccentric and concentric motion of hamstring",
            },
            "doi:10.1/ok": {
                "id": "doi:10.1/ok", "doi": "10.1/ok", "title": "Fine",
                "authors": ["A B"], "year": 2020, "journal": "J",
                "consensus_url": "", "takeaway": "", "consensus_meter": {},
                "citation_key": "B 2020",
            },
        }
        kept, dropped = drop_unrepairable(papers)
        self.assertEqual(list(kept), ["doi:10.1/ok"])
        self.assertEqual(dropped, ["eccentric and concentric motion of hamstring"])

    def test_row_with_a_doi_but_no_year_is_kept(self):
        """Those are refetchable, so dropping them would lose real data."""
        from repair_consensus_cache import drop_unrepairable
        papers = {
            "doi:10.1/x": {"id": "doi:10.1/x", "doi": "10.1/x", "title": "T",
                           "authors": ["A B"], "year": None, "citation_key": "T"}
        }
        kept, dropped = drop_unrepairable(papers)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])

    def test_doi_fork_is_merged_preferring_richer_row(self):
        from repair_consensus_cache import merge_doi_forks
        papers = {
            "doi:10.1249/MSS.999": {
                "id": "doi:10.1249/MSS.999", "doi": "10.1249/MSS.999",
                "title": "T", "authors": ["Maeo, S."], "year": 2021,
                "journal": "MSSE", "consensus_url": "", "takeaway": "x",
                "consensus_meter": {"yes": 9}, "citation_key": "Maeo et al. 2021",
            },
            "doi:10.1249/mss.999": {
                "id": "doi:10.1249/mss.999", "doi": "10.1249/mss.999",
                "title": "T", "authors": ["Sumiaki Maeo"], "year": None,
                "journal": "", "consensus_url": "", "takeaway": "",
                "consensus_meter": {}, "citation_key": "T",
            },
        }
        merged = merge_doi_forks(papers)
        self.assertEqual(len(merged), 1)
        survivor = merged["doi:10.1249/mss.999"]
        self.assertEqual(survivor["consensus_meter"], {"yes": 9})
        self.assertEqual(survivor["year"], 2021)


class TestGetPaperRefresh(unittest.TestCase):
    """--refetch must bypass a cache hit, or repairing a bad row is a no-op."""

    def _fake_response(self, payload):
        import io
        import json
        from unittest import mock
        body = io.BytesIO(json.dumps(payload).encode("utf-8"))
        resp = mock.MagicMock()
        resp.read = body.read
        resp.__enter__ = lambda self_: resp
        resp.__exit__ = lambda *a: False
        return resp

    def test_refresh_bypasses_a_cache_hit(self):
        from unittest import mock
        from consensus_client import ConsensusClient
        client = ConsensusClient(api_key="ak_test", cache_path=None)
        client.cache = {
            "papers": {"doi:10.1/x": {"id": "doi:10.1/x", "doi": "10.1/x", "year": None}}
        }
        payload = {"results": [{"doi": "10.1/x", "publish_year": 2020, "title": "T",
                                "authors": ["Alice Bennett", "C. Other"]}]}
        with mock.patch("urllib.request.urlopen",
                        return_value=self._fake_response(payload)) as urlopen:
            paper = client.get_paper("10.1/x", refresh=True, use_cache=False)
        urlopen.assert_called_once()
        self.assertEqual(paper["year"], 2020)
        self.assertEqual(paper["citation_key"], "Bennett et al. 2020")

    def test_network_fetch_uses_the_search_endpoint(self):
        """/v1/papers/{doi} returns 404; the live API resolves a DOI via /v1/search."""
        from unittest import mock
        from consensus_client import ConsensusClient
        client = ConsensusClient(api_key="ak_test", cache_path=None)
        client.cache = {"papers": {}}
        payload = {"results": [
            {"doi": "10.1111/SMS.14158", "publish_year": 2022, "title": "T",
             "authors": ["Bas van Hooren", "C. Other"]},
            {"doi": "10.9999/other", "publish_year": 1999, "title": "Wrong paper"},
        ]}
        with mock.patch("urllib.request.urlopen",
                        return_value=self._fake_response(payload)) as urlopen:
            paper = client.get_paper("10.1111/sms.14158", refresh=True, use_cache=False)
        called_url = urlopen.call_args[0][0].full_url
        self.assertIn("/v1/search", called_url)
        self.assertEqual(paper["year"], 2022)
        self.assertEqual(paper["citation_key"], "van Hooren et al. 2022")

    def test_network_fetch_returns_none_when_doi_is_absent_from_results(self):
        from unittest import mock
        from consensus_client import ConsensusClient
        client = ConsensusClient(api_key="ak_test", cache_path=None)
        client.cache = {"papers": {}}
        payload = {"results": [{"doi": "10.9999/other", "publish_year": 1999,
                                "title": "Wrong paper"}]}
        import contextlib
        import io
        with mock.patch("urllib.request.urlopen",
                        return_value=self._fake_response(payload)), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            paper = client.get_paper("10.1111/sms.14158", refresh=True, use_cache=False)
        self.assertIsNone(paper)
        self.assertIn("no match", err.getvalue())

    def test_refetch_merges_into_curated_rows(self):
        """--refetch fills the year without wiping aliases, notes or verification."""
        import contextlib
        import io
        import json
        import os
        import tempfile
        from unittest import mock
        import repair_consensus_cache
        curated = {
            "id": "doi:10.1/a", "doi": "10.1/a", "title": "Curated", "authors": ["Alice Bennett", "C. Other"],
            "year": None, "takeaway": "t", "citation_key": "Bennett et al. 2020",
            "citation_aliases": ["Bennett & Other 2020"], "review_note": "Checked by hand.",
        }
        verified = {
            "id": "doi:10.1/b", "doi": "10.1/b", "title": "Verified", "authors": ["Dana Kerr", "E. Other"],
            "year": None, "takeaway": "t", "citation_key": "Kerr et al. 2019",
            "citation_aliases": ["Kerr & Other 2019"], "review_note": "Identity reviewed.",
            "bibliographic_verification": {"status": "verified"},
        }
        payload = {"results": [
            {"doi": "10.1/a", "publish_year": 2020, "title": "Curated", "authors": ["Alice Bennett", "C. Other"]},
            {"doi": "10.1/b", "publish_year": 2019, "title": "Verified", "authors": ["Dana Kerr", "E. Other"]},
        ]}
        with tempfile.TemporaryDirectory() as td:
            cache_path = Path(td) / "cache.json"
            cache_path.write_text(json.dumps({"version": "1.0.0", "queries": {},
                                              "papers": {"doi:10.1/a": curated, "doi:10.1/b": verified}}),
                                  encoding="utf-8")
            with mock.patch.object(repair_consensus_cache, "CACHE_PATH", cache_path), \
                    mock.patch.dict(os.environ, {"CONSENSUS_API_KEY": "ak_test"}), \
                    mock.patch("urllib.request.urlopen",
                               side_effect=lambda *a, **k: self._fake_response(payload)), \
                    mock.patch("time.sleep"), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(repair_consensus_cache.main(["--refetch"]), 0)
            papers = json.loads(cache_path.read_text(encoding="utf-8"))["papers"]
        row = papers["doi:10.1/a"]
        self.assertEqual(row["year"], 2020)
        self.assertEqual(row["citation_aliases"], ["Bennett & Other 2020"])
        self.assertEqual(row["review_note"], "Checked by hand.")
        # A row with a review marker keeps its reviewed identity, so it is left intact.
        self.assertEqual(papers["doi:10.1/b"], verified)

    def test_without_refresh_a_cache_hit_makes_no_network_call(self):
        from unittest import mock
        from consensus_client import ConsensusClient
        client = ConsensusClient(api_key="ak_test", cache_path=None)
        client.cache = {"papers": {"doi:10.1/x": {"id": "doi:10.1/x", "doi": "10.1/x"}}}
        with mock.patch("urllib.request.urlopen") as urlopen:
            client.get_paper("10.1/x")
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
