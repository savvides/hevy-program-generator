#!/usr/bin/env python3
"""Zero-dependency Consensus Academic API client with cache-first persistence."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_PATH = REPO_ROOT / "data" / "consensus_cache.json"

STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "for",
    "from", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "vs", "versus", "with",
}


SURNAME_PARTICLES = {
    "van", "von", "de", "da", "del", "der", "di", "du", "le", "la", "dos", "das",
}
GENERATIONAL_SUFFIXES = {
    "neto", "filho", "junior", "júnior", "jr", "sr", "ii", "iii", "iv",
}
REVIEW_FIELDS = (
    "citation_aliases", "review_provenance", "raw_export", "reviewed_interpretation",
    "bibliographic_verification", "study_type", "citation_count", "journal_sjr_quartile", "abstract",
)
PROTECTED_REVIEW_FIELDS = (
    "citation_aliases", "review_provenance", "raw_export", "reviewed_interpretation",
    "bibliographic_verification",
)
REVIEWED_IDENTITY_FIELDS = ("title", "authors", "year", "journal", "citation_key", "takeaway")


def _surname(name: str) -> str:
    """Extract the citation surname from an author name.

    Handles both catalog shapes: 'Surname, I.' (seeded rows) and
    'Given Surname' (live Consensus API), plus lowercase particles
    ('van Hooren') and generational suffixes ('Krause Neto').
    """
    if "," in name:
        return name.split(",")[0].strip()
    tokens = name.split()
    if not tokens:
        return name.strip()
    start = len(tokens) - 1
    if start > 0 and tokens[start].lower().rstrip(".") in GENERATIONAL_SUFFIXES:
        start -= 1
    while start > 0 and tokens[start - 1].lower() in SURNAME_PARTICLES:
        start -= 1
    return " ".join(tokens[start:])


def derive_citation_key(authors: list[str], year: int | None, title: str = "") -> str:
    """Build the canonical 'Author et al. YYYY' citation key."""
    if authors and year:
        surname = _surname(authors[0])
        return f"{surname} et al. {year}" if len(authors) > 1 else f"{surname} {year}"
    if year:
        return f"Unknown et al. {year}"
    return title or "Unknown"


def _result_items(payload: object) -> list[dict]:
    """Pull the paper list out of a Consensus response envelope."""
    if not isinstance(payload, dict):
        return payload if isinstance(payload, list) else []
    items = payload.get("results") or payload.get("papers") or payload.get("data") or []
    return items if isinstance(items, list) else []


def load_dotenv(path: Path) -> None:
    """Load key-value pairs from .env into os.environ if not already set."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_query(query: str) -> str:
    """Normalize query for collision-free caching.

    Strips punctuation, lowercases, removes stop words, deduplicates, and sorts tokens.
    """
    cleaned = re.sub(r"[^\w\s]", " ", query.lower())
    tokens = cleaned.split()
    filtered = [t for t in tokens if t not in STOP_WORDS]
    if not filtered:
        filtered = tokens
    return " ".join(sorted(set(filtered)))


class ConsensusClient:
    """Client for querying Consensus Academic API with local cache persistence."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        auth_header: str | None = None,
        cache_path: Path | str | None = DEFAULT_CACHE_PATH,
        cache_only: bool = False,
    ):
        load_dotenv(REPO_ROOT / ".env")
        self.api_key = api_key or os.environ.get("CONSENSUS_API_KEY")
        self.base_url = (
            base_url
            or os.environ.get("CONSENSUS_BASE_URL")
            or "https://api.consensus.app"
        ).rstrip("/")
        self.auth_header = auth_header or os.environ.get("CONSENSUS_AUTH_HEADER", "x-api-key")
        self.cache_only = cache_only
        self.cache_path = Path(cache_path) if cache_path is not None else None

        if self.cache_path and self.cache_path.exists():
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        else:
            self.cache = {
                "version": "1.0.0",
                "updated_at": "",
                "queries": {},
                "papers": {},
            }

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "hevy-program-generator/1.0.0",
        }
        if self.api_key:
            if self.auth_header.lower() in ("bearer", "authorization"):
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers[self.auth_header] = self.api_key
        return headers

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        self.cache["updated_at"] = (
            datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.cache_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            # ensure_ascii=False matches repair_consensus_cache.py; the default
            # would re-escape every non-ASCII name and churn the whole file.
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
            f.write("\n")
        temp_file.replace(self.cache_path)

    def _find_in_cache(self, query: str) -> list[dict]:
        norm_q = normalize_query(query)
        queries = self.cache.get("queries", {})
        papers = self.cache.get("papers", {})

        # 1. Direct normalized key match
        if norm_q in queries:
            matched = [
                self.get_paper(pid, cache_only=True)
                for pid in queries[norm_q].get("paper_ids", [])
            ]
            valid = [p for p in matched if p is not None]
            if valid:
                return valid

        # 2. Match against existing query keys by normalizing them
        for cached_k, q_data in queries.items():
            if normalize_query(cached_k) == norm_q:
                matched = [
                    self.get_paper(pid, cache_only=True)
                    for pid in q_data.get("paper_ids", [])
                ]
                valid = [p for p in matched if p is not None]
                if valid:
                    return valid

        # 3. Token subset / overlap match against cached queries
        q_toks = set(norm_q.split())
        if q_toks:
            best_score = 0.0
            best_pids: list[str] = []
            for cached_k, q_data in queries.items():
                c_toks = set(normalize_query(cached_k).split())
                if not c_toks:
                    continue
                if q_toks.issubset(c_toks):
                    score = 2.0 + (len(q_toks) / len(c_toks))
                else:
                    inter = len(q_toks & c_toks)
                    if inter >= 2 or (len(q_toks) == 1 and inter == 1):
                        score = inter / len(q_toks | c_toks)
                    else:
                        score = 0.0
                if score > best_score:
                    best_score = score
                    best_pids = q_data.get("paper_ids", [])
            if best_score >= 0.4 and best_pids:
                matched = [self.get_paper(pid, cache_only=True) for pid in best_pids]
                valid = [p for p in matched if p is not None]
                if valid:
                    return valid

        # 4. Fallback: Search directly across cached papers
        if q_toks:
            matched_papers = []
            for paper in papers.values():
                haystack = (
                    f"{paper.get('title', '')} "
                    f"{paper.get('takeaway', '')} "
                    f"{paper.get('citation_key', '')}"
                ).lower()
                if all(tok in haystack for tok in q_toks):
                    matched_papers.append(paper)
            if matched_papers:
                return matched_papers

        return []

    def _make_request(self, url: str, max_retries: int = 3) -> dict | None:
        """Execute HTTP GET with retry and exponential backoff on HTTP 429."""
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 2.0
                    print(
                        f"Consensus API rate limit (429) hit; sleeping {sleep_time}s before retry...",
                        file=sys.stderr,
                    )
                    time.sleep(sleep_time)
                    continue
                print(f"Consensus API HTTP error {e.code}: {e.reason}", file=sys.stderr)
                return None
            except Exception as e:
                print(f"Consensus API request failed: {e}", file=sys.stderr)
                return None
        return None

    def search(
        self,
        query: str,
        limit: int = 5,
        use_cache: bool = True,
        refresh: bool = False,
    ) -> list[dict]:
        """Search literature by query with cache-first persistence."""
        norm_q = normalize_query(query)

        if use_cache and not refresh:
            cached = self._find_in_cache(query)
            if cached:
                return cached[:limit]

        if self.cache_only or not self.api_key:
            return []

        # Outbound HTTP request
        params = urllib.parse.urlencode({"query": query, "limit": limit})
        url = f"{self.base_url}/v1/search?{params}"
        payload = self._make_request(url)
        if not payload:
            return []

        raw_items = _result_items(payload)

        results: list[dict] = []
        retrieved_ids: list[str] = []
        cached_papers = self.cache.setdefault("papers", {})
        existing_keys = {
            " ".join(p.get("citation_key", "").casefold().split()): p_id
            for p_id, p in cached_papers.items()
            if p.get("citation_key")
        }

        for item in raw_items:
            paper = self._standardize_paper(item)
            pid = paper["id"]
            doi = (paper.get("doi") or "").strip().lower()

            # Invariant: only persist papers with a canonical DOI into cache
            if doi.startswith("10.") and pid == f"doi:{doi}":
                cit_key = paper.get("citation_key", "")
                norm_key = " ".join(cit_key.casefold().split()) if cit_key else ""
                if norm_key and norm_key in existing_keys and existing_keys[norm_key] != pid:
                    # Disambiguate collision before saving
                    for suffix in ("b", "c", "d"):
                        cand = f"{cit_key}{suffix}"
                        if " ".join(cand.casefold().split()) not in existing_keys:
                            paper["citation_key"] = cand
                            existing_keys[" ".join(cand.casefold().split())] = pid
                            break
                    else:
                        # Suffixes exhausted: return the row but never persist a duplicate key.
                        results.append(paper)
                        continue
                elif norm_key:
                    existing_keys[norm_key] = pid

                cached_papers[pid] = paper
                retrieved_ids.append(pid)

            results.append(paper)

        now_iso = (
            datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        self.cache.setdefault("queries", {})[norm_q] = {
            "retrieved_at": now_iso,
            "paper_ids": retrieved_ids,
        }
        self._save_cache()
        return results[:limit]

    def get_paper(
        self,
        doi_or_id: str,
        use_cache: bool = True,
        cache_only: bool = False,
        refresh: bool = False,
    ) -> dict | None:
        """Retrieve a paper by DOI, paper ID, or citation key.

        The cache is searched by all three. A live fetch resolves by DOI only:
        /v1/search returns papers keyed by DOI, so a cache miss on a paper ID or
        citation key returns None rather than a wrong paper.
        """
        target = doi_or_id.strip()
        papers = self.cache.get("papers", {})

        if use_cache and not refresh:
            # Direct ID match
            if target in papers:
                return papers[target]

            # Match with doi: prefix
            doi_key = f"doi:{target}" if not target.lower().startswith("doi:") else target
            if doi_key in papers:
                return papers[doi_key]

            # Case-insensitive DOI match
            target_doi = target.lower().removeprefix("doi:")
            for pid, p in papers.items():
                p_doi = (p.get("doi") or pid).lower().removeprefix("doi:")
                if p_doi == target_doi:
                    return p

            # Match citation key
            target_lower = target.lower()
            matches = [p for p in papers.values()
                       if target_lower in [key.lower() for key in
                                           [p.get("citation_key", ""), *p.get("citation_aliases", [])]]]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return None

        if cache_only or self.cache_only or not self.api_key:
            return None

        # Resolve via the search endpoint: /v1/papers/{id} returns 404.
        params = urllib.parse.urlencode({"query": target, "limit": 10})
        url = f"{self.base_url}/v1/search?{params}"
        payload = self._make_request(url)
        if not payload:
            print(f"Consensus API lookup failed for {target}", file=sys.stderr)
            return None

        wanted = target.lower().removeprefix("doi:")
        match = next(
            (r for r in _result_items(payload)
             if (r.get("doi") or "").lower() == wanted),
            None,
        )
        if match is None:
            print(f"Consensus API returned no match for {target}", file=sys.stderr)
            return None

        paper = self._standardize_paper(match)
        if use_cache:
            self.cache.setdefault("papers", {})[paper["id"]] = paper
            self._save_cache()
        return paper

    def get_paper_by_doi(
        self,
        doi: str,
        use_cache: bool = True,
        cache_only: bool = False,
    ) -> dict | None:
        """Alias for get_paper."""
        return self.get_paper(doi, use_cache=use_cache, cache_only=cache_only)

    def _standardize_paper(self, raw: dict) -> dict:
        doi = (raw.get("doi") or "").lower()
        # A DOI always wins: a raw row may carry its own uppercase "doi:" id, and
        # deferring to it would leave id and doi disagreeing about case.
        if doi:
            paper_id = f"doi:{doi}"
        else:
            paper_id = raw.get("id") or raw.get("title", "unknown_paper")

        authors = raw.get("authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";")]

        year = raw.get("year") or raw.get("publish_year")
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None

        citation_key = raw.get("citation_key") or derive_citation_key(
            authors, year, raw.get("title", "")
        )

        takeaway = (
            raw.get("takeaway")
            or raw.get("summary")
            or raw.get("abstract")
            or ""
        )

        paper = {
            "id": paper_id,
            "title": raw.get("title", ""),
            "authors": authors,
            "year": year,
            "journal": raw.get("journal") or raw.get("journal_name", ""),
            "doi": doi,
            "consensus_url": raw.get("consensus_url") or raw.get("url", ""),
            "takeaway": takeaway,
            "consensus_meter": raw.get("consensus_meter", {}),
            "citation_key": citation_key,
        }
        for field in REVIEW_FIELDS:
            if field in raw:
                paper[field] = raw[field]
        existing = self.cache.get("papers", {}).get(paper_id, {})
        protected: tuple[str, ...] = PROTECTED_REVIEW_FIELDS
        if any(field in existing for field in
               ("review_provenance", "bibliographic_verification", "reviewed_interpretation", "raw_export")):
            protected += REVIEWED_IDENTITY_FIELDS
        # Preserve optional review fields even without provenance markers. Only the
        # explicitly reviewed identity is protected; live API metadata still refreshes.
        for field in protected:
            if field in existing:
                paper[field] = existing[field]
        return paper

    def format_citation(self, paper: dict, claim: str = "") -> str:
        """Format an evidence citation following the canonical Author et al. YYYY (claim) pattern."""
        citation_key = paper.get("citation_key") or derive_citation_key(
            paper.get("authors", []), paper.get("year"), paper.get("title", "")
        )

        resolved_claim = (
            claim.strip()
            or paper.get("takeaway", "").strip()
            or paper.get("title", "").strip()
        )
        if resolved_claim:
            return f"{citation_key} ({resolved_claim})"
        return citation_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zero-dependency Consensus Academic API client with cache-first persistence."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Search query for academic literature",
    )
    parser.add_argument(
        "--doi",
        "-d",
        type=str,
        help="Look up paper by DOI, paper ID, or citation key",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=5,
        help="Maximum number of search results (default: 5)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only query local cache; never make outbound network requests",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass cache and force re-fetching from Consensus API",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help=f"Path to local cache JSON (default: {DEFAULT_CACHE_PATH})",
    )

    args = parser.parse_args()

    if not args.query and not args.doi:
        parser.print_help(file=sys.stderr)
        return 1

    client = ConsensusClient(
        cache_path=args.cache_path,
        cache_only=args.cache_only,
    )

    if args.doi:
        paper = client.get_paper(args.doi)
        if not paper:
            print(f"Paper '{args.doi}' not found in cache or Consensus API.", file=sys.stderr)
            return 1
        papers = [paper]
    else:
        papers = client.search(
            args.query,
            limit=args.limit,
            use_cache=not args.refresh,
            refresh=args.refresh,
        )

    if not papers:
        print("No studies found.", file=sys.stderr)
        return 0

    if args.format == "json":
        print(json.dumps(papers, indent=2))
    elif args.format == "markdown":
        if len(papers) == 1:
            print(client.format_citation(papers[0]))
        else:
            for p in papers:
                print(f"- {client.format_citation(p)}")
    else:
        # text format
        for idx, p in enumerate(papers, 1):
            print(f"{idx}. {p.get('citation_key', '')} — {p.get('title', '')}")
            citation = client.format_citation(p)
            print(f"   Citation: {citation}")
            if p.get("doi"):
                print(f"   DOI: {p.get('doi')}")
            if p.get("takeaway"):
                print(f"   Takeaway: {p.get('takeaway')}")
            if idx < len(papers):
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
