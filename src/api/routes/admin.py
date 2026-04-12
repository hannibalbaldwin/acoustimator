"""Admin routes for user management (Phase 6.6), model retraining (Phase 7.2),
and project-type classification (Phase 7.x)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_admin
from src.api.dependencies import get_db
from src.api.schemas.admin import (
    CreateUserRequest,
    PopulateProjectTypesRequest,
    PopulateProjectTypesResponse,
    RetrainRequest,
    RetrainResponse,
    UpdateUserRequest,
    UserResponse,
)
from src.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_RETRAIN_SCRIPT = _ROOT / "scripts" / "retrain_models.py"
_POPULATE_TYPES_SCRIPT = _ROOT / "scripts" / "populate_project_types.py"


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
    if body.password is not None:
        user.password_hash = _hash_password(body.password)

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


# ---------------------------------------------------------------------------
# POST /api/admin/retrain  (Phase 7.2)
# ---------------------------------------------------------------------------
# NOTE: Vercel serverless cannot run long-lived Python subprocesses.  This
# endpoint is designed to be called by an external scheduler (e.g. a monthly
# GitHub Actions workflow).  It launches retrain_models.py in a non-blocking
# background task so the HTTP response returns immediately.  Example cron:
#
#   on:
#     schedule:
#       - cron: '0 3 1 * *'   # 03:00 UTC on the 1st of every month
#   jobs:
#     retrain:
#       runs-on: ubuntu-latest
#       steps:
#         - uses: actions/checkout@v4
#         - run: |
#             curl -X POST https://your-app.vercel.app/api/admin/retrain \
#               -H "Authorization: Bearer $ADMIN_TOKEN" \
#               -H "Content-Type: application/json" \
#               -d '{"threshold": 10}'


def _run_retrain_subprocess(force: bool, dry_run: bool, threshold: int) -> None:
    """Run scripts/retrain_models.py in a subprocess (background task body).

    Called from a FastAPI BackgroundTask — errors are logged, not raised.
    """
    cmd = [sys.executable, str(_RETRAIN_SCRIPT), f"--threshold={threshold}"]
    if force:
        cmd.append("--force")
    if dry_run:
        cmd.append("--dry-run")

    logger.info("Starting retrain subprocess: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min hard cap
            cwd=str(_ROOT),
        )
        if result.returncode == 0:
            logger.info("Retrain subprocess finished successfully")
        else:
            logger.warning(
                "Retrain subprocess exited with code %d\nstdout:\n%s\nstderr:\n%s",
                result.returncode,
                result.stdout[-2000:],
                result.stderr[-2000:],
            )
    except subprocess.TimeoutExpired:
        logger.error("Retrain subprocess timed out after 600 s")
    except Exception as exc:
        logger.exception("Retrain subprocess raised an unexpected error: %s", exc)


@router.post("/retrain", response_model=RetrainResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_retrain(
    body: RetrainRequest,
    background_tasks: BackgroundTasks,
    _admin: dict = Depends(require_admin),
) -> RetrainResponse:
    """Trigger a model retrain in the background (admin only).

    Launches ``scripts/retrain_models.py`` as a subprocess so the endpoint
    returns immediately with HTTP 202.  The actual training runs asynchronously;
    check ``GET /api/stats/model-status`` afterwards for updated MAPEs and
    ``last_retrain`` timestamp.

    Request body (all optional):

    - **force** — skip the new-projects threshold check (default: false)
    - **dry_run** — evaluate but do not save model files (default: false)
    - **threshold** — min new projects with actuals required (default: 10)
    """
    logger.info(
        "Admin '%s' triggered retrain: force=%s dry_run=%s threshold=%d",
        _admin.get("email", _admin.get("sub", "?")),
        body.force,
        body.dry_run,
        body.threshold,
    )

    background_tasks.add_task(
        _run_retrain_subprocess,
        force=body.force,
        dry_run=body.dry_run,
        threshold=body.threshold,
    )

    flags: list[str] = []
    if body.force:
        flags.append("--force")
    if body.dry_run:
        flags.append("--dry-run")
    flags.append(f"--threshold={body.threshold}")

    return RetrainResponse(
        status="retraining_started",
        message=f"Retraining started in background ({' '.join(flags)}). Check GET /api/stats/model-status for results.",
    )


# ---------------------------------------------------------------------------
# POST /api/admin/populate-project-types  (Phase 7.x)
# ---------------------------------------------------------------------------
# Runs scripts/populate_project_types.py as a subprocess background task.
# Only updates projects where project_type IS NULL, so it is safe to call
# multiple times (subsequent calls are no-ops once all rows are classified).


def _run_populate_types_subprocess(dry_run: bool) -> None:
    """Run scripts/populate_project_types.py in a subprocess (background task body).

    Called from a FastAPI BackgroundTask — errors are logged, not raised.
    """
    cmd = [sys.executable, str(_POPULATE_TYPES_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")

    logger.info("Starting populate-project-types subprocess: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # classification is fast — 2 min hard cap
            cwd=str(_ROOT),
        )
        if result.returncode == 0:
            logger.info("populate-project-types subprocess finished successfully:\n%s", result.stdout[-3000:])
        else:
            logger.warning(
                "populate-project-types subprocess exited with code %d\nstdout:\n%s\nstderr:\n%s",
                result.returncode,
                result.stdout[-2000:],
                result.stderr[-2000:],
            )
    except subprocess.TimeoutExpired:
        logger.error("populate-project-types subprocess timed out after 120 s")
    except Exception as exc:
        logger.exception("populate-project-types subprocess raised an unexpected error: %s", exc)


@router.post(
    "/populate-project-types",
    response_model=PopulateProjectTypesResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def populate_project_types(
    body: PopulateProjectTypesRequest,
    background_tasks: BackgroundTasks,
    _admin: dict = Depends(require_admin),
) -> PopulateProjectTypesResponse:
    """Classify and populate project_type for all projects where it is NULL (admin only).

    Launches ``scripts/populate_project_types.py`` as a subprocess so the
    endpoint returns immediately with HTTP 202.  The classification uses
    keyword heuristics from ``scripts/classify_project_types.py`` and only
    touches rows where ``project_type IS NULL``, making it safe to run
    multiple times.

    Request body (all optional):

    - **dry_run** — classify and log without writing any DB changes (default: false)
    """
    logger.info(
        "Admin '%s' triggered populate-project-types: dry_run=%s",
        _admin.get("email", _admin.get("sub", "?")),
        body.dry_run,
    )

    background_tasks.add_task(_run_populate_types_subprocess, dry_run=body.dry_run)

    flag_str = "--dry-run" if body.dry_run else "live (writes to DB)"
    return PopulateProjectTypesResponse(
        status="classification_started",
        message=f"Project-type classification started in background ({flag_str}). "
        "Check server logs for the per-type summary when complete.",
    )
