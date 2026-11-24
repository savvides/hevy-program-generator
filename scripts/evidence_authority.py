"""Validate the API-driven research review manifest and return its approved DOI roles."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data/evidence_authority.json"


def load_authority(manifest_path: Path | None = None,
                   cache_data: dict | None = None) -> dict[str, str]:
    """Fail closed if manifest integrity, identities or cache agreement fail."""
    try:
        manifest = json.loads((manifest_path or MANIFEST_PATH).read_text(encoding="utf-8"))
        review_id = manifest.get("review_id")
        if not review_id or not isinstance(review_id, str):
            raise ValueError("Manifest missing valid review_id.")

        review_date = manifest.get("review_date")
        if not review_date or not isinstance(review_date, str):
            raise ValueError("Manifest missing valid review_date.")

        primary_entries = manifest.get("primary")
        if not isinstance(primary_entries, list) or len(primary_entries) == 0:
            raise ValueError("Manifest primary list must be a non-empty array.")

        supplemental_entries = manifest.get("supplemental")
        if not isinstance(supplemental_entries, list):
            raise ValueError("Manifest supplemental list must be an array.")

        if cache_data is None:
            cache_data = json.loads((ROOT / "data/consensus_cache.json").read_text(encoding="utf-8"))
        papers = cache_data.get("papers", {})

        identities: set[str] = set()
        for pid, paper in papers.items():
            doi = paper.get("doi")
            if doi:
                identity = "doi:" + doi.strip().lower()
                if identity in identities:
                    raise ValueError(f"duplicate cache DOI identity {identity}; merge the duplicate records.")
                identities.add(identity)
                if pid != identity or paper.get("id") != identity:
                    raise ValueError(f"Noncanonical cache DOI identity {pid}; expected {identity}.")

        roles: dict[str, str] = {}
        for idx, entry in enumerate(primary_entries, 1):
            doi = entry.get("doi", "").strip().lower()
            if not doi.startswith("10."):
                raise ValueError(f"Missing or invalid DOI at primary index {idx}: '{doi}'.")
            pid = "doi:" + doi
            if pid in roles:
                raise ValueError(f"duplicate research DOI {pid}; review the primary identities.")
            roles[pid] = "primary"
            paper = papers.get(pid)
            if paper is None:
                raise ValueError(f"Primary DOI {pid} missing from cache; import record.")

        for supplement in supplemental_entries:
            doi = supplement.get("doi", "").strip().lower()
            purpose = supplement.get("purpose", "").strip()
            if not doi.startswith("10.") or not purpose:
                raise ValueError("Supplement DOI and limited purpose must be explicit and canonical.")
            pid = "doi:" + doi
            if pid in roles:
                raise ValueError(f"duplicate authority DOI {pid}; declare exactly one role.")
            if pid not in papers:
                raise ValueError(f"Supplement DOI {pid} missing from cache; restore the declared source.")
            roles[pid] = "supplemental"

        canonical_keys: dict[str, str] = {}
        for pid, paper in papers.items():
            key = " ".join(paper.get("citation_key", "").casefold().split())
            if not key:
                raise ValueError(f"Cache paper {pid} is missing its canonical citation key.")
            if key in canonical_keys:
                raise ValueError(
                    f"duplicate canonical citation key {key}: {canonical_keys[key]} and {pid}; disambiguate explicitly."
                )
            canonical_keys[key] = pid

        return roles
    except (OSError, KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load research authority: {error}; check manifest and cache structure.") from error
