"""API key authentication middleware."""

from __future__ import annotations

import json
import logging
import os

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Routes that skip auth (health check, docs)
_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class ApiKeyMiddleware:
    """
    Pure ASGI middleware (no BaseHTTPMiddleware) that requires X-API-Key on
    all /api/* routes.  Using raw ASGI avoids the Starlette BaseHTTPMiddleware
    streaming bug where CORS headers are dropped on 500 responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "")

        # Pass through: non-API paths, exempt paths, OPTIONS preflight
        if not path.startswith("/api/") or path in _EXEMPT_PATHS or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        api_key = (os.getenv("ACOUSTIMATOR_API_KEY") or "").strip()
        if not api_key:
            logger.warning("ACOUSTIMATOR_API_KEY not set — API auth disabled")
            await self.app(scope, receive, send)
            return

        # Extract key from headers
        headers = dict(scope.get("headers", []))
        provided_key = headers.get(b"x-api-key", b"").decode() or _query_param(
            scope.get("query_string", b""), "api_key"
        )

        if provided_key != api_key:
            body = json.dumps({"detail": "Invalid or missing API key"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


def _query_param(query_string: bytes, name: str) -> str:
    """Extract a single query param value from raw query_string bytes."""
    for part in query_string.decode(errors="replace").split("&"):
        if "=" in part:
            k, _, v = part.partition("=")
            if k == name:
                return v
    return ""
