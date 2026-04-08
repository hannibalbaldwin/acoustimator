"""Routes for aggregate statistics endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.models import Project, Scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])

_MAIN_SCOPE_TYPES = {"ACT", "AWP", "FW", "SM"}
_YEAR_MIN = 2020
_YEAR_MAX = 2025


# ---------------------------------------------------------------------------
# GET /api/stats/cost-trends
# ---------------------------------------------------------------------------


@router.get("/cost-trends")
async def cost_trends(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Return average cost-per-SF grouped by year and scope type.

    Only years 2020-2025 and scope types ACT, AWP, FW, SM are included.
    """
    # Join scopes → projects, filter valid rows, group by year + scope_type
    stmt = (
        select(
            func.extract("year", Project.quote_date).label("year"),
            Scope.scope_type.cast(str).label("scope_type"),
            func.avg(Scope.cost_per_unit).label("avg_cost_per_sf"),
        )
        .join(Project, Scope.project_id == Project.id)
        .where(
            Scope.cost_per_unit.is_not(None),
            Scope.cost_per_unit > 0,
            Project.quote_date.is_not(None),
            func.extract("year", Project.quote_date) >= _YEAR_MIN,
            func.extract("year", Project.quote_date) <= _YEAR_MAX,
            Scope.scope_type.cast(str).in_(list(_MAIN_SCOPE_TYPES)),
        )
        .group_by(
            func.extract("year", Project.quote_date),
            Scope.scope_type.cast(str),
        )
        .order_by(func.extract("year", Project.quote_date).asc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Build a dict keyed by year string
    year_map: dict[str, dict] = {}
    for row in rows:
        year_str = str(int(row.year))
        scope = row.scope_type
        avg_val = float(row.avg_cost_per_sf) if row.avg_cost_per_sf is not None else None
        if scope not in _MAIN_SCOPE_TYPES or avg_val is None:
            continue
        if year_str not in year_map:
            year_map[year_str] = {"date": year_str}
        year_map[year_str][scope] = round(avg_val, 2)

    return sorted(year_map.values(), key=lambda d: d["date"])
