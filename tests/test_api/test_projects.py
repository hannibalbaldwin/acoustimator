"""Tests for GET /api/projects and GET /api/projects/{id}."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import make_project

# ---------------------------------------------------------------------------
# GET /api/projects — 200 with pagination envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects_returns_200(client: AsyncClient) -> None:
    """GET /api/projects should return 200 with PaginatedResponse."""
    projects = [make_project(), make_project()]

    mock_db = AsyncMock()

    # First execute → count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    # Second execute → page query
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = projects

    mock_db.execute = AsyncMock(side_effect=[count_result, page_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == projects[0].name
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/projects — pagination params are respected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects_pagination(client: AsyncClient) -> None:
    """GET /api/projects?limit=10&offset=5 should return correct envelope."""
    mock_db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 100

    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_result, page_result])

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get("/api/projects?limit=10&offset=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["limit"] == 10
        assert data["offset"] == 5
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/projects/{id} — 404 for unknown project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/projects/<unknown> should return 404."""
    unknown_id = uuid4()

    mock_db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get(f"/api/projects/{unknown_id}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/projects/{id} — 200 for existing project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project_found(client: AsyncClient) -> None:
    """GET /api/projects/<id> should return 200 with ProjectResponse."""
    project = make_project()

    mock_db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = project
    mock_db.execute = AsyncMock(return_value=scalar_result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.get(f"/api/projects/{project.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(project.id)
        assert data["name"] == project.name
    finally:
        app.dependency_overrides.clear()
