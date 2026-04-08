"""Pydantic schemas for export and quote endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExportResponse(BaseModel):
    """Response metadata after triggering an export (unused for StreamingResponse)."""

    estimate_id: str
    filename: str


class QuoteRequest(BaseModel):
    """Body for POST /api/estimates/{id}/quote."""

    template: Literal["T-004A", "T-004B", "T-004E"]


class QuoteResponse(BaseModel):
    """Stub quote response — full implementation in Phase 6.5."""

    quote_id: str
    template: str
    message: str
