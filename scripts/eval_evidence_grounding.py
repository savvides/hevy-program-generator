#!/usr/bin/env python3
"""Evidence Grounding & Consensus Evaluator.

Compiler gatekeeper validating that all program exercises (and cardio prescriptions)
resolve to the dated selected research corpus or an explicit supplement in
data/evidence_authority.json. This checks identity and membership, not claim support.

Validates:
  1. Presence: Every exercise defines a non-empty 'evidence_citation'.
  2. Canonical Format: Matches 'Author et al. YYYY (physiological claim)' or 'Author YYYY (...)'.
  3. Resolution: Citation key resolves uniquely against the local Consensus cache.
  4. Authority: Background, document-only and online-only discoveries cannot pass.

Exits 0 if all exercises satisfy evidence grounding; exits 1 with actionable diagnostics otherwise.

Run: python3 scripts/eval_evidence_grounding.py [--program <path>] [--verify-online]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
CACHE_PATH = REPO_ROOT / "data" / "consensus_cache.json"
EVIDENCE_BASE_PATH = REPO_ROOT / "docs" / "evidence_base.md"
NUTRITION_EVIDENCE_PATH = REPO_ROOT / "docs" / "nutrition_evidence_base.md"

sys.path.insert(0, str(SCRIPTS_DIR))
from program_loader import load_program  # noqa: E402
from consensus_client import ConsensusClient, _surname  # noqa: E402
from evidence_authority import load_authority  # noqa: E402

_SURNAME_PARTICLES = r"(?:(?:van|von|de|da|del|der|di|du|le|la)\s+)?"
_LETTER_OR_HYPHEN = r"(?:[^\W\d_]|['\-])+"
# Surnames may be up to three words ("Krause Neto", "Maia de Farias"). The repeat is
# bounded: an unbounded "*" also matches whole paper titles that end in a year.
_AUTHOR_NAME = rf"{_LETTER_OR_HYPHEN}(?:\s+{_SURNAME_PARTICLES}{_LETTER_OR_HYPHEN}){{0,2}}"
CITATION_REGEX = re.compile(
    rf"^({_AUTHOR_NAME}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_AUTHOR_NAME})?)\s+(\d{{4}}[a-z]?)(?:\s*\((.*?)\))?$",
    flags=re.IGNORECASE,
)


def split_citations(raw: str) -> list[str]:
    """Split multiple citations separated by commas or semicolons outside parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in raw:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char in ",;" and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(char)
    last = "".join(current).strip()
    if last:
        parts.append(last)
    return parts


def _balanced(text: str) -> bool:
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def parse_citation(citation_str: str) -> dict[str, Any] | None:
    """Parse an evidence citation string into structured components.

    Expected formats:
      - 'Author et al. YYYY (claim)'
      - 'Author YYYY (claim)'
      - 'Author & Author YYYY (claim)'
      - 'Author et al. YYYY'
      - 'Author YYYY'
      - Handles surname particles (e.g. 'van Loon et al. 2000')
    """
    if not isinstance(citation_str, str) or not citation_str.strip():
        return None
    raw = citation_str.strip()
    m = CITATION_REGEX.match(raw)
    if not m:
        return None
    author = m.group(1).strip()
    year_raw = m.group(2)
    year = int(year_raw[:4])
    claim = m.group(3).strip() if m.group(3) else None
    if claim is not None and not _balanced(claim):
        # 'A 2021 (x); B 2017 (y)' would otherwise parse as one citation with claim 'x); B 2017 (y'.
        return None
    citation_key = f"{author} {year_raw}"
    return {
        "raw": raw,
        "author": author,
        "year": year,
        "year_token": year_raw,
        "claim": claim,
        "citation_key": citation_key,
    }


def _normalize_key(key: str) -> str:
    """Ignore case, whitespace and abbreviation periods, not surname spelling."""
    return " ".join(key.casefold().replace(".", "").split())


def _extract_primary_surname(author_str: str) -> str:
    """Extract primary author surname, preserving particles like 'van', 'de', etc."""
    clean = re.sub(r"\s+et\s+al\.?.*$", "", author_str, flags=re.IGNORECASE)
    clean = re.split(r"\s+(?:and|&)\s+", clean)[0].strip()
    return clean


def resolve_citation(
    parsed: dict[str, Any],
    cache_data: dict[str, Any],
    evidence_doc_text: str = "",
    verify_online: bool = False,
    consensus_client: Optional[ConsensusClient] = None,
    authority: dict[str, str] | None = None,
) -> tuple[bool, str, str]:
    """Resolve a citation uniquely; supplied authority restricts it to approved DOIs.

    Standalone callers without authority retain document/online resolution.

    Returns:
      (resolved, source_label, details)
    """
    citation_key = parsed["citation_key"]
    norm_target = _normalize_key(citation_key)
    author_clean = parsed["author"]
    year = parsed["year"]
    first_surname = _extract_primary_surname(author_clean)

    papers = cache_data.get("papers", {})

    def select(candidates: list[tuple[str, dict]], source: str) -> tuple[bool, str, str]:
        # Inspect every identity before membership filtering: a background collision
        # cannot make a shorthand unambiguously identify the approved paper.
        if len(candidates) != 1:
            return False, "Unresolved", f"Ambiguous citation '{citation_key}': {len(candidates)} records match."
        pid, paper = candidates[0]
        identity = "doi:" + (paper.get("doi") or pid.removeprefix("doi:")).lower()
        if authority is not None and identity not in authority:
            return False, "Unresolved", f"Citation '{citation_key}' is background; declare its authority before use."
        role = f" ({authority[identity]})" if authority is not None else ""
        return True, source + role, f"{paper.get('doi') or pid} ({paper.get('citation_key') or citation_key})"

    exact = [(pid, paper) for pid, paper in papers.items()
             if norm_target in [_normalize_key(key) for key in
                                [paper.get("citation_key", ""), *paper.get("citation_aliases", [])]]]
    if exact:
        return select(exact, "Consensus Cache")
    fallback = [(pid, paper) for pid, paper in papers.items()
                if paper.get("year") == year and paper.get("authors")
                and _surname(paper["authors"][0]).casefold() == first_surname.casefold()
                and _extract_primary_surname((parse_citation(paper.get("citation_key", "")) or {})
                                             .get("author", "")).casefold() == first_surname.casefold()]
    if len(fallback) == 1:
        # The lone surname-and-year match must also carry the cited year suffix
        # and, when the citation names a co-author, that co-author.
        paper = fallback[0][1]
        cited_authors = re.split(r"\s+(?:and|&)\s+", author_clean)
        if ((parse_citation(paper.get("citation_key", "")) or {}).get("year_token") != parsed["year_token"]
                or (len(cited_authors) > 1
                    and (len(paper["authors"]) < 2
                         or _surname(paper["authors"][1]).casefold() != cited_authors[1].strip().casefold()))):
            fallback = []
    if fallback:
        return select(fallback, "Consensus Cache")

    # Membership never comes from a document substring or a new online discovery.
    if authority is not None:
        return False, "Unresolved", f"Citation '{citation_key}' has no unique approved cache identity."

    # 3. Match in Evidence Base docs (docs/evidence_base.md or docs/nutrition_evidence_base.md)
    if evidence_doc_text and first_surname and year:
        base_surname = first_surname.split()[-1]
        pattern1 = rf"\b{re.escape(base_surname)}\b[^\n\r]*?\b{year}\b"
        pattern2 = rf"\b{year}\b[^\n\r]*?\b{re.escape(base_surname)}\b"
        if re.search(pattern1, evidence_doc_text, re.IGNORECASE) or re.search(pattern2, evidence_doc_text, re.IGNORECASE):
            return True, "Evidence Base Doc", f"docs/evidence_base.md ({citation_key})"

    # 4. Optional online resolution via ConsensusClient
    if verify_online:
        client = consensus_client or ConsensusClient()
        query = f"{citation_key} {parsed.get('claim') or ''}".strip()
        results = client.search(query, limit=3)
        if results:
            matches = [(p.get("id", "consensus-paper"), p) for p in results
                       if _normalize_key(p.get("citation_key", "")) == norm_target
                       or (p.get("year") == year and p.get("authors")
                           and _surname(p["authors"][0]).casefold() == first_surname.casefold())]
            if matches:
                return select(matches, "Consensus API")

    return False, "Unresolved", f"Citation '{parsed['raw']}' could not be resolved in cache or docs"


def eval_program_evidence(
    program_path: Optional[str] = None,
    verify_online: bool = False,
    cache_path: Optional[Path] = None,
    evidence_doc_path: Optional[Path] = None,
) -> tuple[bool, str]:
    """Evaluate program evidence citations against consensus literature standards.

    Returns:
      (passed: bool, diagnostic: str)
    """
    try:
        prog = load_program(program_path)
    except Exception as e:
        return False, f"Failed to load program '{program_path}':\n{e}"

    metadata = prog.get("PROGRAM_METADATA", {})
    title = metadata.get("title", "Training Program")
    file_path = prog.get("_file_path", program_path or "default")
    routines = prog.get("ROUTINES", [])
    cardio = prog.get("CARDIO_SCHEDULE", [])

    c_path = cache_path or CACHE_PATH
    try:
        cache_data = json.loads(c_path.read_text(encoding="utf-8"))
        authority = load_authority(cache_data=cache_data)
    except (OSError, ValueError) as error:
        return False, f"Failed to load research authority: {error}"

    ev_path = evidence_doc_path or EVIDENCE_BASE_PATH
    evidence_texts: list[str] = []
    if ev_path and ev_path.exists():
        evidence_texts.append(ev_path.read_text(encoding="utf-8"))
    if NUTRITION_EVIDENCE_PATH.exists():
        evidence_texts.append(NUTRITION_EVIDENCE_PATH.read_text(encoding="utf-8"))
    combined_doc_text = "\n".join(evidence_texts)

    consensus_client: Optional[ConsensusClient] = None
    if verify_online:
        consensus_client = ConsensusClient()

    failures: list[str] = []
    passed_exercises: list[dict[str, str]] = []

    # 1. Check all routines and exercises
    for r_idx, routine in enumerate(routines):
        r_name = routine.get("name", f"Routine {r_idx + 1}")
        exercises = routine.get("exercises", [])
        if not exercises:
            failures.append(f"Routine '{r_name}' has no exercises defined.")
            continue

        for ex in exercises:
            ex_name = ex.get("name", "Unnamed Exercise")
            if "evidence_citation" not in ex:
                failures.append(f"Missing 'evidence_citation' on exercise '{ex_name}' in routine '{r_name}'.")
                continue

            raw_cit = ex.get("evidence_citation")
            if not isinstance(raw_cit, str) or not raw_cit.strip():
                failures.append(f"Empty or non-string 'evidence_citation' on exercise '{ex_name}' in routine '{r_name}'.")
                continue

            citations = split_citations(raw_cit)
            if not citations:
                failures.append(f"Invalid citation format on exercise '{ex_name}' in routine '{r_name}': '{raw_cit}'")
                continue

            for cit_str in citations:
                parsed = parse_citation(cit_str)
                if not parsed:
                    failures.append(
                        f"Invalid citation format on exercise '{ex_name}' in routine '{r_name}': '{cit_str}' "
                        f"(expected canonical pattern: 'Author et al. YYYY (claim)')"
                    )
                    continue

                resolved, source_lbl, details = resolve_citation(
                    parsed,
                    cache_data=cache_data,
                    evidence_doc_text=combined_doc_text,
                    verify_online=verify_online,
                    consensus_client=consensus_client,
                    authority=authority,
                )
                if not resolved:
                    failures.append(
                        f"Unresolved citation on exercise '{ex_name}' in routine '{r_name}': '{cit_str}'. "
                        f"{details}"
                    )
                else:
                    passed_exercises.append({
                        "routine": r_name,
                        "exercise": ex_name,
                        "citation": cit_str,
                        "source": source_lbl,
                        "details": details,
                    })

    # 2. Check cardio schedule citations if present
    for c_idx, c_item in enumerate(cardio):
        c_day = c_item.get("day", f"Cardio {c_idx + 1}")
        c_type = c_item.get("type", "Session")
        raw_cit = c_item.get("evidence_citation")
        if not isinstance(raw_cit, str) or not raw_cit.strip():
            failures.append(f"Missing evidence_citation on cardio {c_day} {c_type}")
        elif not split_citations(raw_cit):
            failures.append(f"Invalid citation format on cardio '{c_day} {c_type}': '{raw_cit}'")
        else:
            for cit_str in split_citations(raw_cit):
                parsed = parse_citation(cit_str)
                if not parsed:
                    failures.append(
                        f"Invalid citation format on cardio '{c_day} {c_type}': '{cit_str}' "
                        f"(expected canonical pattern: 'Author et al. YYYY (claim)')"
                    )
                    continue

                resolved, source_lbl, details = resolve_citation(
                    parsed,
                    cache_data=cache_data,
                    evidence_doc_text=combined_doc_text,
                    verify_online=verify_online,
                    consensus_client=consensus_client,
                    authority=authority,
                )
                if not resolved:
                    failures.append(
                        f"Unresolved citation on cardio '{c_day} {c_type}': '{cit_str}'. {details}"
                    )
                else:
                    passed_exercises.append({
                        "routine": f"Cardio ({c_day})",
                        "exercise": c_type,
                        "citation": cit_str,
                        "source": source_lbl,
                        "details": details,
                    })

    # Generate diagnostic report
    lines: list[str] = [
        "=" * 80,
        "           CITATION RESOLUTION",
        f"           Program: {title}",
        f"           Source:  {file_path}",
        f"           Reference index: {c_path.name} & evidence_authority.json",
        "=" * 80,
    ]

    current_routine = ""
    for item in passed_exercises:
        if item["routine"] != current_routine:
            current_routine = item["routine"]
            lines.append(f"\n  Routine: {current_routine}")
        lines.append(f"    ✓ {item['exercise']}")
        lines.append(f"      Citation: {item['citation']}")
        lines.append(f"      Resolved: {item['source']} [{item['details']}]")

    lines.append("\n" + "=" * 80)
    if failures:
        lines.append("FAILURES DETECTED:")
        for failure in failures:
            lines.append(f"  ✗ {failure}")
        lines.append("=" * 80)
        lines.append(f"FAIL: {len(failures)} evidence grounding violation(s) found.")
        return False, "\n".join(lines)

    lines.append(f"PASS: All {len(passed_exercises)} citation entries resolved. Claim support, population applicability and study quality are NOT checked.")
    return True, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", default=None, help="Path to training program python file")
    parser.add_argument(
        "--verify-online",
        action="store_true",
        help="Legacy lookup option; new online discoveries cannot bypass research authority",
    )
    args = parser.parse_args(argv)

    passed, diag = eval_program_evidence(args.program, verify_online=args.verify_online)
    print(diag)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
