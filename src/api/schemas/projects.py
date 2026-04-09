"""Pydantic schemas for project endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScopeInProjectResponse(BaseModel):
    """Lightweight scope representation for project detail views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag: str | None = None
    scope_type: str | None = None
    product_name: str | None = None
    square_footage: float | None = None
    area_sf: float | None = None
    cost_per_sf: float | None = None
    total: float | None = None

    @classmethod
    def from_orm_scope(cls, scope: object) -> ScopeInProjectResponse:
        def _f(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None

        sq_ft = _f(scope.square_footage)  # type: ignore[attr-defined]
        cpu = _f(scope.cost_per_unit) if hasattr(scope, "cost_per_unit") else None  # type: ignore[attr-defined]

        return cls(
            id=scope.id,  # type: ignore[attr-defined]
            tag=scope.tag,  # type: ignore[attr-defined]
            scope_type=str(scope.scope_type) if scope.scope_type else None,  # type: ignore[attr-defined]
            product_name=scope.product_name,  # type: ignore[attr-defined]
            square_footage=sq_ft,
            area_sf=sq_ft,
            cost_per_sf=cpu,
            total=_f(scope.total),  # type: ignore[attr-defined]
        )


class ProjectResponse(BaseModel):
    """Project as returned from GET /api/projects."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    gc_name: str | None = None
    address: str | None = None
    status: str | None = None
    project_type: str | None = None
    quote_date: date | None = None
    created_at: datetime
    scopes: list[ScopeInProjectResponse] = []
    scope_types: list[str] = []
    total_cost: float | None = None

    @classmethod
    def from_orm(cls, project: object, include_scopes: bool = False) -> ProjectResponse:
        orm_scopes = []
        if include_scopes:
            raw_scopes = getattr(project, "scopes", []) or []
            orm_scopes = [ScopeInProjectResponse.from_orm_scope(s) for s in raw_scopes]

        raw_scopes_all = getattr(project, "scopes", []) or []
        scope_types = list({str(s.scope_type) for s in raw_scopes_all if s.scope_type})
        total_cost_val = sum(float(s.total) for s in raw_scopes_all if s.total) or None

        return cls(
            id=project.id,  # type: ignore[attr-defined]
            name=project.name,  # type: ignore[attr-defined]
            gc_name=project.gc_name,  # type: ignore[attr-defined]
            address=project.address,  # type: ignore[attr-defined]
            status=str(project.status) if project.status else None,  # type: ignore[attr-defined]
            project_type=str(project.project_type) if project.project_type else None,  # type: ignore[attr-defined]
            quote_date=project.quote_date,  # type: ignore[attr-defined]
            created_at=project.created_at,  # type: ignore[attr-defined]
            scopes=orm_scopes,
            scope_types=scope_types,
            total_cost=total_cost_val,
        )
