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
    total: float | None = None

    @classmethod
    def from_orm_scope(cls, scope: object) -> ScopeInProjectResponse:
        def _f(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None

        return cls(
            id=scope.id,  # type: ignore[attr-defined]
            tag=scope.tag,  # type: ignore[attr-defined]
            scope_type=str(scope.scope_type) if scope.scope_type else None,  # type: ignore[attr-defined]
            product_name=scope.product_name,  # type: ignore[attr-defined]
            square_footage=_f(scope.square_footage),  # type: ignore[attr-defined]
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

    @classmethod
    def from_orm(cls, project: object, include_scopes: bool = False) -> ProjectResponse:
        orm_scopes = []
        if include_scopes:
            raw_scopes = getattr(project, "scopes", []) or []
            orm_scopes = [ScopeInProjectResponse.from_orm_scope(s) for s in raw_scopes]

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
        )
