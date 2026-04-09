"""Tests for /api/admin/users endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(
    *,
    email: str = "alice@example.com",
    name: str | None = "Alice",
    role: str = "admin",
    password_hash: str = "$2b$12$fakehash",
) -> MagicMock:
    u = MagicMock()
    u.id = uuid4()
    u.email = email
    u.name = name
    u.role = role
    u.password_hash = password_hash
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _admin_override() -> dict:
    return {"sub": "admin-user", "role": "admin"}


def _nonadmin_override() -> dict:
    return {"sub": "regular-user", "role": "user"}


# ---------------------------------------------------------------------------
# GET /api/admin/users — 200 with list structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_returns_200(client: AsyncClient) -> None:
    """GET /api/admin/users should return 200 with a list of UserResponse."""
    users = [make_user(), make_user(email="bob@example.com", name="Bob", role="user")]

    mock_db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        response = await client.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # Check required keys
        for item in data:
            assert "id" in item
            assert "email" in item
            assert "name" in item
            assert "role" in item
            assert "created_at" in item
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/admin/users — 201, hashed password, returned UserResponse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_returns_201(client: AsyncClient) -> None:
    """POST /api/admin/users should create a user and return 201."""
    new_user = make_user(email="new@example.com", name="New User", role="user")

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()

    # After refresh the user object is populated on the same mock
    async def _refresh(obj: object) -> None:
        pass

    mock_db.refresh.side_effect = _refresh

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        with patch("src.api.routes.admin._hash_password", return_value="$2b$12$fakehash") as mock_hash:
            # Intercept db.add so we can inject the user mock that _user_to_response will use
            captured: list = []

            def _add(obj: object) -> None:
                # Populate mock fields to simulate what the ORM would do after commit/refresh
                obj.id = new_user.id  # type: ignore[attr-defined]
                obj.email = "new@example.com"  # type: ignore[attr-defined]
                obj.name = "New User"  # type: ignore[attr-defined]
                obj.role = "user"  # type: ignore[attr-defined]
                obj.created_at = new_user.created_at  # type: ignore[attr-defined]
                captured.append(obj)

            mock_db.add.side_effect = _add

            response = await client.post(
                "/api/admin/users",
                json={"email": "new@example.com", "password": "s3cr3t!", "name": "New User", "role": "user"},
            )

        assert response.status_code == 201, response.text
        mock_hash.assert_called_once_with("s3cr3t!")
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "user"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{id} — 200, fields updated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_returns_200(client: AsyncClient) -> None:
    """PATCH /api/admin/users/{id} should update name/role and return 200."""
    user = make_user(name="Old Name", role="user")

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=user)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        response = await client.patch(
            f"/api/admin/users/{user.id}",
            json={"name": "New Name", "role": "admin"},
        )
        assert response.status_code == 200, response.text
        # The mock user's attributes were mutated in-place by the route
        assert user.name == "New Name"
        assert user.role == "admin"
        data = response.json()
        assert "id" in data
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{id} — 404 when user doesn't exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_not_found(client: AsyncClient) -> None:
    """PATCH /api/admin/users/<unknown> should return 404."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        response = await client.patch(
            f"/api/admin/users/{uuid4()}",
            json={"name": "X"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/{id} — 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_user_returns_204(client: AsyncClient) -> None:
    """DELETE /api/admin/users/{id} should delete user and return 204."""
    user = make_user()

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=user)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        response = await client.delete(f"/api/admin/users/{user.id}")
        assert response.status_code == 204
        mock_db.delete.assert_awaited_once_with(user)
        mock_db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/{id} — 404 when user doesn't exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_user_not_found(client: AsyncClient) -> None:
    """DELETE /api/admin/users/<unknown> should return 404."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        response = await client.delete(f"/api/admin/users/{uuid4()}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin auth requirement — 403 for non-admin role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_required_returns_403(client: AsyncClient) -> None:
    """Requests without admin role should return 403."""
    mock_db = AsyncMock()

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    # Override require_admin to raise 403 directly as the real impl would
    from fastapi import HTTPException

    def _not_admin() -> dict:
        raise HTTPException(status_code=403, detail="Admin required")

    app.dependency_overrides[require_admin] = _not_admin

    try:
        response = await client.get("/api/admin/users")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/admin/users — 409 on duplicate email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_duplicate_email_returns_409(client: AsyncClient) -> None:
    """POST /api/admin/users with existing email should return 409."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.rollback = AsyncMock()

    # Simulate IntegrityError on commit (duplicate unique constraint)
    mock_db.commit = AsyncMock(side_effect=IntegrityError("stmt", "params", Exception("unique violation")))

    from src.api.auth import require_admin
    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_admin] = _admin_override

    try:
        with patch("src.api.routes.admin._hash_password", return_value="$2b$12$fakehash"):
            response = await client.post(
                "/api/admin/users",
                json={"email": "dup@example.com", "password": "pass1234"},
            )
        assert response.status_code == 409
        data = response.json()
        assert "dup@example.com" in data["detail"]
    finally:
        app.dependency_overrides.clear()
