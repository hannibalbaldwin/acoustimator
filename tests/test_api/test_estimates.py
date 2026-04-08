"""Tests for POST /api/estimates and GET /api/estimates/{id}."""

from __future__ import annotations

import io
from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import make_estimate, make_scope

# ---------------------------------------------------------------------------
# GET /api/estimates/{id} — 404 for unknown ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_estimate_not_found(client: AsyncClient) -> None:
    """GET /api/estimates/<unknown> should return 404."""
    unknown_id = uuid4()

    # Mock db session — execute returns no result
    mock_db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get(f"/api/estimates/{unknown_id}")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/estimates/{id} — 200 for existing estimate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_estimate_found(client: AsyncClient) -> None:
    """GET /api/estimates/<id> should return 200 with EstimateResponse."""
    scope = make_scope()
    estimate = make_estimate(scopes=[scope])
    scope.estimate_id = estimate.id

    mock_db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = estimate
    mock_db.execute = AsyncMock(return_value=scalar_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get(f"/api/estimates/{estimate.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(estimate.id)
        assert data["project_name"] == estimate.name
        assert data["status"] == "draft"
        assert "scopes" in data
        assert len(data["scopes"]) == 1
        assert data["confidence_level"] == "medium"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/estimates — 201 with mocked plan reader + estimator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_estimate_returns_201(client: AsyncClient) -> None:
    """POST /api/estimates should call estimator and return 201."""
    from datetime import datetime

    from src.estimation.models import ProjectEstimate, ScopeEstimate

    fake_scope_estimate = ScopeEstimate(
        scope_tag="ACT-1",
        scope_type="ACT",
        area_sf=Decimal("1200"),
        product_hint="Armstrong Ultima",
        predicted_cost_per_sf=Decimal("4.48"),
        predicted_markup_pct=Decimal("0.33"),
        predicted_man_days=Decimal("3.0"),
        material_cost=Decimal("2400.00"),
        labor_cost=Decimal("2175.00"),
        total=Decimal("5376.92"),
        confidence=0.75,
        model_used="ACT_cost_model",
        comparable_projects=["Project A"],
    )
    fake_pe = ProjectEstimate(
        source_plan="/tmp/test.pdf",
        extraction_confidence=0.75,
        scope_estimates=[fake_scope_estimate],
        total_estimated_cost=Decimal("5376.92"),
        total_area_sf=Decimal("1200"),
        estimated_man_days=Decimal("3.0"),
        notes=[],
        created_at=datetime.now(UTC),
    )

    estimate_obj = make_estimate(scopes=[])
    scope_obj = make_scope(estimate_id=estimate_obj.id)
    estimate_with_scopes = make_estimate(scopes=[scope_obj])
    estimate_with_scopes.id = estimate_obj.id

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # First execute call (for the re-fetch after commit) returns estimate with scopes
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = estimate_with_scopes
    mock_db.execute = AsyncMock(return_value=scalar_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("src.estimation.estimator.estimate_from_pdf", return_value=fake_pe):
            fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")
            response = await client.post(
                "/api/estimates",
                data={
                    "project_name": "Test Project",
                    "gc_name": "Skanska",
                    "address": "123 Main St",
                },
                files=[("plans", ("test_plan.pdf", fake_pdf, "application/pdf"))],
            )

        assert response.status_code == 201, response.text
        data = response.json()
        assert "id" in data
        assert data["project_name"] == "Test Project"
        assert data["status"] in ("draft", "reviewed", "finalized", "exported")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/estimates — 422 with no files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_estimate_no_files_returns_422(client: AsyncClient) -> None:
    """POST /api/estimates with no plan files should return 422."""
    mock_db = AsyncMock()

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.post(
            "/api/estimates",
            data={"project_name": "Test Project"},
            # no files provided
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
