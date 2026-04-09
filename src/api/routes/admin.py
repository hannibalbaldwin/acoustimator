"""Admin routes for user management (Phase 6.6)."""

from __future__ import annotations

import logging
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_admin
from src.api.dependencies import get_db
from src.api.schemas.admin import CreateUserRequest, UpdateUserRequest, UserResponse
from src.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[UserResponse]:
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [_user_to_response(u) for u in users]


# ---------------------------------------------------------------------------
# POST /api/admin/users
# ---------------------------------------------------------------------------


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> UserResponse:
    """Create a new user (admin only)."""
    user = User(
        email=body.email,
        password_hash=_hash_password(body.password),
        name=body.name,
        role=body.role,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{body.email}' already exists.",
        ) from exc
    return _user_to_response(user)


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}
# ---------------------------------------------------------------------------


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> UserResponse:
    """Update a user's name and/or role (admin only)."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role

    await db.commit()
    await db.refresh(user)
    return _user_to_response(user)


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/{user_id}
# ---------------------------------------------------------------------------


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> None:
    """Delete a user (admin only)."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.commit()
