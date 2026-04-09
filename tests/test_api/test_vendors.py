"""Tests for /api/vendors/* endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_all_time_row(
    *,
    vendor_id: object | None = None,
    vendor_name: str = "Armstrong World Industries",
    quote_count: int = 8,
    avg_total: float = 12500.0,
) -> MagicMock:
    row = MagicMock()
    row.vendor_id = vendor_id or uuid4()
    row.vendor_name = vendor_name
    row.quote_count = quote_count
    row.avg_total = avg_total
    return row


def make_window_row(
    *,
    vendor_id: object,
    avg: float = 11000.0,
    count: int = 4,
    attr_avg: str = "baseline_avg",
    attr_count: str = "baseline_count",
) -> MagicMock:
    row = MagicMock()
    row.vendor_id = vendor_id
    setattr(row, attr_avg, avg)
    setattr(row, attr_count, count)
    return row


# ---------------------------------------------------------------------------
# GET /api/vendors/price-summary — returns list of vendor summaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vendor_price_summary_returns_list(client: AsyncClient) -> None:
    """GET /api/vendors/price-summary should return a list of vendor summary dicts."""
    vid = uuid4()
    all_time_row = make_all_time_row(vendor_id=vid, quote_count=5)

    baseline_row = make_window_row(
        vendor_id=vid, avg=10000.0, count=3, attr_avg="baseline_avg", attr_count="baseline_count"
    )
    recent_row = make_window_row(
        vendor_id=vid, avg=11500.0, count=2, attr_avg="recent_avg", attr_count="recent_count"
    )

    mock_db = AsyncMock()

    all_time_result = MagicMock()
    all_time_result.all.return_value = [all_time_row]

    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    recent_result = MagicMock()
    recent_result.all.return_value = [recent_row]

    mock_db.execute = AsyncMock(side_effect=[all_time_result, baseline_result, recent_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/vendors/price-summary")
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        entry = data[0]
        assert "vendor_name" in entry
        assert "quote_count" in entry
        assert "avg_total" in entry
        assert "recent_avg" in entry
        assert "baseline_avg" in entry
        assert "pct_change" in entry
        assert "alert" in entry
        assert entry["vendor_name"] == "Armstrong World Industries"
        assert entry["quote_count"] == 5
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_vendor_price_summary_empty_when_no_qualifying_vendors(client: AsyncClient) -> None:
    """GET /api/vendors/price-summary should return [] when no vendors have enough quotes."""
    # Vendor with only 2 quotes (below _MIN_QUOTES=3)
    all_time_row = make_all_time_row(quote_count=2)

    mock_db = AsyncMock()
    all_time_result = MagicMock()
    all_time_result.all.return_value = [all_time_row]

    mock_db.execute = AsyncMock(return_value=all_time_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/vendors/price-summary")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_vendor_price_summary_alert_on_large_price_change(client: AsyncClient) -> None:
    """GET /api/vendors/price-summary should flag alert=True when price change > 15%."""
    vid = uuid4()
    all_time_row = make_all_time_row(vendor_id=vid, quote_count=6)

    # Baseline = 10000, recent = 12000 → pct_change = 20% → alert
    baseline_row = make_window_row(
        vendor_id=vid, avg=10000.0, count=3, attr_avg="baseline_avg", attr_count="baseline_count"
    )
    recent_row = make_window_row(
        vendor_id=vid, avg=12000.0, count=3, attr_avg="recent_avg", attr_count="recent_count"
    )

    mock_db = AsyncMock()
    all_time_result = MagicMock()
    all_time_result.all.return_value = [all_time_row]

    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    recent_result = MagicMock()
    recent_result.all.return_value = [recent_row]

    mock_db.execute = AsyncMock(side_effect=[all_time_result, baseline_result, recent_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/vendors/price-summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["alert"] is True
        assert entry["pct_change"] == pytest.approx(20.0, abs=0.5)
        assert entry["alert_message"] is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_vendor_price_summary_no_alert_on_small_price_change(client: AsyncClient) -> None:
    """GET /api/vendors/price-summary should not flag alert when price change <= 15%."""
    vid = uuid4()
    all_time_row = make_all_time_row(vendor_id=vid, quote_count=4)

    # Baseline = 10000, recent = 10500 → 5% change → no alert
    baseline_row = make_window_row(
        vendor_id=vid, avg=10000.0, count=2, attr_avg="baseline_avg", attr_count="baseline_count"
    )
    recent_row = make_window_row(
        vendor_id=vid, avg=10500.0, count=2, attr_avg="recent_avg", attr_count="recent_count"
    )

    mock_db = AsyncMock()
    all_time_result = MagicMock()
    all_time_result.all.return_value = [all_time_row]

    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    recent_result = MagicMock()
    recent_result.all.return_value = [recent_row]

    mock_db.execute = AsyncMock(side_effect=[all_time_result, baseline_result, recent_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/vendors/price-summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["alert"] is False
        assert data[0]["alert_message"] is None
    finally:
        app.dependency_overrides.clear()
