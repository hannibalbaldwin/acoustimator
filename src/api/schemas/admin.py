"""Pydantic schemas for the admin user management and retraining API."""

from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    created_at: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = "user"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    password: str | None = None


# ---------------------------------------------------------------------------
# Retraining schemas (Phase 7.2)
# ---------------------------------------------------------------------------


class RetrainRequest(BaseModel):
    """Optional parameters for POST /api/admin/retrain."""

    force: bool = False
    """Skip the should_retrain threshold check and retrain unconditionally."""

    dry_run: bool = False
    """Evaluate new models but do not save .joblib files or update the manifest."""

    threshold: int = 10
    """Minimum new projects with actuals since last retrain required to trigger."""


class RetrainResponse(BaseModel):
    """Immediate acknowledgement returned by POST /api/admin/retrain."""

    status: str
    """Always 'retraining_started' when a background task was queued."""

    message: str
    """Human-readable description of what was scheduled."""


# ---------------------------------------------------------------------------
# Project-type population schemas (Phase 7.x)
# ---------------------------------------------------------------------------


class PopulateProjectTypesRequest(BaseModel):
    """Optional parameters for POST /api/admin/populate-project-types."""

    dry_run: bool = False
    """Classify and log without writing any changes to the DB."""


class PopulateProjectTypesResponse(BaseModel):
    """Immediate acknowledgement returned by POST /api/admin/populate-project-types."""

    status: str
    """Always 'classification_started' when a background task was queued."""

    message: str
    """Human-readable description of what was scheduled."""
