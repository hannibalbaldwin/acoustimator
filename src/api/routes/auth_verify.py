"""Simple credential verification endpoint for Auth.js."""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db

router = APIRouter(prefix="/api/credentials", tags=["auth"])


class VerifyRequest(BaseModel):
    email: str
    password: str


class VerifyResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str


@router.post("/verify", response_model=VerifyResponse)
async def verify_credentials(body: VerifyRequest, db: AsyncSession = Depends(get_db)) -> VerifyResponse:
    """Verify email/password credentials and return user info if valid.

    Returns 401 for any invalid credential — intentionally no hint whether the
    email or password is wrong.
    """
    result = await db.execute(
        text("SELECT id::text, email, name, role, password_hash FROM users WHERE email = :email"),
        {"email": body.email.lower().strip()},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    id_, email, name, role, password_hash = row
    if not bcrypt.checkpw(body.password.encode(), password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return VerifyResponse(id=id_, email=email, name=name, role=role)
