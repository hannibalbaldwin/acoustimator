"""FastAPI application entry point for Acoustimator Phase 6."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import estimates as estimates_router
from src.api.routes import projects as projects_router
from src.api.routes import stats as stats_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(estimates_router.router)
app.include_router(projects_router.router)
app.include_router(stats_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}
