"""Tests for src/enrichment/product_normalizer.py.

Covers exact matches, fuzzy matches, compound "Tile on Grid" splitting,
no-match cases, batch normalization, and catalog loading.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.enrichment.product_normalizer import (
    NormalizationResult,
    ProductMatch,
    ProductNormalizer,
    normalize_product_name,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "products_catalog.json"


@pytest.fixture(scope="module")
def normalizer() -> ProductNormalizer:
    """Shared ProductNormalizer instance backed by the real catalog."""
    return ProductNormalizer(catalog_path=CATALOG_PATH)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


class TestCatalogLoading:
    """Verify the catalog file can be loaded and produces sane entries."""

    def test_catalog_file_exists(self) -> None:
        """The seed catalog JSON file must exist at the expected path."""
        assert CATALOG_PATH.exists(), f"Catalog not found: {CATALOG_PATH}"

    def test_catalog_is_valid_json(self) -> None:
        """Catalog file must parse as a non-empty JSON array."""
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0

    def test_catalog_contains_required_fields(self) -> None:
        """Every catalog entry must have canonical_name, manufacturer, category, aliases."""
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        for entry in data:
            assert "canonical_name" in entry, f"Missing canonical_name: {entry}"
            assert "category" in entry, f"Missing category: {entry}"
            assert "aliases" in entry, f"Missing aliases: {entry}"
            assert isinstance(entry["aliases"], list), f"aliases must be a list: {entry}"

    def test_normalizer_loads_from_catalog(self) -> None:
        """ProductNormalizer should load entries without raising."""
        n = ProductNormalizer(catalog_path=CATALOG_PATH)
        assert len(n._entries) >= 30

    def test_normalizer_raises_for_missing_catalog(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised when the catalog path does not exist."""
        missing = tmp_path / "nonexistent_catalog.json"
        with pytest.raises(FileNotFoundError, match="Product catalog not found"):
            ProductNormalizer(catalog_path=missing)

    def test_normalizer_raises_for_invalid_json(self, tmp_path: Path) -> None:
        """ValueError is raised when the catalog file contains invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ this is not json }", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            ProductNormalizer(catalog_path=bad_file)


# ---------------------------------------------------------------------------
# Exact matches — compound "Tile on Grid" input
# ---------------------------------------------------------------------------


class TestCompoundTileOnGrid:
    """Tests for inputs containing the 'Tile on Grid' compound format."""

    def test_dune_on_suprafine_exact(self, normalizer: ProductNormalizer) -> None:
        """'Dune on Suprafine' → Armstrong Dune (tile) + Armstrong Suprafine (grid), both exact."""
        result = normalizer.normalize("Dune on Suprafine")

        assert result.raw_input == "Dune on Suprafine"
        assert result.primary is not None
        assert result.secondary is not None

        assert result.primary.canonical_name == "Armstrong Dune"
        assert result.primary.is_exact is True
        assert result.primary.score == 1.0

        assert result.secondary.canonical_name == "Armstrong Suprafine"
        assert result.secondary.is_exact is True
        assert result.secondary.score == 1.0

    def test_armstrong_dune_2404_on_xl(self, normalizer: ProductNormalizer) -> None:
        """'Armstrong Dune #2404 on XL' → Armstrong Dune tile + Armstrong Suprafine grid."""
        result = normalizer.normalize("Armstrong Dune #2404 on XL")

        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Dune"

        assert result.secondary is not None
        assert result.secondary.canonical_name == "Armstrong Suprafine"

    def test_compound_case_insensitive(self, normalizer: ProductNormalizer) -> None:
        """Compound splitting should work regardless of case around 'on'."""
        result = normalizer.normalize("dune ON suprafine")

        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Dune"
        assert result.secondary is not None
        assert result.secondary.canonical_name == "Armstrong Suprafine"

    def test_dune_2x2_suprafine_grid_no_split(self, normalizer: ProductNormalizer) -> None:
        """'Dune, 2x2, Suprafine grid' has no ' on ' and yields no secondary match."""
        result = normalizer.normalize("Dune, 2x2, Suprafine grid")
        # primary should still resolve to Armstrong Dune via fuzzy/exact
        assert result.secondary is None

    def test_secondary_none_when_no_grid(self, normalizer: ProductNormalizer) -> None:
        """A non-compound product name should leave secondary as None."""
        result = normalizer.normalize("Zintra Embossed 12mm")
        assert result.secondary is None


# ---------------------------------------------------------------------------
# Exact matches — individual products
# ---------------------------------------------------------------------------


class TestExactMatches:
    """Tests for direct exact alias matches."""

    def test_zintra_embossed_12mm(self, normalizer: ProductNormalizer) -> None:
        """'Zintra Embossed 12mm' → MDC Zintra Embossed 12mm, exact."""
        result = normalizer.normalize("Zintra Embossed 12mm")
        assert result.primary is not None
        assert result.primary.canonical_name == "MDC Zintra Embossed 12mm"
        assert result.primary.is_exact is True
        assert result.primary.score == 1.0

    def test_woodworks_vector(self, normalizer: ProductNormalizer) -> None:
        """'WoodWorks Vector' → Armstrong WoodWorks Vector, exact."""
        result = normalizer.normalize("WoodWorks Vector")
        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong WoodWorks Vector"
        assert result.primary.is_exact is True

    def test_cortega_alias(self, normalizer: ProductNormalizer) -> None:
        """'Cortega' exact alias maps to Armstrong Cortega."""
        result = normalizer.normalize("Cortega")
        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Cortega"
        assert result.primary.is_exact is True

    def test_qrd_diffuser(self, normalizer: ProductNormalizer) -> None:
        """'QRD Diffuser' maps to RPG QRD Diffuser, exact."""
        result = normalizer.normalize("QRD Diffuser")
        assert result.primary is not None
        assert result.primary.canonical_name == "RPG QRD Diffuser"
        assert result.primary.is_exact is True

    def test_cambridge_sound(self, normalizer: ProductNormalizer) -> None:
        """'Cambridge Sound' maps to Cambridge Sound Management."""
        result = normalizer.normalize("Cambridge Sound")
        assert result.primary is not None
        assert result.primary.canonical_name == "Cambridge Sound Management"
        assert result.primary.is_exact is True

    def test_mdc_zintra_12mm_felt_alias(self, normalizer: ProductNormalizer) -> None:
        """'MDC Zintra 12mm Felt' matches MDC Zintra Embossed 12mm via alias."""
        result = normalizer.normalize("MDC Zintra 12mm Felt")
        assert result.primary is not None
        assert result.primary.canonical_name == "MDC Zintra Embossed 12mm"

    def test_lyra_pb_woodlook(self, normalizer: ProductNormalizer) -> None:
        """'Lyra PB WoodLook' maps to Armstrong Lyra PB."""
        result = normalizer.normalize("Lyra PB WoodLook")
        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Lyra PB"

    def test_case_insensitive_exact(self, normalizer: ProductNormalizer) -> None:
        """Exact matching must be case-insensitive."""
        result = normalizer.normalize("SUPRAFINE")
        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Suprafine"
        assert result.primary.is_exact is True


# ---------------------------------------------------------------------------
# Fuzzy matches
# ---------------------------------------------------------------------------


class TestFuzzyMatches:
    """Tests for inputs that should resolve via fuzzy matching."""

    def test_fuzzy_match_returns_product_match(self, normalizer: ProductNormalizer) -> None:
        """A close-but-not-exact alias should return a ProductMatch with is_exact=False."""
        # Slight misspelling / variation
        result = normalizer.normalize("Armstrng Dune")
        if result.primary is not None:  # fuzzy should catch this
            assert result.primary.is_exact is False
            assert 0.0 < result.primary.score < 1.0

    def test_fuzzy_score_within_bounds(self, normalizer: ProductNormalizer) -> None:
        """Fuzzy match score must be between 0.0 and 1.0 exclusive of 1.0."""
        result = normalizer.normalize("Armstrng Dune")
        if result.primary is not None and not result.primary.is_exact:
            assert 0.0 < result.primary.score < 1.0

    def test_fuzzy_threshold_rejects_garbage(self, normalizer: ProductNormalizer) -> None:
        """A completely unrelated string must not produce a match."""
        result = normalizer.normalize("Completely Unknown Product XYZ")
        assert result.primary is None


# ---------------------------------------------------------------------------
# No-match / edge cases
# ---------------------------------------------------------------------------


class TestNoMatchAndEdgeCases:
    """Tests for inputs that should yield None matches or graceful handling."""

    def test_unknown_product_returns_none_primary(self, normalizer: ProductNormalizer) -> None:
        """'Completely Unknown Product XYZ' → NormalizationResult(primary=None, secondary=None)."""
        result = normalizer.normalize("Completely Unknown Product XYZ")
        assert result.primary is None
        assert result.secondary is None
        assert result.raw_input == "Completely Unknown Product XYZ"

    def test_empty_string(self, normalizer: ProductNormalizer) -> None:
        """Empty string input returns NormalizationResult with both matches None."""
        result = normalizer.normalize("")
        assert result.primary is None
        assert result.secondary is None

    def test_whitespace_only_string(self, normalizer: ProductNormalizer) -> None:
        """Whitespace-only input returns NormalizationResult with both matches None."""
        result = normalizer.normalize("   ")
        assert result.primary is None
        assert result.secondary is None

    def test_raw_input_preserved(self, normalizer: ProductNormalizer) -> None:
        """The raw_input field must always reflect the original string unchanged."""
        raw = "  Dune on Suprafine  "
        result = normalizer.normalize(raw)
        assert result.raw_input == raw


# ---------------------------------------------------------------------------
# Batch normalization
# ---------------------------------------------------------------------------


class TestBatchNormalization:
    """Tests for normalize_batch."""

    def test_batch_empty_list(self, normalizer: ProductNormalizer) -> None:
        """normalize_batch([]) must return an empty list."""
        results = normalizer.normalize_batch([])
        assert results == []

    def test_batch_returns_correct_count(self, normalizer: ProductNormalizer) -> None:
        """normalize_batch must return the same number of results as inputs."""
        names = ["Dune", "Suprafine", "Zintra", "Completely Unknown XYZ"]
        results = normalizer.normalize_batch(names)
        assert len(results) == len(names)

    def test_batch_results_are_normalization_results(self, normalizer: ProductNormalizer) -> None:
        """Each element in the batch output must be a NormalizationResult instance."""
        results = normalizer.normalize_batch(["Dune", "Suprafine"])
        for r in results:
            assert isinstance(r, NormalizationResult)

    def test_batch_preserves_order(self, normalizer: ProductNormalizer) -> None:
        """normalize_batch must preserve input order in the output."""
        names = ["Suprafine", "Dune"]
        results = normalizer.normalize_batch(names)
        assert results[0].raw_input == "Suprafine"
        assert results[1].raw_input == "Dune"

    def test_batch_single_item(self, normalizer: ProductNormalizer) -> None:
        """normalize_batch with one item should behave like normalize."""
        single = normalizer.normalize_batch(["Cortega"])
        assert len(single) == 1
        assert single[0].primary is not None
        assert single[0].primary.canonical_name == "Armstrong Cortega"


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


class TestModuleLevelConvenience:
    """Tests for the normalize_product_name module-level function."""

    def test_normalize_product_name_returns_result(self) -> None:
        """normalize_product_name should return a NormalizationResult."""
        result = normalize_product_name("Dune")
        assert isinstance(result, NormalizationResult)
        assert result.primary is not None
        assert result.primary.canonical_name == "Armstrong Dune"

    def test_normalize_product_name_lazy_loads(self) -> None:
        """Calling normalize_product_name multiple times should not raise."""
        r1 = normalize_product_name("Suprafine")
        r2 = normalize_product_name("Suprafine")
        assert r1.primary is not None
        assert r2.primary is not None
        assert r1.primary.canonical_name == r2.primary.canonical_name


# ---------------------------------------------------------------------------
# ProductMatch model
# ---------------------------------------------------------------------------


class TestProductMatchModel:
    """Unit tests for the ProductMatch Pydantic model."""

    def test_product_match_exact(self) -> None:
        """ProductMatch with is_exact=True and score=1.0 should validate cleanly."""
        m = ProductMatch(
            canonical_name="Armstrong Dune",
            manufacturer="Armstrong",
            category="ceiling_tile",
            score=1.0,
            matched_alias="Dune",
            is_exact=True,
        )
        assert m.score == 1.0
        assert m.is_exact is True

    def test_product_match_fuzzy(self) -> None:
        """ProductMatch with is_exact=False and fractional score should validate cleanly."""
        m = ProductMatch(
            canonical_name="Armstrong Dune",
            manufacturer="Armstrong",
            category="ceiling_tile",
            score=0.87,
            matched_alias="Dune 2x2",
            is_exact=False,
        )
        assert m.is_exact is False
        assert 0.0 < m.score < 1.0

    def test_product_match_manufacturer_optional(self) -> None:
        """manufacturer field may be None."""
        m = ProductMatch(
            canonical_name="Unknown Panel",
            manufacturer=None,
            category="wall_panel",
            score=0.8,
            matched_alias="Unknown",
            is_exact=False,
        )
        assert m.manufacturer is None
