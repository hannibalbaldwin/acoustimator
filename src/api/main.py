"""FastAPI application entry point for Acoustimator Phase 6."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import ApiKeyMiddleware
from src.api.routes import admin as admin_router
from src.api.routes import auth_verify as auth_verify_router
from src.api.routes import estimate_additional_items as estimate_additional_items_router
from src.api.routes import estimate_notes as estimate_notes_router
from src.api.routes import estimate_stream as estimate_stream_router
from src.api.routes import estimates as estimates_router
from src.api.routes import products as products_router
from src.api.routes import projects as projects_router
from src.api.routes import stats as stats_router
from src.api.routes import vendors as vendors_router
from src.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    logger.info("Acoustimator API starting up")
    yield
    logger.info("Acoustimator API shutting down")


app = FastAPI(
    title="Acoustimator API",
    description="AI-powered cost estimation engine for Commercial Acoustics",
    version="6.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# ApiKeyMiddleware must be added BEFORE CORSMiddleware so that CORS is the
# outermost layer (runs first/last). If the API key check fails and returns a
# 401/500, CORS headers are still present in the response.
app.add_middleware(ApiKeyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(admin_router.router)
app.include_router(auth_verify_router.router)
app.include_router(estimate_additional_items_router.router, prefix="/api/estimates")
app.include_router(estimate_notes_router.router, prefix="/api/estimates")
app.include_router(estimate_stream_router.router, prefix="/api/estimates")
app.include_router(estimates_router.router)
app.include_router(products_router.router)
app.include_router(projects_router.router)
app.include_router(stats_router.router)
app.include_router(vendors_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}
