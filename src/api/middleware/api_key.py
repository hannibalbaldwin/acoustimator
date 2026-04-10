"""API key authentication middleware."""

from __future__ import annotations

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Routes that skip auth (health check, docs)
_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header on all /api/* routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-API routes, exempt paths, and CORS preflight requests
        if not path.startswith("/api/") or path in _EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        api_key = os.getenv("ACOUSTIMATOR_API_KEY")
        if not api_key:
            # If no key configured, allow all (dev mode)
            logger.warning("ACOUSTIMATOR_API_KEY not set — API auth disabled")
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if provided_key != api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
