"""Tests for POST /api/auth/verify."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# POST /api/auth/verify — correct credentials → 200 + user payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_correct_credentials_returns_200(client: AsyncClient) -> None:
    """POST /api/auth/verify with valid email/password should return user info."""
    user_id = str(uuid4())

    mock_db = AsyncMock()
    row = MagicMock()
    # Simulate row unpacking: id_, email, name, role, password_hash
    row.__iter__ = MagicMock(return_value=iter([user_id, "alice@example.com", "Alice", "admin", "$2b$12$fakehash"]))
    result = MagicMock()
    result.fetchone.return_value = row
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("src.api.routes.auth_verify.bcrypt.checkpw", return_value=True):
            response = await client.post(
                "/api/auth/verify",
                json={"email": "alice@example.com", "password": "correct_password"},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "alice@example.com"
        assert data["name"] == "Alice"
        assert data["role"] == "admin"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/auth/verify — wrong password → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_wrong_password_returns_401(client: AsyncClient) -> None:
    """POST /api/auth/verify with wrong password should return 401."""
    user_id = str(uuid4())

    mock_db = AsyncMock()
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([user_id, "alice@example.com", "Alice", "user", "$2b$12$fakehash"]))
    result = MagicMock()
    result.fetchone.return_value = row
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("src.api.routes.auth_verify.bcrypt.checkpw", return_value=False):
            response = await client.post(
                "/api/auth/verify",
                json={"email": "alice@example.com", "password": "wrong_password"},
            )
        assert response.status_code == 401
        data = response.json()
        assert "invalid" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/auth/verify — unknown email → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_unknown_email_returns_401(client: AsyncClient) -> None:
    """POST /api/auth/verify with unknown email should return 401."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = None  # No matching user
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await client.post(
            "/api/auth/verify",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "invalid" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/auth/verify — case-insensitive email matching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_case_insensitive_email(client: AsyncClient) -> None:
    """POST /api/auth/verify with uppercase email should match the stored lowercase record."""
    user_id = str(uuid4())

    mock_db = AsyncMock()
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([user_id, "alice@example.com", "Alice", "user", "$2b$12$fakehash"]))
    result = MagicMock()
    result.fetchone.return_value = row
    mock_db.execute = AsyncMock(return_value=result)

    from src.api.dependencies import get_db
    from src.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("src.api.routes.auth_verify.bcrypt.checkpw", return_value=True):
            # Login with UPPER@EMAIL.COM — the route lowercases it before querying
            response = await client.post(
                "/api/auth/verify",
                json={"email": "ALICE@EXAMPLE.COM", "password": "correct_password"},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["id"] == user_id

        # Verify the DB was queried with the lowercased, stripped email
        call_args = mock_db.execute.call_args
        params = call_args[0][1]  # positional second arg: the params dict
        assert params["email"] == "alice@example.com"
    finally:
        app.dependency_overrides.clear()
