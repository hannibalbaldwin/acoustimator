"""Routes for aggregate statistics endpoints."""

from __future__ import annotations

import calendar
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.models import Estimate, Project, Scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])

_MAIN_SCOPE_TYPES = {"ACT", "AWP", "FW", "SM"}
_YEAR_MIN = 2020
_YEAR_MAX = 2026


# ---------------------------------------------------------------------------
# GET /api/stats/cost-trends
# ---------------------------------------------------------------------------


@router.get("/cost-trends")
async def cost_trends(
    granularity: Literal["year", "quarter", "month"] = Query("year", description="Time bucket size"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Return average cost-per-SF grouped by time bucket and scope type.

    The ``granularity`` parameter controls the time bucket size:
    - ``year``    — one row per calendar year (default)
    - ``quarter`` — one row per calendar quarter (e.g. "2025 Q1")
    - ``month``   — one row per calendar month (e.g. "Jan '25")

    Only years 2020-2026 and scope types ACT, AWP, FW, SM are included.
    The ``_count`` field on each bucket reflects the number of distinct projects
    and can be used by the frontend to mute sparse buckets (< 3 projects).
    """
    year_col = func.extract("year", Project.quote_date).label("year")
    scope_col = Scope.scope_type.cast(String).label("scope_type")
    avg_col = func.avg(Scope.cost_per_unit).label("avg_cost_per_sf")
    count_col = func.count(func.distinct(Project.id)).label("project_count")

    base_where = [
        Scope.cost_per_unit.is_not(None),
        Scope.cost_per_unit > 0,
        Project.quote_date.is_not(None),
        func.extract("year", Project.quote_date) >= _YEAR_MIN,
        func.extract("year", Project.quote_date) <= _YEAR_MAX,
        Scope.scope_type.cast(String).in_(list(_MAIN_SCOPE_TYPES)),
    ]

    if granularity == "year":
        stmt = (
            select(year_col, scope_col, avg_col, count_col)
            .join(Project, Scope.project_id == Project.id)
            .where(*base_where)
            .group_by(func.extract("year", Project.quote_date), Scope.scope_type.cast(String))
            .order_by(func.extract("year", Project.quote_date).asc())
        )
    elif granularity == "quarter":
        quarter_col = func.extract("quarter", Project.quote_date).label("quarter")
        stmt = (
            select(year_col, quarter_col, scope_col, avg_col, count_col)
            .join(Project, Scope.project_id == Project.id)
            .where(*base_where)
            .group_by(
                func.extract("year", Project.quote_date),
                func.extract("quarter", Project.quote_date),
                Scope.scope_type.cast(String),
            )
            .order_by(
                func.extract("year", Project.quote_date).asc(),
                func.extract("quarter", Project.quote_date).asc(),
            )
        )
    else:  # month
        month_col = func.extract("month", Project.quote_date).label("month")
        stmt = (
            select(year_col, month_col, scope_col, avg_col, count_col)
            .join(Project, Scope.project_id == Project.id)
            .where(*base_where)
            .group_by(
                func.extract("year", Project.quote_date),
                func.extract("month", Project.quote_date),
                Scope.scope_type.cast(String),
            )
            .order_by(
                func.extract("year", Project.quote_date).asc(),
                func.extract("month", Project.quote_date).asc(),
            )
        )

    result = await db.execute(stmt)
    rows = result.all()

    bucket_map: dict[str, dict] = {}
    for row in rows:
        scope = row.scope_type
        avg_val = float(row.avg_cost_per_sf) if row.avg_cost_per_sf is not None else None
        proj_count = int(row.project_count) if row.project_count is not None else 0
        if scope not in _MAIN_SCOPE_TYPES or avg_val is None:
            continue

        # Build the label key
        year = int(row.year)
        if granularity == "year":
            label = str(year)
        elif granularity == "quarter":
            quarter = int(row.quarter)
            label = f"{year} Q{quarter}"
        else:  # month
            month = int(row.month)
            month_abbr = calendar.month_abbr[month]  # 'Jan', 'Feb', …
            label = f"{month_abbr} '{str(year)[2:]}"  # "Jan '25"

        if label not in bucket_map:
            bucket_map[label] = {"date": label, "_count": proj_count}
        else:
            # Keep the max count seen across scope types for this bucket
            bucket_map[label]["_count"] = max(bucket_map[label]["_count"], proj_count)

        bucket_map[label][scope] = round(avg_val, 2)

    return sorted(bucket_map.values(), key=lambda d: d["date"])


# ---------------------------------------------------------------------------
# GET /api/stats/summary
# ---------------------------------------------------------------------------

# TypeScript shape for the frontend team:
#
# interface StatsSummary {
#   total_projects: number;        // integer
#   active_estimates: number;      // integer
#   avg_act_cost_per_sf: number | null;   // float, null if no data
#   total_historical_sf: number | null;   // float, null if no data
# }


@router.get("/summary")
async def stats_summary(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return high-level aggregate statistics for the dashboard.

    - total_projects: COUNT(*) from projects
    - active_estimates: COUNT(*) from estimates WHERE status != 'exported'
    - avg_act_cost_per_sf: AVG cost_per_unit for ACT scopes (0 < value < 50)
    - total_historical_sf: SUM square_footage across all scopes
    """
    # 1. total_projects
    total_projects_result = await db.execute(select(func.count()).select_from(Project))
    total_projects: int = total_projects_result.scalar_one()

    # 2. active_estimates — status is a StrEnum stored as a varchar; cast to String for comparison
    active_estimates_result = await db.execute(
        select(func.count()).select_from(Estimate).where(Estimate.status.cast(String) != "exported")
    )
    active_estimates: int = active_estimates_result.scalar_one()

    # 3. avg_act_cost_per_sf — ACT scopes only, cap outliers at $50/SF
    avg_act_result = await db.execute(
        select(func.avg(Scope.cost_per_unit)).where(
            Scope.scope_type.cast(String) == "ACT",
            Scope.cost_per_unit > 0,
            Scope.cost_per_unit < 50,
        )
    )
    avg_act_raw = avg_act_result.scalar_one()
    avg_act_cost_per_sf = round(float(avg_act_raw), 2) if avg_act_raw is not None else None

    # 4. total_historical_sf — sum of all scope square_footages
    total_sf_result = await db.execute(select(func.sum(Scope.square_footage)).where(Scope.square_footage.is_not(None)))
    total_sf_raw = total_sf_result.scalar_one()
    total_historical_sf = round(float(total_sf_raw), 0) if total_sf_raw is not None else None

    return {
        "total_projects": total_projects,
        "active_estimates": active_estimates,
        "avg_act_cost_per_sf": avg_act_cost_per_sf,
        "total_historical_sf": total_historical_sf,
    }
