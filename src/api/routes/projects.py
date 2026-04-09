"""Routes for historical project browsing."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_db
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.projects import ProjectResponse
from src.db.models import Project, Scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    scope_type: str | None = Query(None, description="Filter by scope type (e.g. ACT, AWP)"),
    gc_name: str | None = Query(None, description="Filter by GC name (partial match)"),
    year_from: int | None = Query(None, description="Minimum year (based on quote_date)"),
    year_to: int | None = Query(None, description="Maximum year (based on quote_date)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProjectResponse]:
    """List historical projects with optional filters."""
    base_query = select(Project)

    if scope_type:
        base_query = base_query.where(
            Project.id.in_(select(Scope.project_id).where(Scope.scope_type.cast(String).ilike(scope_type)))
        )

    if gc_name:
        base_query = base_query.where(Project.gc_name.ilike(f"%{gc_name}%"))

    if year_from is not None:
        base_query = base_query.where(func.extract("year", Project.quote_date) >= year_from)

    if year_to is not None:
        base_query = base_query.where(func.extract("year", Project.quote_date) <= year_to)

    # Count total
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total: int = count_result.scalar_one()

    # Fetch page
    page_query = (
        base_query.order_by(Project.created_at.desc()).offset(offset).limit(limit).options(selectinload(Project.scopes))
    )
    result = await db.execute(page_query)
    projects = result.scalars().all()

    items = [ProjectResponse.from_orm(p, include_scopes=True) for p in projects]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# GET /api/projects/gc-names  — distinct non-null GC names for filter dropdown
# ---------------------------------------------------------------------------


@router.get("/gc-names", response_model=list[str])
async def list_gc_names(db: AsyncSession = Depends(get_db)) -> list[str]:
    """Return sorted list of distinct non-null GC names for the filter dropdown."""
    result = await db.execute(
        select(Project.gc_name).where(Project.gc_name.isnot(None)).distinct().order_by(Project.gc_name)
    )
    return [row[0] for row in result.fetchall()]


# ---------------------------------------------------------------------------
# GET /api/projects/{id}
# ---------------------------------------------------------------------------


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Fetch a single project by ID with its scopes."""
    result = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.scopes)))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return ProjectResponse.from_orm(project, include_scopes=True)
