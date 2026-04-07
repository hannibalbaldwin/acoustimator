"""Product name normalization for Commercial Acoustics (Tampa, FL).

Normalizes free-form product name strings from historical buildups to canonical
entries in the product catalog. Handles compound names like "Dune on Suprafine"
by splitting on "on" and matching each part separately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rapidfuzz import fuzz, process

# Default catalog path relative to this file's package root
_CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "products_catalog.json"

# Minimum fuzzy match score (0-100 scale) to accept a result
_FUZZY_THRESHOLD = 75


class ProductMatch(BaseModel):
    """Result of a product name normalization lookup against the catalog."""

    canonical_name: str
    manufacturer: str | None
    category: str
    score: float  # 0.0-1.0 match confidence
    matched_alias: str  # The alias that produced the match
    is_exact: bool  # True for case-insensitive exact match, False for fuzzy


class NormalizationResult(BaseModel):
    """Full normalization result, optionally containing both tile and grid matches.

    When the raw input contains "X on Y" syntax (e.g., "Dune on Suprafine"),
    ``primary`` holds the tile/panel match and ``secondary`` holds the grid match.
    """

    primary: ProductMatch | None
    secondary: ProductMatch | None
    raw_input: str


class _CatalogEntry(BaseModel):
    """Internal representation of one catalog record loaded from JSON."""

    canonical_name: str
    manufacturer: str | None = None
    category: str
    subcategory: str | None = None
    aliases: list[str] = []
    notes: str | None = None


class ProductNormalizer:
    """Normalizes free-form product names to canonical catalog entries.

    Uses exact match first, then fuzzy matching via rapidfuzz.
    Handles compound names like "Dune on Suprafine" by splitting on " on ".

    Example::

        normalizer = ProductNormalizer()
        result = normalizer.normalize("Dune on Suprafine")
        # result.primary.canonical_name == "Armstrong Dune"
        # result.secondary.canonical_name == "Armstrong Suprafine"
    """

    def __init__(self, catalog_path: Path | None = None) -> None:
        """Load product catalog from a JSON file.

        Args:
            catalog_path: Path to the products_catalog.json file. Defaults to
                ``data/products_catalog.json`` at the repository root.
        """
        path = catalog_path or _CATALOG_PATH
        self._entries: list[_CatalogEntry] = self._load_catalog(path)
        # Build flat alias lookup: normalized alias text → (entry, original alias)
        self._alias_map: dict[str, tuple[_CatalogEntry, str]] = {}
        self._alias_list: list[str] = []  # for rapidfuzz corpus
        for entry in self._entries:
            for alias in entry.aliases:
                normalized = alias.strip().lower()
                self._alias_map[normalized] = (entry, alias)
                self._alias_list.append(alias.strip())

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def normalize(self, raw_name: str) -> NormalizationResult:
        """Normalize a raw product name string to canonical catalog entries.

        Handles the "Tile on Grid" compound format by splitting on " on " and
        matching each segment independently. The first segment is mapped to
        ``primary`` and the second to ``secondary``.

        Args:
            raw_name: Free-form product name from a historical buildup.

        Returns:
            A :class:`NormalizationResult` with ``primary`` and (optionally)
            ``secondary`` :class:`ProductMatch` objects. Either or both may be
            ``None`` if no match meets the confidence threshold.
        """
        parts = self._split_compound(raw_name)

        primary = self._match_segment(parts[0]) if parts else None
        secondary = self._match_segment(parts[1]) if len(parts) > 1 else None

        return NormalizationResult(
            primary=primary,
            secondary=secondary,
            raw_input=raw_name,
        )

    def normalize_batch(self, names: list[str]) -> list[NormalizationResult]:
        """Normalize a list of product name strings.

        Args:
            names: List of free-form product name strings.

        Returns:
            A list of :class:`NormalizationResult` objects in the same order as
            the input list.
        """
        return [self.normalize(name) for name in names]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_catalog(path: Path) -> list[_CatalogEntry]:
        """Read and parse the JSON catalog file.

        Args:
            path: Absolute path to the catalog JSON file.

        Returns:
            List of :class:`_CatalogEntry` objects.

        Raises:
            FileNotFoundError: If the catalog file does not exist.
            ValueError: If the catalog file contains invalid JSON or schema.
        """
        if not path.exists():
            raise FileNotFoundError(f"Product catalog not found: {path}")

        try:
            raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in catalog file {path}: {exc}") from exc

        return [_CatalogEntry.model_validate(item) for item in raw]

    @staticmethod
    def _split_compound(raw_name: str) -> list[str]:
        """Split a compound product name on ' on ' into at most two segments.

        "Dune on Suprafine" → ["Dune", "Suprafine"]
        "Dune, 2x2, Suprafine grid" → ["Dune, 2x2, Suprafine grid"]  (no " on ")

        Args:
            raw_name: Raw product name string.

        Returns:
            List with one or two cleaned string segments.
        """
        # Case-insensitive split on " on " — only split at the first occurrence
        lower = raw_name.lower()
        marker = " on "
        idx = lower.find(marker)
        if idx == -1:
            return [raw_name.strip()]
        left = raw_name[:idx].strip()
        right = raw_name[idx + len(marker) :].strip()
        return [left, right]

    def _match_segment(self, segment: str) -> ProductMatch | None:
        """Attempt to match a single product name segment against the catalog.

        Tries exact (case-insensitive) match first, then falls back to fuzzy
        matching using :func:`rapidfuzz.fuzz.token_sort_ratio`. Fuzzy matches
        below :data:`_FUZZY_THRESHOLD` are discarded.

        Args:
            segment: A single product name segment (after compound splitting).

        Returns:
            A :class:`ProductMatch` if a suitable match is found, else ``None``.
        """
        cleaned = segment.strip()
        if not cleaned:
            return None

        # --- 1. Exact match (case-insensitive) ---
        lower_cleaned = cleaned.lower()
        if lower_cleaned in self._alias_map:
            entry, original_alias = self._alias_map[lower_cleaned]
            return ProductMatch(
                canonical_name=entry.canonical_name,
                manufacturer=entry.manufacturer,
                category=entry.category,
                score=1.0,
                matched_alias=original_alias,
                is_exact=True,
            )

        # --- 2. Fuzzy match ---
        if not self._alias_list:
            return None

        result = process.extractOne(
            cleaned,
            self._alias_list,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=_FUZZY_THRESHOLD,
        )
        if result is None:
            return None

        best_alias, raw_score, _idx = result
        entry, original_alias = self._alias_map[best_alias.strip().lower()]
        return ProductMatch(
            canonical_name=entry.canonical_name,
            manufacturer=entry.manufacturer,
            category=entry.category,
            score=round(raw_score / 100.0, 4),
            matched_alias=original_alias,
            is_exact=False,
        )


# ---------------------------------------------------------------------------
# Module-level convenience API
# ---------------------------------------------------------------------------

_default_normalizer: ProductNormalizer | None = None


def normalize_product_name(raw_name: str) -> NormalizationResult:
    """Normalize a product name using the default catalog.

    Lazy-loads the :class:`ProductNormalizer` on first call and reuses it on
    subsequent calls, avoiding repeated I/O and index construction.

    Args:
        raw_name: Free-form product name string.

    Returns:
        A :class:`NormalizationResult` with matched canonical entries.
    """
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = ProductNormalizer()
    return _default_normalizer.normalize(raw_name)
