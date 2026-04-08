"""Pydantic schemas for estimate endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScopeResponse(BaseModel):
    """A single scope line item within an estimate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_id: UUID
    tag: str | None = None
    scope_type: str | None = None
    product_name: str | None = None
    square_footage: float | None = None
    material_cost: float | None = None
    markup_pct: float | None = None
    man_days: float | None = None
    labor_price: float | None = None
    total: float | None = None
    confidence_score: float | None = None
    ai_notes: str | None = None
    room_name: str | None = None
    floor: str | None = None
    building: str | None = None
    manually_adjusted: bool = False

    @classmethod
    def from_orm_scope(cls, scope: object) -> ScopeResponse:
        """Convert an EstimateScope ORM object, casting Decimal → float."""

        def _f(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None

        return cls(
            id=scope.id,  # type: ignore[attr-defined]
            estimate_id=scope.estimate_id,  # type: ignore[attr-defined]
            tag=scope.tag,  # type: ignore[attr-defined]
            scope_type=scope.scope_type,  # type: ignore[attr-defined]
            product_name=scope.product_name,  # type: ignore[attr-defined]
            square_footage=_f(scope.square_footage),  # type: ignore[attr-defined]
            material_cost=_f(scope.material_cost),  # type: ignore[attr-defined]
            markup_pct=_f(scope.markup_pct),  # type: ignore[attr-defined]
            man_days=_f(scope.man_days),  # type: ignore[attr-defined]
            labor_price=_f(scope.labor_price),  # type: ignore[attr-defined]
            total=_f(scope.total),  # type: ignore[attr-defined]
            confidence_score=_f(scope.confidence_score),  # type: ignore[attr-defined]
            ai_notes=scope.ai_notes,  # type: ignore[attr-defined]
            room_name=scope.room_name,  # type: ignore[attr-defined]
            floor=scope.floor,  # type: ignore[attr-defined]
            building=scope.building,  # type: ignore[attr-defined]
            manually_adjusted=scope.manually_adjusted,  # type: ignore[attr-defined]
        )


class ComparableProjectResponse(BaseModel):
    """Enriched comparable project returned within an EstimateResponse."""

    id: str
    folder_name: str
    scope_type: str | None = None
    area_sf: float | None = None
    cost_per_sf: float | None = None
    total_cost: float | None = None
    year: int | None = None
    similarity_score: float = 0.0


class EstimateResponse(BaseModel):
    """Full estimate returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_name: str
    gc_name: str | None = None
    address: str | None = None
    status: str
    total_cost: float | None = None
    total_sf: float | None = None
    cost_per_sf: float | None = None
    man_days: float | None = None
    confidence_score: float | None = None
    confidence_level: str | None = None
    created_at: datetime
    scopes: list[ScopeResponse] = []
    comparable_projects: list[ComparableProjectResponse] = []

    @classmethod
    def from_orm(cls, estimate: object, scopes: list[object] | None = None) -> EstimateResponse:
        """Build an EstimateResponse from an Estimate ORM object."""

        def _f(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None

        total_cost = _f(estimate.total_estimate)  # type: ignore[attr-defined]
        # total_area_sf may not be a column; try attribute gracefully
        total_sf_val: float | None = None
        try:
            total_sf_val = _f(estimate.total_area_sf)  # type: ignore[attr-defined]
        except AttributeError:
            pass

        cost_per_sf: float | None = None
        if total_cost and total_sf_val and total_sf_val > 0:
            cost_per_sf = total_cost / total_sf_val

        confidence_score_raw = estimate.overall_confidence  # type: ignore[attr-defined]
        confidence_score = _f(confidence_score_raw)

        confidence_level: str | None = None
        if confidence_score is not None:
            if confidence_score >= 0.8:
                confidence_level = "high"
            elif confidence_score >= 0.5:
                confidence_level = "medium"
            else:
                confidence_level = "low"

        orm_scopes = scopes if scopes is not None else []
        scope_responses = [ScopeResponse.from_orm_scope(s) for s in orm_scopes]

        return cls(
            id=estimate.id,  # type: ignore[attr-defined]
            project_name=estimate.name,  # type: ignore[attr-defined]
            gc_name=estimate.gc_name,  # type: ignore[attr-defined]
            address=estimate.project_address,  # type: ignore[attr-defined]
            status=str(estimate.status) if estimate.status else "draft",  # type: ignore[attr-defined]
            total_cost=total_cost,
            total_sf=total_sf_val,
            cost_per_sf=cost_per_sf,
            man_days=None,  # computed from scopes if needed
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            created_at=estimate.created_at,  # type: ignore[attr-defined]
            scopes=scope_responses,
            comparable_projects=[],
        )


class EstimateListItem(BaseModel):
    """Lightweight estimate summary for the list endpoint."""

    id: UUID
    project_name: str
    gc_name: str | None = None
    status: str
    total_cost: float | None = None
    confidence_level: str | None = None
    created_at: datetime
    scope_types: list[str] = []


class CreateEstimateRequest(BaseModel):
    """Non-file fields for POST /api/estimates (parsed from form data)."""

    project_name: str
    gc_name: str | None = None
    address: str | None = None
    scope_type_hints: list[str] = []


class UpdateScopeRequest(BaseModel):
    """Body for PATCH /api/estimates/{id}/scopes/{scope_id}."""

    product_name: str | None = None
    area_sf: float | None = None
    material_cost_per_sf: float | None = None
    markup_pct: float | None = None
    labor_days: float | None = None
    is_accepted: bool | None = None
