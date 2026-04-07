"""Historical project comparison engine for Acoustimator Phase 5.4.

Finds the most similar historical scopes and projects to anchor cost estimates.
Similarity is computed via a weighted feature distance (no ML required).
"""

from __future__ import annotations

import asyncio
import logging
import math
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Project, Scope
from src.db.session import async_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class ComparableProject(BaseModel):
    """A historical project that is similar to the target estimate scope."""

    project_name: str
    folder_name: str | None
    scope_type: str
    area_sf: float
    actual_cost_per_sf: float | None
    actual_markup_pct: float | None
    actual_total: float | None
    similarity_score: float  # 0–1


class ComparableScope(BaseModel):
    """A historical scope line-item that is similar to the target estimate scope."""

    project_name: str
    scope_tag: str | None
    scope_type: str
    area_sf: float
    cost_per_sf: float | None
    markup_pct: float | None
    total: float | None
    similarity_score: float  # 0–1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_float(value: Decimal | float | int | None) -> float | None:
    """Convert Decimal/int to float, returning None for falsy values."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if math.isfinite(f) and f > 0 else None
    except (TypeError, ValueError):
        return None


def _sf_similarity(area_sf: float, ref_sf: float) -> float:
    """Log-ratio SF similarity: 1 / (1 + |log(area_sf / ref_sf)|).

    Returns a value in (0, 1]. Equal sizes → 1.0. Works well across orders of magnitude.
    """
    if area_sf <= 0 or ref_sf <= 0:
        return 0.0
    return 1.0 / (1.0 + abs(math.log(area_sf / ref_sf)))


def _cost_similarity(cost_per_sf: float, ref_cost_per_sf: float) -> float:
    """Relative cost similarity: 1 / (1 + |target - ref| / ref).

    Returns a value in (0, 1]. Equal costs → 1.0.
    """
    if ref_cost_per_sf <= 0:
        return 0.0
    return 1.0 / (1.0 + abs(cost_per_sf - ref_cost_per_sf) / ref_cost_per_sf)


def _compute_similarity(
    scope_type: str,
    area_sf: float,
    cost_per_sf: float | None,
    ref_scope_type: str,
    ref_sf: float,
    ref_cost_per_sf: float | None,
) -> float:
    """Compute weighted similarity score in [0, 1].

    Weights:
        scope_type_match : 0.5
        sf_similarity    : 0.3
        cost_similarity  : 0.2  (skipped and renormalized when cost unknown)
    """
    # Base weights
    w_type = 0.5
    w_sf = 0.3
    w_cost = 0.2

    type_score = 1.0 if scope_type == ref_scope_type else 0.0
    sf_score = _sf_similarity(area_sf, ref_sf)

    if cost_per_sf is not None and ref_cost_per_sf is not None:
        cost_score: float | None = _cost_similarity(cost_per_sf, ref_cost_per_sf)
    else:
        cost_score = None

    if cost_score is None:
        # Renormalize without cost component
        total_w = w_type + w_sf
        if total_w == 0:
            return 0.0
        return (w_type * type_score + w_sf * sf_score) / total_w
    else:
        return w_type * type_score + w_sf * sf_score + w_cost * cost_score


# ---------------------------------------------------------------------------
# Core async functions
# ---------------------------------------------------------------------------


async def find_comparable_projects(
    session: AsyncSession,
    scope_type: str,
    area_sf: float,
    cost_per_sf: float | None = None,
    top_n: int = 3,
) -> list[ComparableProject]:
    """Return the top_n most similar historical projects for the given scope parameters.

    Fetches all scopes (joined with their parent project) and scores each one against
    the target parameters. One comparable is returned per unique project; if a project
    has multiple matching scopes only the highest-scored scope is kept.

    Args:
        session: Active async SQLAlchemy session.
        scope_type: Target scope type string (e.g. "ACT", "AWP").
        area_sf: Target area in square feet.
        cost_per_sf: Predicted $/SF from the estimation model (optional).
        top_n: Number of comparables to return.

    Returns:
        List of ComparableProject sorted by similarity_score descending.
    """
    stmt = select(Scope, Project).join(Project, Scope.project_id == Project.id).where(Scope.square_footage.is_not(None))
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        logger.warning("find_comparable_projects: no scopes found in database")
        return []

    # Aggregate best score per project_id
    best: dict[str, tuple[float, Scope, Project]] = {}  # project_id → (score, scope, project)

    for scope, project in rows:
        ref_sf = _to_float(scope.square_footage)
        if ref_sf is None:
            continue

        ref_scope_type = scope.scope_type.value if scope.scope_type else ""
        ref_cost = _to_float(scope.cost_per_unit)

        score = _compute_similarity(
            scope_type=scope_type,
            area_sf=area_sf,
            cost_per_sf=cost_per_sf,
            ref_scope_type=ref_scope_type,
            ref_sf=ref_sf,
            ref_cost_per_sf=ref_cost,
        )

        project_key = str(project.id)
        if project_key not in best or score > best[project_key][0]:
            best[project_key] = (score, scope, project)

    # Sort by score descending, take top_n
    ranked = sorted(best.values(), key=lambda t: t[0], reverse=True)[:top_n]

    comparables: list[ComparableProject] = []
    for score, scope, project in ranked:
        ref_sf = _to_float(scope.square_footage)
        actual_cost = _to_float(scope.cost_per_unit)
        actual_markup = _to_float(scope.markup_pct)
        actual_total = _to_float(scope.total)

        comparables.append(
            ComparableProject(
                project_name=project.name,
                folder_name=project.folder_name,
                scope_type=scope.scope_type.value if scope.scope_type else "",
                area_sf=ref_sf or 0.0,
                actual_cost_per_sf=actual_cost,
                actual_markup_pct=actual_markup,
                actual_total=actual_total,
                similarity_score=round(score, 4),
            )
        )

    return comparables


async def find_comparable_scopes(
    session: AsyncSession,
    scope_type: str,
    area_sf: float,
    top_n: int = 5,
) -> list[ComparableScope]:
    """Return the top_n most similar historical scope line-items.

    Unlike find_comparable_projects, this returns individual scope rows (multiple
    rows from the same project may appear) and does not factor in cost_per_sf when
    scoring (cost is unknown at query time for this variant).

    Args:
        session: Active async SQLAlchemy session.
        scope_type: Target scope type string (e.g. "ACT", "AWP").
        area_sf: Target area in square feet.
        top_n: Number of comparable scopes to return.

    Returns:
        List of ComparableScope sorted by similarity_score descending.
    """
    stmt = select(Scope, Project).join(Project, Scope.project_id == Project.id).where(Scope.square_footage.is_not(None))
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        logger.warning("find_comparable_scopes: no scopes found in database")
        return []

    scored: list[tuple[float, Scope, Project]] = []

    for scope, project in rows:
        ref_sf = _to_float(scope.square_footage)
        if ref_sf is None:
            continue

        ref_scope_type = scope.scope_type.value if scope.scope_type else ""

        score = _compute_similarity(
            scope_type=scope_type,
            area_sf=area_sf,
            cost_per_sf=None,  # no cost hint in this variant
            ref_scope_type=ref_scope_type,
            ref_sf=ref_sf,
            ref_cost_per_sf=None,
        )
        scored.append((score, scope, project))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:top_n]

    comparables: list[ComparableScope] = []
    for score, scope, project in top:
        ref_sf = _to_float(scope.square_footage)
        cost = _to_float(scope.cost_per_unit)
        markup = _to_float(scope.markup_pct)
        total = _to_float(scope.total)

        comparables.append(
            ComparableScope(
                project_name=project.name,
                scope_tag=scope.tag,
                scope_type=scope.scope_type.value if scope.scope_type else "",
                area_sf=ref_sf or 0.0,
                cost_per_sf=cost,
                markup_pct=markup,
                total=total,
                similarity_score=round(score, 4),
            )
        )

    return comparables


# ---------------------------------------------------------------------------
# Sync wrapper
# ---------------------------------------------------------------------------


def find_comparables_sync(
    scope_type: str,
    area_sf: float,
    cost_per_sf: float | None = None,
    top_n: int = 3,
) -> list[ComparableProject]:
    """Sync wrapper around find_comparable_projects.

    Creates its own database session. Safe to call from non-async contexts
    (e.g. CLI scripts, Jupyter notebooks, synchronous test helpers).

    Args:
        scope_type: Target scope type string (e.g. "ACT", "AWP").
        area_sf: Target area in square feet.
        cost_per_sf: Predicted $/SF (optional).
        top_n: Number of comparables to return.

    Returns:
        List of ComparableProject sorted by similarity_score descending.
    """

    async def _run() -> list[ComparableProject]:
        async with async_session() as session:
            return await find_comparable_projects(
                session=session,
                scope_type=scope_type,
                area_sf=area_sf,
                cost_per_sf=cost_per_sf,
                top_n=top_n,
            )

    return asyncio.run(_run())
