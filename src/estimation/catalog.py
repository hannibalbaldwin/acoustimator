"""Product catalog utilities for Acoustimator.

Provides fuzzy-match lookup against data/products_catalog.json so the
estimation layer can flag scopes whose product name has no catalog baseline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level cache — loaded once on first call.
_catalog: list[dict[str, Any]] | None = None

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "products_catalog.json"


def _load_catalog() -> list[dict[str, Any]]:
    """Load and cache the products catalog from disk."""
    global _catalog
    if _catalog is None:
        try:
            with _CATALOG_PATH.open(encoding="utf-8") as fh:
                _catalog = json.load(fh)
        except FileNotFoundError:
            logger.warning("products_catalog.json not found at %s", _CATALOG_PATH)
            _catalog = []
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse products_catalog.json: %s", exc)
            _catalog = []
    return _catalog


def _catalog_search_terms(entry: dict[str, Any]) -> list[str]:
    """Return all searchable strings for a catalog entry (name + aliases)."""
    terms: list[str] = []
    canonical = entry.get("canonical_name") or entry.get("name") or ""
    if canonical:
        terms.append(canonical.lower().strip())
    for alias in entry.get("aliases", []):
        if alias:
            terms.append(alias.lower().strip())
    return terms


def is_known_product(product_name: str | None) -> bool:
    """Return True if *product_name* fuzzy-matches any catalog entry.

    Matching strategy: substring containment in both directions — the search
    term is considered a match if *either*:
    - the lowercased product_name contains a catalog term, or
    - a catalog term contains the lowercased product_name.

    This covers common abbreviations (e.g. "Dune" matches "Armstrong Dune")
    and slightly verbose names ("Armstrong Ultima 2x2" matches "Armstrong Ultima").
    """
    if not product_name or not product_name.strip():
        return False

    needle = product_name.lower().strip()
    catalog = _load_catalog()

    for entry in catalog:
        for term in _catalog_search_terms(entry):
            if not term:
                continue
            if needle in term or term in needle:
                return True

    return False


def list_catalog_entries() -> list[dict[str, Any]]:
    """Return a lightweight summary of every catalog entry."""
    catalog = _load_catalog()
    results: list[dict[str, Any]] = []
    for entry in catalog:
        results.append(
            {
                "name": entry.get("canonical_name") or entry.get("name") or "",
                "canonical_name": entry.get("canonical_name") or entry.get("name") or "",
                "category": entry.get("category") or "",
                "alias_count": len(entry.get("aliases", [])),
            }
        )
    return results


def add_catalog_entry(
    name: str,
    canonical_name: str,
    category: str,
    aliases: list[str],
) -> dict[str, Any]:
    """Append a new entry to the on-disk catalog and invalidate the cache.

    Returns the newly created entry dict.
    """
    global _catalog

    new_entry: dict[str, Any] = {
        "canonical_name": canonical_name,
        "name": name,
        "category": category,
        "aliases": aliases,
    }

    # Load current data (to preserve any entries added since last reload)
    try:
        with _CATALOG_PATH.open(encoding="utf-8") as fh:
            current: list[dict[str, Any]] = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        current = []

    current.append(new_entry)

    with _CATALOG_PATH.open("w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Invalidate in-memory cache so next call re-reads from disk.
    _catalog = None

    return new_entry
