"""Routes for vendor price-summary endpoints (Phase 7.3)."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.models import Vendor, VendorQuote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vendors", tags=["vendors"])

# Cutoff date that separates "baseline" quotes from "recent" quotes
_CUTOFF = date(2025, 7, 1)
_MIN_QUOTES = 3
_TOP_N = 10
_ALERT_THRESHOLD = 15.0  # pct


# ---------------------------------------------------------------------------
# GET /api/vendors/price-summary
# ---------------------------------------------------------------------------


@router.get("/price-summary")
async def vendor_price_summary(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return top vendors with average quote amounts and price-change trend.

    For each vendor with at least 3 quotes:
    - baseline_avg = avg total for quotes before 2025-07-01
    - recent_avg   = avg total for quotes on/after 2025-07-01
    - pct_change   = (recent_avg - baseline_avg) / baseline_avg * 100
    - alert        = True if abs(pct_change) > 15 and both windows have ≥ 1 quote

    Returns the top 10 vendors by quote_count, descending.
    """
    # ── All-time aggregates per vendor ────────────────────────────────────
    all_time_stmt = (
        select(
            Vendor.id.label("vendor_id"),
            Vendor.name.label("vendor_name"),
            func.count(VendorQuote.id).label("quote_count"),
            func.avg(VendorQuote.total).label("avg_total"),
        )
        .join(Vendor, VendorQuote.vendor_id == Vendor.id)
        .where(VendorQuote.total.is_not(None), VendorQuote.total > 0)
        .group_by(Vendor.id, Vendor.name)
        .order_by(func.count(VendorQuote.id).desc())
        .limit(_TOP_N * 5)  # over-fetch; filter by min_quotes below
    )
    all_time_result = await db.execute(all_time_stmt)
    all_time_rows = all_time_result.all()

    # Collect vendor IDs that pass the minimum quote count
    qualifying: list[tuple] = [r for r in all_time_rows if int(r.quote_count) >= _MIN_QUOTES]
    if not qualifying:
        return []

    vendor_ids = [r.vendor_id for r in qualifying]

    # ── Baseline window (before cutoff) ───────────────────────────────────
    baseline_stmt = (
        select(
            Vendor.id.label("vendor_id"),
            func.avg(VendorQuote.total).label("baseline_avg"),
            func.count(VendorQuote.id).label("baseline_count"),
        )
        .join(Vendor, VendorQuote.vendor_id == Vendor.id)
        .where(
            Vendor.id.in_(vendor_ids),
            VendorQuote.total.is_not(None),
            VendorQuote.total > 0,
            VendorQuote.quote_date.is_not(None),
            VendorQuote.quote_date < _CUTOFF,
        )
        .group_by(Vendor.id)
    )
    baseline_result = await db.execute(baseline_stmt)
    baseline_map: dict = {r.vendor_id: r for r in baseline_result.all()}

    # ── Recent window (on/after cutoff) ───────────────────────────────────
    recent_stmt = (
        select(
            Vendor.id.label("vendor_id"),
            func.avg(VendorQuote.total).label("recent_avg"),
            func.count(VendorQuote.id).label("recent_count"),
        )
        .join(Vendor, VendorQuote.vendor_id == Vendor.id)
        .where(
            Vendor.id.in_(vendor_ids),
            VendorQuote.total.is_not(None),
            VendorQuote.total > 0,
            VendorQuote.quote_date.is_not(None),
            VendorQuote.quote_date >= _CUTOFF,
        )
        .group_by(Vendor.id)
    )
    recent_result = await db.execute(recent_stmt)
    recent_map: dict = {r.vendor_id: r for r in recent_result.all()}

    # ── Build response ─────────────────────────────────────────────────────
    output: list[dict] = []
    for row in qualifying:
        vid = row.vendor_id
        vname: str = row.vendor_name or "(unknown)"
        quote_count = int(row.quote_count)
        avg_total = float(row.avg_total) if row.avg_total is not None else None

        baseline_row = baseline_map.get(vid)
        recent_row = recent_map.get(vid)

        baseline_avg = float(baseline_row.baseline_avg) if baseline_row and baseline_row.baseline_avg else None
        recent_avg = float(recent_row.recent_avg) if recent_row and recent_row.recent_avg else None
        baseline_count = int(baseline_row.baseline_count) if baseline_row else 0
        recent_count = int(recent_row.recent_count) if recent_row else 0

        pct_change: float | None = None
        alert = False
        alert_message: str | None = None

        if baseline_avg and recent_avg and baseline_avg > 0 and baseline_count >= 1 and recent_count >= 1:
            pct_change = round((recent_avg - baseline_avg) / baseline_avg * 100, 1)
            if abs(pct_change) > _ALERT_THRESHOLD:
                alert = True
                direction = "up" if pct_change > 0 else "down"
                alert_message = f"Prices {direction} ~{abs(pct_change):.0f}% (pre → post mid-2025)"

        # Derive a simple canonical slug from the vendor name
        canonical_name = vname.lower().replace(" ", "_").replace(",", "").replace(".", "")

        entry: dict = {
            "vendor_name": vname,
            "canonical_name": canonical_name,
            "quote_count": quote_count,
            "avg_total": round(avg_total, 2) if avg_total is not None else None,
            "recent_avg": round(recent_avg, 2) if recent_avg is not None else None,
            "baseline_avg": round(baseline_avg, 2) if baseline_avg is not None else None,
            "pct_change": pct_change,
            "alert": alert,
            "alert_message": alert_message,
        }
        output.append(entry)

        if len(output) >= _TOP_N:
            break

    return output
