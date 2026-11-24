#!/usr/bin/env python3
"""Zero-dependency Consensus API annual literature update and authority manager.

Commands:
  --refresh-existing  Refetch live metadata for all approved DOIs in evidence_authority.json.
  --discover          Run configured topic queries in evidence_authority.json to discover new papers.
  --render-index      Render markdown register (docs/research/<review_id>.md) from manifest and cache.
  --dry-run           Preview actions without modifying disk files.
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "evidence_authority.json"
CACHE_PATH = REPO_ROOT / "data" / "consensus_cache.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from consensus_client import ConsensusClient, derive_citation_key  # noqa: E402
from eval_evidence_grounding import CITATION_REGEX  # noqa: E402
from repair_consensus_cache import PREPRINT_SERVERS  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict, dry_run: bool = False) -> None:
    if dry_run:
        print(f"  [dry-run] Would write {path.name}")
        return
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)
    print(f"  Wrote {path}")


def refresh_approved_dois(
    client: ConsensusClient,
    manifest: dict,
    cache: dict,
    delay: float = 0.0,
    dry_run: bool = False,
    cache_path: Path = CACHE_PATH,
) -> int:
    """Refetch live metadata for all approved primary and supplemental DOIs."""
    papers = cache.get("papers", {})
    approved_dois = [entry["doi"].strip().lower() for entry in manifest.get("primary", [])]
    approved_dois.extend([entry["doi"].strip().lower() for entry in manifest.get("supplemental", [])])

    print(f"--- Refreshing {len(approved_dois)} approved DOIs via Consensus API ---")
    refreshed_count = 0

    for idx, doi in enumerate(approved_dois):
        if idx > 0 and delay > 0:
            time.sleep(delay)
        pid = f"doi:{doi}"
        existing = papers.get(pid)
        fresh = client.get_paper(doi, refresh=True, use_cache=False)
        if fresh and fresh.get("year"):
            # Ensure pid consistency
            fresh["id"] = pid
            fresh["doi"] = doi
            # Preserve existing review provenance and status if present
            if existing and "review_provenance" in existing:
                fresh["review_provenance"] = existing["review_provenance"]
            # Merge: curated fields the API never returns (review_note, journal_sjr_quartile) survive.
            papers[pid] = {**(existing or {}), **fresh}
            refreshed_count += 1
            print(f"  ✓ Refreshed {pid}: {fresh.get('citation_key')}")
        else:
            print(f"  ✗ Failed to fetch fresh metadata for {pid}; keeping existing cache")

    cache["papers"] = dict(sorted(papers.items()))
    save_json(cache_path, cache, dry_run=dry_run)
    return refreshed_count


def discover_new_papers(
    client: ConsensusClient,
    manifest: dict,
    cache: dict,
    min_year: int = 2025,
    limit_per_query: int = 5,
    delay: float = 0.0,
    dry_run: bool = False,
    cache_path: Path = CACHE_PATH,
    manifest_path: Path = MANIFEST_PATH,
) -> tuple[int, list[dict]]:
    """Execute configured annual topic queries and add qualifying new papers to primary."""
    queries = manifest.get("queries", [])
    primary_list = manifest.get("primary", [])
    existing_primary_dois = {e["doi"].strip().lower() for e in primary_list}
    existing_all_dois = {e["doi"].strip().lower() for e in primary_list}
    existing_all_dois.update(e["doi"].strip().lower() for e in manifest.get("supplemental", []))

    papers = cache.get("papers", {})
    existing_citation_keys = {
        " ".join(p.get("citation_key", "").casefold().split()): pid
        for pid, p in papers.items()
        if p.get("citation_key")
    }

    print(f"--- Running {len(queries)} annual topic queries (min_year={min_year}) ---")
    new_primary_entries: list[dict] = []

    for idx, q in enumerate(queries):
        if idx > 0 and delay > 0:
            time.sleep(delay)
        print(f"Query: '{q}'")
        results = client.search(q, limit=limit_per_query, refresh=True, use_cache=False)
        for p in results:
            doi = (p.get("doi") or "").strip().lower()
            if not doi.startswith("10."):
                continue
            if doi in existing_all_dois:
                continue

            # Invariant checks
            year = p.get("year")
            if not isinstance(year, int) or year < min_year:
                continue

            authors = p.get("authors")
            if not isinstance(authors, list) or len(authors) == 0:
                continue

            title = p.get("title")
            if not isinstance(title, str) or not title.strip():
                continue

            takeaway = (p.get("takeaway") or p.get("abstract") or title).strip()
            if not takeaway:
                continue
            p["takeaway"] = takeaway

            journal = (p.get("journal") or "").strip().lower()
            if journal in PREPRINT_SERVERS:
                continue

            cit_key = p.get("citation_key", "")
            if not cit_key or not CITATION_REGEX.match(cit_key):
                cit_key = derive_citation_key(authors, year, title)

            if not CITATION_REGEX.match(cit_key):
                print(f"  Skipping {doi}: citation key '{cit_key}' does not match canonical format")
                continue

            norm_key = " ".join(cit_key.casefold().split())
            if norm_key in existing_citation_keys and existing_citation_keys[norm_key] != f"doi:{doi}":
                # Key collision: try disambiguation with suffix
                disambiguated = False
                for suffix in ("b", "c", "d"):
                    cand_key = f"{cit_key}{suffix}"
                    cand_norm = " ".join(cand_key.casefold().split())
                    if cand_norm not in existing_citation_keys:
                        cit_key = cand_key
                        p["citation_key"] = cand_key
                        disambiguated = True
                        break
                if not disambiguated:
                    print(f"  Skipping {doi}: citation key '{cit_key}' collides and could not be disambiguated")
                    continue

            # Standardize entry for primary corpus
            pid = f"doi:{doi}"
            p["id"] = pid
            p["doi"] = doi
            p["review_provenance"] = {
                "review_id": manifest.get("review_id", "consensus-review"),
                "source": "api_query",
                "query": q,
            }

            papers[pid] = p
            existing_citation_keys[" ".join(cit_key.casefold().split())] = pid
            existing_all_dois.add(doi)
            existing_primary_dois.add(doi)

            entry = {
                "doi": doi,
                "topic": p.get("title", ""),
                "policy_use": "Indexed only; no new policy from this unappraised record.",
                "verification_depth": "M; Consensus API discovery metadata/abstract only; no claim-level appraisal",
            }
            primary_list.append(entry)
            new_primary_entries.append(entry)
            print(f"  + Discovered new primary paper: {cit_key} (DOI: {doi})")

    manifest["primary"] = primary_list
    cache["papers"] = dict(sorted(papers.items()))

    save_json(cache_path, cache, dry_run=dry_run)
    save_json(manifest_path, manifest, dry_run=dry_run)
    return len(new_primary_entries), new_primary_entries


def render_review_markdown(
    manifest: dict,
    cache: dict,
    output_path: Path,
    dry_run: bool = False,
) -> str:
    """Generate deterministic markdown register from manifest and cache."""
    review_id = manifest.get("review_id", "annual-consensus-review")
    review_date = manifest.get("review_date", str(datetime.date.today()))
    primary_list = manifest.get("primary", [])
    papers = cache.get("papers", {})

    lines = [
        f"# Consensus Literature Review Index ({review_id})",
        "",
        f"Review ID: `{review_id}`. Date: `{review_date}`.",
        f"The primary research corpus contains **{len(primary_list)} records**.",
        "The [authority manifest](../../data/evidence_authority.json) owns membership.",
        "The [exercise](../evidence_base.md) and [nutrition](../nutrition_evidence_base.md) documents carry qualified interpretations.",
        "",
        "## Reading the register",
        "",
        "- **M — metadata only:** DOI identity checked; topic/population from API export or abstract. No original-content claim appraisal.",
        "- **A — original abstract:** original journal/PubMed abstract checked; interpretation remains limited to that depth.",
        "- **S — selected full-text sections:** relevant original methods, results, or discussion inspected.",
        "- **U — original content unresolved:** metadata checked, substantive source inaccessible.",
        "",
        "| Row | Citation and source links | Topic / study population | Policy use or limit | Verification depth |",
        "| --- | --- | --- | --- | --- |",
    ]

    for idx, entry in enumerate(primary_list, 1):
        doi = entry.get("doi", "")
        pid = f"doi:{doi}"
        paper = papers.get(pid, {})
        citation_key = paper.get("citation_key") or entry.get("doi")
        aliases = paper.get("citation_aliases", [])
        alias_str = f"; aliases: {', '.join(aliases)}" if aliases else ""
        url = paper.get("consensus_url") or f"https://doi.org/{doi}"
        citation_col = f"{citation_key}{alias_str}. [DOI {doi}](https://doi.org/{doi}); [Consensus]({url})"
        topic = entry.get("topic", paper.get("title", "")).replace("|", "\\|")
        policy = entry.get("policy_use", "").replace("|", "\\|")
        depth = entry.get("verification_depth", "M").replace("|", "\\|")
        lines.append(f"| {idx} | {citation_col} | {topic} | {policy} | {depth} |")

    lines.append("")
    lines.append("## Explicit supplemental exercise sources")
    lines.append("")
    lines.append("| DOI | Purpose and limited scope |")
    lines.append("| --- | --- |")
    for supp in manifest.get("supplemental", []):
        doi = supp.get("doi", "")
        purpose = supp.get("purpose", "").replace("|", "\\|")
        lines.append(f"| [{doi}](https://doi.org/{doi}) | {purpose} |")
    lines.append("")

    content = "\n".join(lines)
    if dry_run:
        print(f"  [dry-run] Would write {output_path}")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"  Wrote {output_path}")
    return content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Run annual discovery and render-index in sequence")
    parser.add_argument("--refresh-existing", action="store_true", help="Refresh existing approved DOIs via Consensus API")
    parser.add_argument("--discover", action="store_true", help="Run annual queries to discover new papers")
    parser.add_argument("--render-index", action="store_true", help="Render markdown review register")
    parser.add_argument("--min-year", type=int, default=2025, help="Minimum year for newly discovered papers (default: 2025)")
    parser.add_argument("--limit", type=int, default=5, help="Results limit per discovery query (default: 5)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between API requests (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without disk writes")
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH, help="Path to evidence_authority.json")
    parser.add_argument("--cache-path", type=Path, default=CACHE_PATH, help="Path to consensus_cache.json")

    args = parser.parse_args(argv)

    if args.all:
        args.discover = True
        args.render_index = True

    if not (args.refresh_existing or args.discover or args.render_index):
        parser.print_help(file=sys.stderr)
        return 1

    manifest = load_json(args.manifest_path)
    cache = load_json(args.cache_path)
    client = ConsensusClient(cache_path=args.cache_path)
    # Keep the loaded cache (it protects reviewed fields) but never let the client
    # write it: save_json, which honours --dry-run, is the only writer.
    client.cache_path = None

    if args.refresh_existing:
        refresh_approved_dois(client, manifest, cache, delay=args.delay, dry_run=args.dry_run,
                              cache_path=args.cache_path)

    if args.discover:
        discover_new_papers(
            client,
            manifest,
            cache,
            min_year=args.min_year,
            limit_per_query=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
            cache_path=args.cache_path,
            manifest_path=args.manifest_path,
        )

    if args.render_index:
        review_id = manifest.get("review_id", "consensus-review")
        out_path = REPO_ROOT / "docs" / "research" / f"{review_id}.md"
        render_review_markdown(manifest, cache, out_path, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
