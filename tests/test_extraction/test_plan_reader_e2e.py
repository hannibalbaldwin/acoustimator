"""End-to-end tests for the plan reading pipeline using real Dropbox PDFs.

These tests are skipped in CI (no Dropbox access). Run locally to verify
plan reading regressions.

Each test is decorated with ``@requires_dropbox`` so the suite still passes
on machines that don't have the Dropbox folder mounted.  Tests that also
need ML models are additionally decorated with ``@requires_models``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.estimation.estimator import estimate_from_plan_result
from src.extraction.plan_reader import read_plan
from tests.conftest import requires_dropbox, requires_models

# ===========================================================================
# Seven Pines — known-good vector PDF
# ===========================================================================


@requires_dropbox
def test_seven_pines_jax_extraction(seven_pines_pdf: Path) -> None:
    """The Seven Pines Jax PDF must extract with full confidence and produce
    exactly 3 area-bearing AWP scopes from Bluebeam polygon annotations.

    Validates the top-level PlanReadResult fields against known good values
    recorded from an actual extraction run (extraction_confidence=1.0,
    total_area_sf≈1595.38, 7 vector-rich pages, ≥44 scope suggestions).
    """
    result = read_plan(seven_pines_pdf, use_vision=False)

    assert result.success is True, f"Extraction failed: {result.error}"
    assert result.extraction_confidence == pytest.approx(1.0), (
        f"Expected confidence 1.0, got {result.extraction_confidence}"
    )
    assert result.total_area_sf is not None, "total_area_sf should not be None"
    assert abs(float(result.total_area_sf) - 1595.38) < 5.0, (
        f"total_area_sf {result.total_area_sf} not within 5 SF of 1595.38"
    )
    assert len(result.scope_suggestions) >= 10, (
        f"Expected >= 10 scope suggestions, got {len(result.scope_suggestions)}"
    )

    area_scopes = [
        s for s in result.scope_suggestions
        if s.area_sf is not None and s.area_sf > 0
    ]
    assert len(area_scopes) == 3, (
        f"Expected exactly 3 scopes with area_sf > 0, got {len(area_scopes)}"
    )
    for s in area_scopes:
        assert s.scope_type == "AWP", (
            f"Expected area scope to be AWP type, got {s.scope_type} ({s.scope_tag})"
        )

    assert result.vector_rich_pages >= 5, (
        f"Expected >= 5 vector-rich pages, got {result.vector_rich_pages}"
    )


@requires_dropbox
def test_seven_pines_awp_areas_match_known_values(seven_pines_pdf: Path) -> None:
    """The 3 AWP Bluebeam polygon areas must match recorded values within 1 SF.

    Known values from the actual extraction run:
      - AWP-1: 568.87 SF
      - AWP-2: 378.18 SF
      - AWP-3: 648.33 SF

    Sorted ascending: [378.18, 568.87, 648.33]
    """
    result = read_plan(seven_pines_pdf, use_vision=False)
    assert result.success is True, f"Extraction failed: {result.error}"

    area_scopes = sorted(
        [s for s in result.scope_suggestions if s.area_sf is not None and s.area_sf > 0],
        key=lambda s: float(s.area_sf),
    )
    assert len(area_scopes) == 3, (
        f"Expected exactly 3 area scopes, got {len(area_scopes)}"
    )

    expected_sorted = [378.18, 568.87, 648.33]
    for scope, expected in zip(area_scopes, expected_sorted, strict=False):
        actual = float(scope.area_sf)
        assert abs(actual - expected) < 1.0, (
            f"{scope.scope_tag}: area_sf {actual:.2f} not within 1 SF of expected {expected}"
        )


# ===========================================================================
# Brandon Library — second known-good vector PDF
# ===========================================================================


@requires_dropbox
def test_brandon_library_extraction(brandon_library_pdf: Path) -> None:
    """The Brandon Library PDF must extract successfully with total_area_sf > 10,000 SF.

    Known values: extraction_confidence=1.0, total_area_sf=17914.05,
    29 scope suggestions.
    """
    result = read_plan(brandon_library_pdf, use_vision=False)

    assert result.success is True, f"Extraction failed: {result.error}"
    assert result.extraction_confidence == pytest.approx(1.0), (
        f"Expected confidence 1.0, got {result.extraction_confidence}"
    )
    assert result.total_area_sf is not None, "total_area_sf should not be None"
    assert float(result.total_area_sf) > 10_000, (
        f"total_area_sf {result.total_area_sf} unexpectedly low for Brandon Library"
    )
    assert len(result.scope_suggestions) >= 5, (
        f"Expected >= 5 scope suggestions, got {len(result.scope_suggestions)}"
    )


# ===========================================================================
# Full pipeline: Seven Pines read → estimate
# ===========================================================================


@requires_dropbox
@requires_models
def test_full_pipeline_seven_pines(seven_pines_pdf: Path) -> None:
    """Full regression test: read Seven Pines PDF then run estimate_from_plan_result().

    Verifies the complete pipeline from raw PDF to cost estimate produces
    3 AWP scope estimates with positive man-days and a total cost > $40k.
    """
    plan_result = read_plan(seven_pines_pdf, use_vision=False)
    assert plan_result.success is True, f"Plan reading failed: {plan_result.error}"

    estimate = estimate_from_plan_result(plan_result)

    assert len(estimate.scope_estimates) == 3, (
        f"Expected 3 scope estimates after filtering, got {len(estimate.scope_estimates)}"
    )
    assert estimate.total_estimated_cost > 40_000, (
        f"Total cost ${estimate.total_estimated_cost} below expected floor of $40k"
    )
    for se in estimate.scope_estimates:
        assert se.predicted_man_days is not None and se.predicted_man_days > 0, (
            f"{se.scope_tag}: predicted_man_days should be > 0"
        )


# ===========================================================================
# Raster PDF — low-confidence extraction without vision
# ===========================================================================


@requires_dropbox
def test_raster_pdf_without_vision_produces_low_confidence(
    dropbox_root: Path,
) -> None:
    """A raster-heavy PDF read without the Vision API fallback should produce
    extraction_confidence <= 0.6 to signal that page content could not be
    fully extracted.

    Uses the USF MUS drawings as a raster test case; skips if not present.
    """
    usf_pdf = dropbox_root / "+USF MUS" / "USF MUS Takeoff Drawings 4.23.25.pdf"
    if not usf_pdf.exists():
        pytest.skip(f"Raster test PDF not found at {usf_pdf}")

    result = read_plan(usf_pdf, use_vision=False)

    assert result.extraction_confidence <= 0.6, (
        f"Expected low extraction_confidence (<= 0.6) for raster PDF without vision, "
        f"got {result.extraction_confidence}"
    )
