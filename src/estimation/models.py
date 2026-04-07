"""Pydantic models for the Acoustimator estimation output (Phase 5.1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ScopeEstimate(BaseModel):
    """Cost estimate for a single acoustic scope (e.g. ACT-1, AWP-2)."""

    scope_tag: str
    """Tag from the plan, e.g. 'ACT-1'."""

    scope_type: str
    """Scope category: 'ACT', 'AWP', 'FW', etc."""

    area_sf: Decimal | None
    """Measured area in square feet (from plan reader)."""

    product_hint: str | None
    """Product name extracted from the plan, if any."""

    predicted_cost_per_sf: Decimal | None
    """ML-predicted total cost per SF (material + markup + labor amortised)."""

    predicted_markup_pct: Decimal | None
    """ML-predicted markup fraction, e.g. 0.33 = 33 %."""

    predicted_man_days: Decimal | None
    """ML-predicted installation labour in man-days."""

    material_cost: Decimal | None
    """Estimated pre-markup material cost: area_sf × (cost_per_sf / (1 + markup_pct))."""

    labor_cost: Decimal | None
    """Estimated labour cost: predicted_man_days × daily_labor_rate."""

    total: Decimal | None
    """material_cost × (1 + markup_pct) + labor_cost + material_cost × sales_tax_pct."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Combined confidence: 0.6 × plan_confidence + 0.4 × model_confidence."""

    model_used: str
    """Which cost model produced the cost/SF prediction, e.g. 'ACT_cost_model'."""

    comparable_projects: list[str] = Field(default_factory=list)
    """Top-3 historical project names with similar scope type and area."""


class ProjectEstimate(BaseModel):
    """Full project-level estimate assembled from all scopes."""

    source_plan: str
    """Absolute path to the source PDF."""

    extraction_confidence: float = Field(ge=0.0, le=1.0)
    """Overall plan-reading confidence from PlanReadResult."""

    scope_estimates: list[ScopeEstimate]
    """Per-scope estimates (only scopes that passed quality filters)."""

    total_estimated_cost: Decimal
    """Sum of all scope totals."""

    total_area_sf: Decimal | None
    """Total measured area across all scopes (or from plan reader aggregate)."""

    estimated_man_days: Decimal
    """Sum of all scope man-days."""

    notes: list[str] = Field(default_factory=list)
    """Warnings, low-confidence flags, fallback notices."""

    created_at: datetime
    """Timestamp when the estimate was generated."""
