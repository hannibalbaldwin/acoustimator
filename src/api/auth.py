"""JWT auth dependency using Auth.js v5 shared secret."""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, status

# Auth is optional during local dev if AUTH_SECRET is not set
_AUTH_SECRET = os.getenv("AUTH_SECRET", "")


async def get_current_user(request: Request) -> dict:
    """Verify the Auth.js v5 JWT from the session cookie or Authorization header."""
    if not _AUTH_SECRET:
        # Auth disabled in local dev (no secret configured) — return guest
        return {"sub": "local", "role": "admin"}

    try:
        from fastapi_nextauth_jwt import NextAuthJWT

        jwt = NextAuthJWT(secret=_AUTH_SECRET)
        payload = await jwt(request)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")
        return dict(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Raise 403 if the user is not an admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
