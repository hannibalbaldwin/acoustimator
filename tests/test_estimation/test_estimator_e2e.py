"""End-to-end estimator tests using the Seven Pines fixture JSON.

These tests exercise `estimate_from_plan_result()` against known extraction
output to guard against regressions in the filtering logic, heuristic
fallbacks, and cost computation pipeline.  No Dropbox access is needed —
the fixture JSON encodes real values from an actual extraction run.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tests.conftest import requires_models
from src.estimation.estimator import estimate_from_plan_result
from src.extraction.plan_parser.models import PlanReadResult, ScopeSuggestion

FIXTURE_PATH = Path("tests/fixtures/seven_pines_plan_result.json")

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def seven_pines_plan_result() -> PlanReadResult:
    """Load the Seven Pines fixture and parse into PlanReadResult.

    Represents real extraction output: 44 scope suggestions, 3 with area_sf
    (AWP Bluebeam polygons), 41 without (ceiling schedule text extractions).
    """
    data = json.loads(FIXTURE_PATH.read_text())
    return PlanReadResult.model_validate(data)


# ---------------------------------------------------------------------------
# Helper: build a minimal PlanReadResult with specific scopes
# ---------------------------------------------------------------------------


def _make_plan_result(scope_suggestions: list[ScopeSuggestion]) -> PlanReadResult:
    return PlanReadResult(
        source_file="/fake/test_plan.pdf",
        total_pages=1,
        vector_rich_pages=1,
        raster_pages=0,
        pages=[],
        rooms=[],
        ceiling_specs=[],
        scope_suggestions=scope_suggestions,
        total_area_sf=None,
        extraction_confidence=0.95,
        vision_pages_used=0,
        error=None,
        success=True,
    )


def _make_scope(
    tag: str,
    scope_type: str = "ACT",
    area_sf: str | None = "500.00",
    confidence: float = 0.85,
    source: str = "bluebeam_annotation",
) -> ScopeSuggestion:
    return ScopeSuggestion(
        scope_type=scope_type,
        scope_tag=tag,
        area_sf=Decimal(area_sf) if area_sf is not None else None,
        length_lf=None,
        product_hint=None,
        confidence=confidence,
        source=source,
        rooms=[],
    )


# ===========================================================================
# TestEstimatorFromFixture — uses the real Seven Pines JSON fixture
# ===========================================================================


class TestEstimatorFromFixture:
    """Estimator integration tests driven by the Seven Pines real-extraction fixture.

    The fixture has 44 scope suggestions: 3 AWP with area_sf (from Bluebeam
    polygons) and 41 text-only scopes with area_sf=None.  The estimator must
    drop all 41 area-less scopes and produce exactly 3 AWP ScopeEstimates.
    """

    def test_three_awp_scopes_survive_filtering(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """Only the 3 Bluebeam polygon scopes with area_sf should survive the
        estimator's quality filter — the 41 text-only scopes must be dropped."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        assert len(result.scope_estimates) == 3, (
            f"Expected exactly 3 surviving scopes, got {len(result.scope_estimates)}"
        )
        scope_types = {se.scope_type for se in result.scope_estimates}
        assert scope_types == {"AWP"}, (
            f"Expected all surviving scopes to be AWP, got {scope_types}"
        )

        known_areas = {Decimal("568.87"), Decimal("378.18"), Decimal("648.33")}
        for se in result.scope_estimates:
            assert se.area_sf is not None
            closest = min(known_areas, key=lambda a: abs(a - se.area_sf))
            assert abs(se.area_sf - closest) < Decimal("1.0"), (
                f"area_sf {se.area_sf} not within 1.0 SF of any known AWP area"
            )

    def test_total_cost_reasonable(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """Total estimated cost for the 3 AWP scopes (1595 SF combined) must fall
        within a plausible range.  The actual bid was ~$68k; we assert > $40k
        (conservative floor) and < $200k (generous ceiling)."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        total = result.total_estimated_cost
        assert total > Decimal("40000"), (
            f"Total cost ${total} is suspiciously low for 1595 SF of AWP"
        )
        assert total < Decimal("200000"), (
            f"Total cost ${total} exceeds sanity upper bound of $200k"
        )

    def test_man_days_predicted(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """Estimated man-days for 1595 SF of AWP must be within a reasonable range.
        AWP heuristic is ~1.8 man-days per 1000 SF → expect ~2.9 days minimum;
        we assert > 5 to accommodate model variance, capped at 100."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        man_days = result.estimated_man_days
        assert man_days > Decimal("5"), (
            f"estimated_man_days {man_days} is too low for 1595 SF of AWP"
        )
        assert man_days < Decimal("100"), (
            f"estimated_man_days {man_days} exceeds sanity bound of 100"
        )

    def test_scope_cost_components_populated(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """Each surviving scope must have positive material_cost, total, and
        predicted_man_days — none of these should be zero or None."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        for se in result.scope_estimates:
            assert se.material_cost is not None and se.material_cost > Decimal("0"), (
                f"{se.scope_tag}: material_cost is {se.material_cost}"
            )
            assert se.total is not None and se.total > Decimal("0"), (
                f"{se.scope_tag}: total is {se.total}"
            )
            assert se.predicted_man_days is not None and se.predicted_man_days > Decimal("0"), (
                f"{se.scope_tag}: predicted_man_days is {se.predicted_man_days}"
            )

    def test_area_sf_scopes_filtered_by_estimator(self) -> None:
        """Scopes with area_sf=None must be silently dropped regardless of
        confidence.  A synthetic plan with 2 area scopes + 3 area-less scopes
        should produce exactly 2 ScopeEstimates."""
        scopes = [
            _make_scope("ACT-1", area_sf="1000.00", confidence=0.9),
            _make_scope("ACT-2", area_sf="800.00", confidence=0.9),
            _make_scope("ACT-3", area_sf=None, confidence=0.9),
            _make_scope("ACT-4", area_sf=None, confidence=0.9),
            _make_scope("ACT-5", area_sf=None, confidence=0.9),
        ]
        plan_result = _make_plan_result(scopes)
        result = estimate_from_plan_result(plan_result)

        assert len(result.scope_estimates) == 2, (
            f"Expected 2 scopes (those with area_sf), got {len(result.scope_estimates)}"
        )

    def test_low_confidence_scopes_filtered(self) -> None:
        """Scopes with confidence < 0.3 are skipped; 0.3 itself passes (not strictly <).
        A synthetic plan with confidence=[0.2, 0.3, 0.5] should yield 2 estimates."""
        scopes = [
            _make_scope("ACT-1", area_sf="500.00", confidence=0.2),   # skipped: < 0.3
            _make_scope("ACT-2", area_sf="600.00", confidence=0.3),   # passes: == 0.3
            _make_scope("ACT-3", area_sf="700.00", confidence=0.5),   # passes: > 0.3
        ]
        plan_result = _make_plan_result(scopes)
        result = estimate_from_plan_result(plan_result)

        assert len(result.scope_estimates) == 2, (
            f"Expected 2 scopes (confidence 0.3 and 0.5), got {len(result.scope_estimates)}"
        )
        surviving_confidences = sorted(
            float(s.confidence) for s in result.scope_estimates
        )
        # Both surviving scopes should have positive combined confidence
        for c in surviving_confidences:
            assert c > 0

    def test_notes_populated_for_skipped_scopes(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """The estimator must add a note for every dropped scope.  With 41
        area-less scopes in the fixture, the notes list should be non-empty."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        assert len(result.notes) > 0, (
            "Expected notes to record skipped scopes, but notes list is empty"
        )

    @requires_models
    def test_comparable_projects_found(
        self, seven_pines_plan_result: PlanReadResult
    ) -> None:
        """When model files and training_data.csv are available, at least one
        scope estimate should surface comparable historical projects."""
        result = estimate_from_plan_result(seven_pines_plan_result)

        has_comparables = any(
            len(se.comparable_projects) > 0 for se in result.scope_estimates
        )
        assert has_comparables, (
            "Expected at least one scope to have comparable_projects when models are present"
        )


# ===========================================================================
# TestHeuristicFallback — monkeypatches model loaders to force heuristics
# ===========================================================================


class TestHeuristicFallback:
    """Verify that the estimator degrades gracefully when no ML models are
    available, falling back to hard-coded heuristic cost-per-SF tables."""

    def test_heuristic_used_when_no_models(
        self,
        seven_pines_plan_result: PlanReadResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When all three model-loading functions return None, the heuristic
        path must still produce 3 scopes each with a positive total cost.
        The estimator notes must include the string 'heuristic' to confirm
        which code path was taken."""
        monkeypatch.setattr(
            "src.estimation.estimator._load_cost_model",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "src.estimation.estimator._get_markup_model",
            lambda: None,
        )
        monkeypatch.setattr(
            "src.estimation.estimator._get_labor_model",
            lambda: None,
        )

        result = estimate_from_plan_result(seven_pines_plan_result)

        assert len(result.scope_estimates) == 3, (
            f"Heuristic fallback should still produce 3 AWP scopes, got {len(result.scope_estimates)}"
        )
        for se in result.scope_estimates:
            assert se.total is not None and se.total > Decimal("0"), (
                f"{se.scope_tag}: heuristic total is {se.total}"
            )

        # At least one note should mention the heuristic fallback
        combined_notes = " ".join(result.notes).lower()
        assert "heuristic" in combined_notes, (
            f"Expected 'heuristic' in estimator notes; got: {result.notes[:5]}"
        )
