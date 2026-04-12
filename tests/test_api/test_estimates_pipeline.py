"""API-layer tests for the estimates pipeline.

Sections
--------
1. TestAdditionalItemsCRUD — fully mocked, no DB needed
2. TestScopePatchLaborRecompute — tests the labor_price recompute fix
3. TestFullPipelineWithRealPDF — requires Dropbox + real DB (skipped in CI)
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_db
from src.api.main import app
from tests.conftest import requires_dropbox, requires_models
from tests.test_api.conftest import make_estimate

# ===========================================================================
# Section 1: Additional Items CRUD (fully mocked DB)
# ===========================================================================


class TestAdditionalItemsCRUD:
    """CRUD tests for GET/POST/PATCH/DELETE /api/estimates/{id}/additional-items.

    All DB interactions are mocked — these tests verify HTTP routing, status
    codes, and response shapes without touching a real database.
    """

    @pytest.mark.asyncio
    async def test_list_additional_items_empty(self, client: AsyncClient) -> None:
        """GET /api/estimates/{id}/additional-items returns 200 and empty list
        when there are no items for the estimate."""
        estimate_id = uuid4()

        mock_db = AsyncMock()
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=scalars_result)

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.get(f"/api/estimates/{estimate_id}/additional-items")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_additional_item(self, client: AsyncClient) -> None:
        """POST /api/estimates/{id}/additional-items with valid body returns 201.

        The response must include item_type, description, and amount matching
        the submitted values.
        """
        estimate_id = uuid4()
        item_id = uuid4()
        now = datetime.now(UTC)

        # db.get(Estimate, estimate_id) → returns a mock estimate (not None)
        mock_estimate = MagicMock()
        mock_estimate.id = estimate_id

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.estimate_id = estimate_id
        mock_item.item_type = "lift_rental"
        mock_item.description = "Scissor lift - 3 days"
        mock_item.amount = Decimal("2100.00")
        mock_item.created_at = now

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_estimate)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", item_id) or None)

        # db.refresh is called on the real EstimateAdditionalItem instance that
        # the route constructed. We simulate the DB filling in auto-generated
        # columns (id, created_at) that weren't set by the constructor.
        async def _refresh(obj: object) -> None:
            obj.id = item_id  # type: ignore[attr-defined]
            obj.created_at = now  # type: ignore[attr-defined]

        mock_db.refresh = AsyncMock(side_effect=_refresh)

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.post(
                f"/api/estimates/{estimate_id}/additional-items",
                json={
                    "item_type": "lift_rental",
                    "description": "Scissor lift - 3 days",
                    "amount": 2100.0,
                },
            )
            assert response.status_code == 201, response.text
            data = response.json()
            assert data["item_type"] == "lift_rental"
            assert data["amount"] == pytest.approx(2100.0)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_additional_item_estimate_not_found(self, client: AsyncClient) -> None:
        """POST to a non-existent estimate must return 404.

        The route does `db.get(Estimate, estimate_id)` — when it returns None
        the route raises a 404 HTTPException.
        """
        fake_id = uuid4()

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.post(
                f"/api/estimates/{fake_id}/additional-items",
                json={"item_type": "lift_rental", "amount": 500.0},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_additional_item(self, client: AsyncClient) -> None:
        """PATCH /api/estimates/{id}/additional-items/{item_id} updates amount.

        The route executes a SELECT, modifies in-memory, commits, and returns
        the updated item.  We mock db.execute to return the item and verify
        the response reflects the patched amount.
        """
        estimate_id = uuid4()
        item_id = uuid4()
        now = datetime.now(UTC)

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.estimate_id = estimate_id
        mock_item.item_type = "lift_rental"
        mock_item.description = "Scissor lift"
        mock_item.amount = Decimal("2100.00")
        mock_item.created_at = now

        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = mock_item

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=scalar_result)
        mock_db.commit = AsyncMock()

        async def _refresh(obj: object) -> None:
            # Simulate the amount being updated before refresh
            obj.amount = Decimal("2500.00")  # type: ignore[attr-defined]

        mock_db.refresh = AsyncMock(side_effect=_refresh)

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.patch(
                f"/api/estimates/{estimate_id}/additional-items/{item_id}",
                json={"amount": 2500.0},
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["amount"] == pytest.approx(2500.0)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_additional_item(self, client: AsyncClient) -> None:
        """DELETE /api/estimates/{id}/additional-items/{item_id} returns 204.

        Verifies the route finds the item and returns No Content on success.
        """
        estimate_id = uuid4()
        item_id = uuid4()

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.estimate_id = estimate_id

        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = mock_item

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=scalar_result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.delete(f"/api/estimates/{estimate_id}/additional-items/{item_id}")
            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# Section 2: Scope PATCH — labor_price recompute
# ===========================================================================


class TestScopePatchLaborRecompute:
    """Tests for PATCH /api/estimates/{estimate_id}/scopes/{scope_id}.

    The critical invariant: when ``labor_days`` is updated, the route must
    recompute ``labor_price = man_days * daily_labor_rate`` before writing.
    This exercises the fix made to estimates.py.

    The PATCH route uses ``_fetch_estimate_or_404`` which issues a single
    ``db.execute → scalar_one_or_none`` call that returns the estimate with
    selectinload'd scopes.  We must mock this pattern correctly for both
    the initial fetch and the re-fetch after commit.
    """

    @pytest.mark.asyncio
    async def test_scope_patch_labor_days_updates_labor_price(self, client: AsyncClient) -> None:
        """PATCH scope with labor_days=8 must set labor_price = 8 × 725 = 5800.

        Setup: scope starts with man_days=5, labor_price=3625, daily_labor_rate=725.
        After PATCH with labor_days=8: labor_price should become 5800.

        The route modifies scope in-memory and then re-fetches the estimate
        from DB for the response.  We track the mutation on the mock scope
        and construct the post-update estimate for the re-fetch call.
        """
        estimate_id = uuid4()
        scope_id = uuid4()

        # Build scope mock with explicit Decimal values
        mock_scope = MagicMock()
        mock_scope.id = scope_id
        mock_scope.estimate_id = estimate_id
        mock_scope.tag = "ACT-1"
        mock_scope.scope_type = "ACT"
        mock_scope.product_name = "Armstrong Ultima"
        mock_scope.product_id = None
        mock_scope.square_footage = Decimal("1200.00")
        mock_scope.material_cost = Decimal("2400.00")
        mock_scope.markup_pct = Decimal("0.33")
        mock_scope.man_days = Decimal("5.0")
        mock_scope.daily_labor_rate = Decimal("725.00")
        mock_scope.labor_price = Decimal("3625.00")
        mock_scope.total = Decimal("5376.00")
        mock_scope.confidence_score = Decimal("0.80")
        mock_scope.ai_notes = None
        mock_scope.room_name = "Open Office"
        mock_scope.floor = "1"
        mock_scope.building = None
        mock_scope.manually_adjusted = False
        mock_scope.comparable_project_ids = []

        # MagicMock supports normal attribute assignment — the route will set
        # scope.man_days and scope.labor_price directly, and from_orm_scope
        # will read them back correctly when building the response.

        # Build estimate mock
        mock_estimate = make_estimate(scopes=[mock_scope])
        mock_estimate.id = estimate_id
        mock_estimate.notes = None
        mock_estimate.actual_total_cost = None
        mock_estimate.actual_cost_date = None
        mock_estimate.accuracy_note = None

        # The route calls _fetch_estimate_or_404 twice: before and after commit.
        # Both calls do db.execute → scalar_one_or_none → estimate.
        # We return the same mock_estimate both times; by the second call,
        # mock_scope will already have been mutated by the route.
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = mock_estimate

        # For comparable projects enrichment (ai_notes fallback path)
        comparable_result = MagicMock()
        comparable_result.scalars.return_value.all.return_value = []

        call_count = 0

        async def _execute(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            # First two calls are _fetch_estimate_or_404 (initial + re-fetch)
            # Subsequent calls may be for comparable project lookups
            if call_count <= 2:
                return scalar_result
            return comparable_result

        mock_db = AsyncMock()
        mock_db.execute = _execute
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.patch(
                f"/api/estimates/{estimate_id}/scopes/{scope_id}",
                json={"labor_days": 8.0},
            )
            assert response.status_code == 200, response.text

            # After patching man_days to 8 days at $725/day, labor_price = $5800
            data = response.json()
            # The scopes list in the response should contain the updated scope
            assert "scopes" in data
            scopes_in_response = data["scopes"]
            assert len(scopes_in_response) == 1
            patched_scope = scopes_in_response[0]
            assert patched_scope["man_days"] == pytest.approx(8.0, abs=0.01)
            assert patched_scope["labor_price"] == pytest.approx(5800.0, abs=1.0)
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# Section 3: Full pipeline with real PDF upload (requires Dropbox + real DB)
# ===========================================================================


@requires_dropbox
@requires_models
@pytest.mark.asyncio
async def test_create_estimate_from_seven_pines_pdf(dropbox_root: Path) -> None:
    """Create an estimate by POSTing the real Seven Pines PDF to the API.

    This test uses a REAL database connection and bypasses the mock DB.
    It verifies the full pipeline: PDF upload → plan reading → estimator →
    DB persistence → API response.

    Skipped when DATABASE_URL is not set in environment (no real DB available).

    Post-test cleanup: the created estimate is deleted from the DB so the
    test is idempotent.

    Expected: 3 AWP scopes, all with total_cost > 0, confidence_level = "high".
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured — skipping real-DB pipeline test")

    pdf_path = dropbox_root / "+Seven Pines Jax" / "Seven Pines Jax - Takeoff Dwgs.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Seven Pines PDF not found at {pdf_path}")

    api_key = os.environ.get("ACOUSTIMATOR_API_KEY", "dev-key")
    created_id: str | None = None

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        with open(pdf_path, "rb") as f:
            response = await ac.post(
                "/api/estimates",
                data={
                    "project_name": "Seven Pines Jax E2E Test",
                    "gc_name": "Test GC",
                },
                files={"plans": ("seven_pines.pdf", f, "application/pdf")},
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        created_id = data.get("id")

        # Validate estimate-level fields
        assert "scopes" in data
        scopes = data["scopes"]
        assert len(scopes) == 3, (
            f"Expected exactly 3 AWP scopes, got {len(scopes)}: {[s.get('scope_type') for s in scopes]}"
        )
        for scope in scopes:
            assert scope.get("scope_type") == "AWP", f"Expected scope_type=AWP, got {scope.get('scope_type')}"
            assert (scope.get("total") or 0) > 0, f"Scope {scope.get('tag')} has zero total cost"

        assert data.get("confidence_level") == "high", (
            f"Expected confidence_level=high (extraction_confidence=1.0), got {data.get('confidence_level')}"
        )

        # Cleanup: delete the created estimate so re-runs are idempotent
        if created_id:
            delete_resp = await ac.delete(
                f"/api/estimates/{created_id}",
                headers={"X-API-Key": api_key},
            )
            # Best-effort cleanup — don't fail the test if delete fails
            if delete_resp.status_code not in (200, 204, 404):
                import warnings

                warnings.warn(
                    f"Failed to clean up estimate {created_id}: HTTP {delete_resp.status_code}",
                    stacklevel=1,
                )
