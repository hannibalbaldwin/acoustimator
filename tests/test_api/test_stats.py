"""Tests for /api/stats/* endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# GET /api/stats/summary — 200 with required keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_summary_returns_200(client: AsyncClient) -> None:
    """GET /api/stats/summary should return 200 with all required keys."""
    mock_db = AsyncMock()

    # Four sequential scalar_one() calls: total_projects, active_estimates, avg_act, total_sf
    results = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    results[0].scalar_one.return_value = 125  # total_projects
    results[1].scalar_one.return_value = 18  # active_estimates
    results[2].scalar_one.return_value = 4.87  # avg_act_cost_per_sf
    results[3].scalar_one.return_value = 987654.0  # total_historical_sf

    mock_db.execute = AsyncMock(side_effect=results)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/summary")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "total_projects" in data
        assert "active_estimates" in data
        assert "avg_act_cost_per_sf" in data
        assert "total_historical_sf" in data
        assert data["total_projects"] == 125
        assert data["active_estimates"] == 18
        assert isinstance(data["avg_act_cost_per_sf"], float)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stats_summary_null_averages(client: AsyncClient) -> None:
    """GET /api/stats/summary should return null for avg/sf when no data exists."""
    mock_db = AsyncMock()

    results = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    results[0].scalar_one.return_value = 0
    results[1].scalar_one.return_value = 0
    results[2].scalar_one.return_value = None  # No ACT data
    results[3].scalar_one.return_value = None  # No scope data

    mock_db.execute = AsyncMock(side_effect=results)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["avg_act_cost_per_sf"] is None
        assert data["total_historical_sf"] is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/stats/cost-trends?granularity=year — returns list of data points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_trends_year_returns_list(client: AsyncClient) -> None:
    """GET /api/stats/cost-trends?granularity=year should return a list of trend dicts."""
    # Build a fake row that has the fields the route accesses
    row1 = MagicMock()
    row1.scope_type = "ACT"
    row1.avg_cost_per_sf = 4.85
    row1.project_count = 10
    row1.year = 2024.0

    row2 = MagicMock()
    row2.scope_type = "AWP"
    row2.avg_cost_per_sf = 7.21
    row2.project_count = 5
    row2.year = 2024.0

    mock_db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [row1, row2]
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/cost-trends?granularity=year")
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        if data:
            first = data[0]
            assert "date" in first
            assert "_count" in first
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cost_trends_empty_db_returns_empty_list(client: AsyncClient) -> None:
    """GET /api/stats/cost-trends should return an empty list when there is no data."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/cost-trends?granularity=year")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/stats/accuracy — returns accuracy stats structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_accuracy_with_data(client: AsyncClient) -> None:
    """GET /api/stats/accuracy should return accuracy stats structure when data exists."""
    from decimal import Decimal

    mock_db = AsyncMock()

    # First execute: rows with actuals
    actuals_row1 = MagicMock()
    actuals_row1.id = "estimate-1"
    actuals_row1.actual_total_cost = Decimal("10000")
    actuals_row1.total_estimate = Decimal("9500")

    actuals_row2 = MagicMock()
    actuals_row2.id = "estimate-2"
    actuals_row2.actual_total_cost = Decimal("20000")
    actuals_row2.total_estimate = Decimal("21000")

    actuals_result = MagicMock()
    actuals_result.all.return_value = [actuals_row1, actuals_row2]

    # Second execute: per-scope-type breakdown
    scope_row = MagicMock()
    scope_row.scope_type = "ACT"
    scope_row.n = 3

    scope_result = MagicMock()
    scope_result.all.return_value = [scope_row]

    mock_db.execute = AsyncMock(side_effect=[actuals_result, scope_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/accuracy")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "total_with_actuals" in data
        assert "mean_absolute_pct_error" in data
        assert "mean_bias_pct" in data
        assert "by_scope_type" in data
        assert data["total_with_actuals"] == 2
        assert isinstance(data["mean_absolute_pct_error"], float)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stats_accuracy_no_data_returns_zeros(client: AsyncClient) -> None:
    """GET /api/stats/accuracy should return null metrics when no actuals exist."""
    mock_db = AsyncMock()

    result = MagicMock()
    result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/stats/accuracy")
        assert response.status_code == 200
        data = response.json()
        assert data["total_with_actuals"] == 0
        assert data["mean_absolute_pct_error"] is None
        assert data["mean_bias_pct"] is None
        assert data["by_scope_type"] == {}
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/stats/model-status — returns model status structure (or empty gracefully)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_model_status_no_manifest(client: AsyncClient) -> None:
    """GET /api/stats/model-status should return a valid structure even without a manifest file."""
    mock_db = AsyncMock()

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # ModelRetrainer is imported locally inside the route function, so patch its module path
        with (
            patch("src.api.routes.stats._MANIFEST_PATH") as mock_path,
            patch("src.models.retrainer.ModelRetrainer") as mock_retrainer_cls,
        ):
            mock_path.exists.return_value = False

            mock_retrainer = MagicMock()
            mock_retrainer.should_retrain = AsyncMock(return_value=(False, "No actuals yet"))
            mock_retrainer_cls.return_value = mock_retrainer

            response = await client.get("/api/stats/model-status")

        assert response.status_code == 200, response.text
        data = response.json()
        assert "last_retrain" in data
        assert "models" in data
        assert "needs_retrain" in data
        assert "retrain_reason" in data
        assert isinstance(data["models"], list)
        assert data["last_retrain"] is None  # no manifest → no retrain date
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stats_model_status_with_manifest(client: AsyncClient) -> None:
    """GET /api/stats/model-status should parse model entries from a manifest."""
    import json

    mock_db = AsyncMock()

    manifest_data = {
        "last_retrain": "2026-01-15T10:00:00Z",
        "ACT": {
            "status": "trained",
            "cv_mape": 0.135,
            "n_training_rows": 82,
            "model_type": "RandomForest",
        },
        "AWP": {
            "status": "trained",
            "cv_mape": 0.182,
            "n_training_rows": 45,
            "model_type": "GradientBoosting",
        },
    }

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with (
            patch("src.api.routes.stats._MANIFEST_PATH") as mock_path,
            patch("src.models.retrainer.ModelRetrainer") as mock_retrainer_cls,
        ):
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = json.dumps(manifest_data)

            mock_retrainer = MagicMock()
            mock_retrainer.should_retrain = AsyncMock(return_value=(False, "OK"))
            mock_retrainer_cls.return_value = mock_retrainer

            response = await client.get("/api/stats/model-status")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["last_retrain"] == "2026-01-15T10:00:00Z"
        assert len(data["models"]) >= 2
        act_model = next((m for m in data["models"] if m["scope_type"] == "ACT"), None)
        assert act_model is not None
        assert act_model["n_train"] == 82
        assert act_model["algorithm"] == "RandomForest"
    finally:
        app.dependency_overrides.clear()
