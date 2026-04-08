"""Shared fixtures for the API test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.main import app

# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------


def make_mock_db() -> AsyncMock:
    """Return a minimal async mock that satisfies get_db."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Async HTTP client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient wired to the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample ORM-like objects for mocking
# ---------------------------------------------------------------------------


def make_estimate(
    *,
    name: str = "Test Project",
    gc_name: str | None = "Skanska",
    status: str = "draft",
    total_estimate: Decimal | None = Decimal("12345.67"),
    overall_confidence: Decimal | None = Decimal("0.75"),
    scopes: list | None = None,
) -> MagicMock:
    est = MagicMock()
    est.id = uuid4()
    est.name = name
    est.gc_name = gc_name
    est.project_address = "123 Main St, Tampa FL"
    est.status = status
    est.total_estimate = total_estimate
    est.overall_confidence = overall_confidence
    est.source_plans = []
    est.created_at = datetime.now(UTC)
    est.updated_at = datetime.now(UTC)
    est.estimate_scopes = scopes or []
    return est


def make_scope(estimate_id: object | None = None) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.estimate_id = estimate_id or uuid4()
    s.tag = "ACT-1"
    s.scope_type = "ACT"
    s.product_name = "Armstrong Ultima"
    s.square_footage = Decimal("1200.00")
    s.material_cost = Decimal("2400.00")
    s.markup_pct = Decimal("0.33")
    s.man_days = Decimal("3.00")
    s.labor_price = Decimal("2175.00")
    s.total = Decimal("5376.92")
    s.confidence_score = Decimal("0.80")
    s.ai_notes = None
    s.room_name = "Open Office"
    s.floor = "1"
    s.building = None
    s.manually_adjusted = False
    s.comparable_project_ids = []
    return s


def make_project() -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.name = "Hillsborough County Courthouse"
    p.gc_name = "Skanska USA"
    p.address = "800 E Twiggs St, Tampa FL"
    p.status = "awarded"
    p.project_type = "government"
    p.quote_date = None
    p.created_at = datetime.now(UTC)
    p.scopes = []
    return p
