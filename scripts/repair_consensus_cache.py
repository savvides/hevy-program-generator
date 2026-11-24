#!/usr/bin/env python3
"""Repair degraded rows in data/consensus_cache.json.

Offline repair only: regenerates citation keys that fail the canonical format,
merges DOI-case forks, and reports duplicates. Rows missing a year cannot be
repaired offline (the raw API response is not stored) and are reported for
refetch. Idempotent: running twice produces a byte-identical file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
CACHE_PATH = REPO_ROOT / "data" / "consensus_cache.json"

sys.path.insert(0, str(SCRIPTS_DIR))
from consensus_client import ConsensusClient, _surname, derive_citation_key  # noqa: E402
from eval_evidence_grounding import CITATION_REGEX  # noqa: E402

RICHNESS_FIELDS = ("year", "journal", "takeaway", "consensus_meter", "consensus_url")
PREPRINT_SERVERS = ("biorxiv", "medrxiv", "arxiv", "preprints.org", "ssrn")


def _richness(paper: dict) -> int:
    """Count populated fields, to pick the survivor when merging forks."""
    return sum(1 for key in RICHNESS_FIELDS if paper.get(key))


def merge_doi_forks(papers: dict) -> dict:
    """Collapse ids that differ only by DOI case, keeping the richest row."""
    by_canonical: dict[str, dict] = {}
    for pid, paper in papers.items():
        canonical = pid.lower()
        existing = by_canonical.get(canonical)
        if existing is None:
            winner, loser = dict(paper), None
        elif _richness(paper) > _richness(existing):
            winner, loser = dict(paper), existing
        else:
            winner, loser = existing, paper
        if loser is not None:
            for key, value in loser.items():
                if value and not winner.get(key):
                    winner[key] = value
        winner["id"] = canonical
        if winner.get("doi"):
            winner["doi"] = winner["doi"].lower()
        by_canonical[canonical] = winner
    return by_canonical


def _is_preprint(paper: dict) -> bool:
    return (paper.get("journal") or "").strip().lower() in PREPRINT_SERVERS


def drop_preprint_duplicates(papers: dict) -> tuple[dict, dict]:
    """Drop preprints that also exist as a published paper under the same title.

    Consensus indexes the bioRxiv preprint and the journal version separately,
    under different DOIs, so the same study appears twice and produces two
    identical citation keys. Returns the surviving rows and a mapping from each
    dropped id to the id that replaces it, so query paper_ids can be rewritten.
    """
    by_title: dict[str, list[str]] = {}
    for pid, paper in papers.items():
        by_title.setdefault((paper.get("title") or "").strip().lower(), []).append(pid)

    remap: dict[str, str] = {}
    for pids in by_title.values():
        if len(pids) < 2:
            continue
        published = [pid for pid in pids if not _is_preprint(papers[pid])]
        if not published:
            continue
        survivor = max(published, key=lambda pid: _richness(papers[pid]))
        for pid in pids:
            if pid != survivor and _is_preprint(papers[pid]):
                remap[pid] = survivor
    kept = {pid: paper for pid, paper in papers.items() if pid not in remap}
    return kept, remap


def drop_unrepairable(papers: dict) -> tuple[dict, list[str]]:
    """Drop rows that can never satisfy the schema guard.

    A row with neither a DOI nor a year cannot be refetched (there is no id the
    API can resolve) and cannot have a citation key derived, so it would block
    the guard permanently. Rows with a DOI are refetchable and always kept.
    """
    dropped = [
        pid
        for pid, paper in papers.items()
        if not paper.get("doi") and paper.get("year") is None
    ]
    kept = {pid: paper for pid, paper in papers.items() if pid not in dropped}
    return kept, sorted(dropped)


def _is_degraded(key: str, authors: list[str]) -> bool:
    """True when a citation key needs regenerating.

    Two ways a key can be wrong. It can fail the canonical format outright
    (a raw paper title), or it can satisfy the format while still carrying the
    author's given name ("Matheus Barbalho et al. 2020"), which the widened
    surname regex accepts. Hand-curated two-author forms
    ("Buchheit & Laursen 2013") are legitimate and always preserved.
    """
    match = CITATION_REGEX.match(key)
    if not match:
        return True
    author_part = match.group(1)
    if " & " in author_part or " and " in author_part.lower():
        return False
    if not authors:
        return False
    stated = author_part.replace(" et al.", "").replace(" et al", "").strip()
    return stated != _surname(authors[0])


def repair_papers(papers: dict) -> tuple[dict, int]:
    """Repair unreviewed keys; reviewed identities require a deliberate review update."""
    repaired = {}
    changed = 0
    for pid, paper in papers.items():
        paper = dict(paper)
        key = paper.get("citation_key", "")
        reviewed = any(field in paper for field in
                       ("review_provenance", "bibliographic_verification", "reviewed_interpretation", "raw_export"))
        # The surname heuristic cannot infer every reviewed identity, such as ACSM
        # as a corporate author. Preserve its canonical key and review fields intact.
        if not reviewed and _is_degraded(key, paper.get("authors", [])):
            new_key = derive_citation_key(
                paper.get("authors", []), paper.get("year"), paper.get("title", "")
            )
            if new_key != key:
                paper["citation_key"] = new_key
                changed += 1
        repaired[pid] = paper
    return repaired, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair the Consensus cache.")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="Re-fetch rows with a null year from the live API (spends API quota)",
    )
    args = parser.parse_args(argv)

    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)

    before = len(cache["papers"])
    merged = merge_doi_forks(cache["papers"])
    deduped, preprint_remap = drop_preprint_duplicates(merged)
    deduped, unrepairable = drop_unrepairable(deduped)
    papers, changed = repair_papers(deduped)

    id_remap = {pid: pid.lower() for pid in cache["papers"] if pid != pid.lower()}
    id_remap.update(preprint_remap)
    for pid in unrepairable:
        id_remap[pid] = None
    for query in cache.get("queries", {}).values():
        query["paper_ids"] = sorted(
            {
                mapped
                for mapped in (id_remap.get(pid, pid) for pid in query.get("paper_ids", []))
                if mapped is not None
            }
        )

    keys: dict[str, list[str]] = {}
    for pid, paper in papers.items():
        keys.setdefault(paper.get("citation_key", ""), []).append(pid)
    duplicates = {k: v for k, v in keys.items() if len(v) > 1}
    missing_year = sorted(pid for pid, p in papers.items() if p.get("year") is None)

    print(f"  papers: {before} -> {len(papers)}")
    print(f"  preprint duplicates dropped: {len(preprint_remap)}")
    print(f"  unrepairable rows dropped (no DOI, no year): {len(unrepairable)}")
    for pid in unrepairable:
        print(f"    {pid}")
    print(f"  citation keys regenerated: {changed}")
    print(f"  duplicate citation keys: {len(duplicates)}")
    for key, pids in sorted(duplicates.items()):
        print(f"    {key!r}: {pids}")
    if args.refetch and missing_year:
        client = ConsensusClient(cache_path=None)
        client.cache = {"papers": papers}  # so the client protects reviewed fields
        for pid in missing_year:
            doi = papers[pid].get("doi")
            if not doi:
                print(f"    SKIP {pid}: no DOI, cannot refetch by id")
                continue
            fresh = client.get_paper(doi, refresh=True, use_cache=False)
            if fresh and fresh.get("year"):
                papers[pid] = {**papers[pid], **fresh}
                print(f"    refetched {pid} -> year {fresh['year']}")
            else:
                print(f"    FAILED  {pid}: no year returned")
        missing_year = sorted(pid for pid, p in papers.items() if p.get("year") is None)

    print(f"  rows needing a network refetch (year is null): {len(missing_year)}")
    for pid in missing_year:
        print(f"    {pid}")

    if args.dry_run:
        print("  --dry-run: no write performed")
        return 0

    cache["papers"] = dict(sorted(papers.items()))
    tmp = CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(CACHE_PATH)
    print(f"  wrote {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
