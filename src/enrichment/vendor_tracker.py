"""Vendor cost tracking and analysis for Acoustimator.

Provides the VendorCostTracker class for querying vendor quote history,
summarising preferred vendors by product type, and detecting price changes
across quotes.

Usage:
    from src.enrichment.vendor_tracker import VendorCostTracker
    from src.db.session import async_session

    async with async_session() as session:
        tracker = VendorCostTracker(session)
        summary = await tracker.get_vendor_summary()
        changes = await tracker.detect_price_changes(threshold_pct=10)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class PricePoint:
    """A single price observation for a product from a vendor quote."""

    quote_date: str | None
    vendor_name: str | None
    product: str
    sku: str | None
    unit: str | None
    unit_cost: Decimal | None
    total: Decimal | None
    quote_number: str | None
    source_file: str | None
    project_name: str | None


@dataclass
class VendorSummary:
    """Aggregated statistics for a single vendor."""

    vendor_name: str
    quote_count: int
    total_line_items: int
    avg_quote_total: Decimal | None
    min_quote_total: Decimal | None
    max_quote_total: Decimal | None
    avg_freight: Decimal | None
    freight_pct_of_total: Decimal | None  # avg freight / avg total * 100
    products_quoted: list[str] = field(default_factory=list)
    date_range: tuple[str | None, str | None] = (None, None)


@dataclass
class PriceChangeAlert:
    """A detected price change for a product across quotes."""

    product: str
    vendor_name: str | None
    sku: str | None
    unit: str | None
    earlier_date: str | None
    later_date: str | None
    earlier_unit_cost: Decimal
    later_unit_cost: Decimal
    change_pct: float  # positive = increase, negative = decrease
    earlier_source: str | None
    later_source: str | None


# ---------------------------------------------------------------------------
# VendorCostTracker
# ---------------------------------------------------------------------------


class VendorCostTracker:
    """Query and analyse vendor pricing data from the vendor_quotes table.

    All methods are async and expect an open AsyncSession.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_price_history(
        self,
        product_name: str,
        vendor_name: str | None = None,
    ) -> list[PricePoint]:
        """Return time-series of unit prices for a product across all quotes.

        Searches the items JSONB column for line items where the product field
        contains *product_name* (case-insensitive substring match).

        Args:
            product_name: Substring to match against item.product.
            vendor_name:  Optional vendor name filter (case-insensitive).

        Returns:
            List of PricePoint ordered by quote_date ascending (nulls last).
        """
        vendor_filter = ""
        if vendor_name:
            vendor_filter = "AND LOWER(v.name) LIKE LOWER(:vendor_like)"

        sql = text(f"""
            SELECT
                vq.quote_date,
                vq.quote_number,
                vq.source_file,
                v.name AS vendor_name,
                p.name AS project_name,
                item->>'product'   AS product,
                item->>'sku'       AS sku,
                item->>'unit'      AS unit,
                item->>'unit_cost' AS unit_cost,
                item->>'total'     AS total
            FROM vendor_quotes vq
            LEFT JOIN vendors v    ON vq.vendor_id   = v.id
            LEFT JOIN projects p   ON vq.project_id  = p.id
            CROSS JOIN LATERAL jsonb_array_elements(vq.items) AS item
            WHERE LOWER(item->>'product') LIKE LOWER(:product_like)
              {vendor_filter}
            ORDER BY vq.quote_date ASC NULLS LAST
        """)

        params: dict[str, Any] = {"product_like": f"%{product_name}%"}
        if vendor_name:
            params["vendor_like"] = f"%{vendor_name}%"

        result = await self._session.execute(sql, params)
        rows = result.mappings().all()

        points: list[PricePoint] = []
        for row in rows:
            unit_cost = None
            if row["unit_cost"] is not None:
                try:
                    unit_cost = Decimal(str(row["unit_cost"]))
                except Exception:
                    pass
            total = None
            if row["total"] is not None:
                try:
                    total = Decimal(str(row["total"]))
                except Exception:
                    pass
            points.append(
                PricePoint(
                    quote_date=str(row["quote_date"]) if row["quote_date"] else None,
                    vendor_name=row["vendor_name"],
                    product=row["product"] or "",
                    sku=row["sku"],
                    unit=row["unit"],
                    unit_cost=unit_cost,
                    total=total,
                    quote_number=row["quote_number"],
                    source_file=row["source_file"],
                    project_name=row["project_name"],
                )
            )
        return points

    async def get_vendor_summary(self) -> list[VendorSummary]:
        """Return aggregated statistics per vendor, ordered by quote count desc.

        Includes:
          - quote count and total quote value stats
          - average freight and freight-as-percent-of-total
          - distinct products quoted (up to 10 per vendor)
          - earliest and latest quote dates
        """
        # Main aggregates
        agg_sql = text("""
            SELECT
                COALESCE(v.name, '(unknown)') AS vendor_name,
                COUNT(vq.id)                  AS quote_count,
                AVG(vq.total)                 AS avg_total,
                MIN(vq.total)                 AS min_total,
                MAX(vq.total)                 AS max_total,
                AVG(vq.freight)               AS avg_freight,
                TO_CHAR(MIN(vq.quote_date), 'YYYY-MM-DD') AS earliest_date,
                TO_CHAR(MAX(vq.quote_date), 'YYYY-MM-DD') AS latest_date
            FROM vendor_quotes vq
            LEFT JOIN vendors v ON vq.vendor_id = v.id
            GROUP BY COALESCE(v.name, '(unknown)')
            ORDER BY quote_count DESC
        """)

        agg_result = await self._session.execute(agg_sql)
        agg_rows = agg_result.mappings().all()

        # Line-item counts and distinct products per vendor
        items_sql = text("""
            SELECT
                COALESCE(v.name, '(unknown)') AS vendor_name,
                COUNT(item)                   AS total_items,
                ARRAY_AGG(DISTINCT item->>'product')
                    FILTER (WHERE item->>'product' IS NOT NULL) AS products
            FROM vendor_quotes vq
            LEFT JOIN vendors v ON vq.vendor_id = v.id
            CROSS JOIN LATERAL jsonb_array_elements(vq.items) AS item
            GROUP BY COALESCE(v.name, '(unknown)')
        """)

        items_result = await self._session.execute(items_sql)
        items_map: dict[str, dict] = {
            row["vendor_name"]: dict(row) for row in items_result.mappings().all()
        }

        summaries: list[VendorSummary] = []
        for row in agg_rows:
            vname = row["vendor_name"]
            item_data = items_map.get(vname, {})
            products = item_data.get("products") or []

            avg_total = Decimal(str(row["avg_total"])) if row["avg_total"] is not None else None
            avg_freight = (
                Decimal(str(row["avg_freight"])) if row["avg_freight"] is not None else None
            )

            freight_pct: Decimal | None = None
            if avg_total and avg_freight and avg_total > 0:
                freight_pct = (avg_freight / avg_total * 100).quantize(Decimal("0.1"))

            summaries.append(
                VendorSummary(
                    vendor_name=vname,
                    quote_count=int(row["quote_count"]),
                    total_line_items=int(item_data.get("total_items", 0)),
                    avg_quote_total=avg_total,
                    min_quote_total=(
                        Decimal(str(row["min_total"])) if row["min_total"] is not None else None
                    ),
                    max_quote_total=(
                        Decimal(str(row["max_total"])) if row["max_total"] is not None else None
                    ),
                    avg_freight=avg_freight,
                    freight_pct_of_total=freight_pct,
                    products_quoted=products[:10],  # cap at 10 for display
                    date_range=(row["earliest_date"], row["latest_date"]),
                )
            )
        return summaries

    async def detect_price_changes(
        self,
        threshold_pct: float = 10.0,
    ) -> list[PriceChangeAlert]:
        """Flag products where unit_cost changed more than threshold_pct between quotes.

        Compares all pairs of line items for the same (product, unit) combination
        from quotes with known dates. Only considers items with a non-null unit_cost.

        Args:
            threshold_pct: Minimum percentage change to flag (default 10%).

        Returns:
            List of PriceChangeAlert objects sorted by abs(change_pct) descending.
        """
        # Pull all dated line items with unit_cost
        sql = text("""
            SELECT
                vq.quote_date,
                vq.source_file,
                v.name AS vendor_name,
                item->>'product'   AS product,
                item->>'sku'       AS sku,
                item->>'unit'      AS unit,
                (item->>'unit_cost')::numeric AS unit_cost
            FROM vendor_quotes vq
            LEFT JOIN vendors v ON vq.vendor_id = v.id
            CROSS JOIN LATERAL jsonb_array_elements(vq.items) AS item
            WHERE vq.quote_date IS NOT NULL
              AND item->>'unit_cost' IS NOT NULL
              AND (item->>'unit_cost')::numeric > 0
              AND item->>'product' IS NOT NULL
            ORDER BY item->>'product', vq.quote_date
        """)

        result = await self._session.execute(sql)
        rows = result.mappings().all()

        # Group by (normalized product, unit, vendor)
        from collections import defaultdict

        groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows:
            key = (
                (row["product"] or "").strip().lower()[:80],
                (row["unit"] or "").strip().upper(),
                (row["vendor_name"] or "(unknown)"),
            )
            groups[key].append(dict(row))

        alerts: list[PriceChangeAlert] = []

        for (product_key, unit, vendor), observations in groups.items():
            # Sort by date; need at least 2 observations
            observations.sort(key=lambda r: str(r["quote_date"]))
            if len(observations) < 2:
                continue

            # Compare consecutive observations
            for i in range(len(observations) - 1):
                earlier = observations[i]
                later = observations[i + 1]

                try:
                    cost_a = Decimal(str(earlier["unit_cost"]))
                    cost_b = Decimal(str(later["unit_cost"]))
                except Exception:
                    continue

                if cost_a == 0:
                    continue

                change_pct = float((cost_b - cost_a) / cost_a * 100)

                if abs(change_pct) >= threshold_pct:
                    alerts.append(
                        PriceChangeAlert(
                            product=earlier["product"] or product_key,
                            vendor_name=vendor if vendor != "(unknown)" else None,
                            sku=earlier.get("sku"),
                            unit=unit or None,
                            earlier_date=str(earlier["quote_date"]),
                            later_date=str(later["quote_date"]),
                            earlier_unit_cost=cost_a,
                            later_unit_cost=cost_b,
                            change_pct=round(change_pct, 1),
                            earlier_source=earlier.get("source_file"),
                            later_source=later.get("source_file"),
                        )
                    )

        alerts.sort(key=lambda a: abs(a.change_pct), reverse=True)
        return alerts

    async def get_preferred_vendors_by_category(self) -> dict[str, list[str]]:
        """Return top vendors by product keyword category based on quote frequency.

        Categories are heuristically derived from product name keywords common
        in the acoustics industry.

        Returns:
            Dict mapping category label to sorted list of vendor names.
        """
        keyword_map = {
            "Ceiling Tile (ACT)": ["armstrong", "ultima", "lyra", "dune", "optima", "tile"],
            "Wall Panel / Fabric": ["panel", "fabric", "snap-tex", "koroseal", "mdc", "dwp"],
            "Grid / Suspension": ["grid", "tee", "main beam", "cross tee", "prelude", "suprafine"],
            "Wood Ceiling": ["wood", "9wood", "plank", "solo", "akuwood"],
            "Felt / Baffle": ["felt", "baffle", "turf", "acoufelt", "autex"],
            "Specialty / Diffuser": ["rpg", "diffuser", "cloud", "j2", "softspan"],
        }

        sql = text("""
            SELECT
                COALESCE(v.name, '(unknown)') AS vendor_name,
                item->>'product' AS product
            FROM vendor_quotes vq
            LEFT JOIN vendors v ON vq.vendor_id = v.id
            CROSS JOIN LATERAL jsonb_array_elements(vq.items) AS item
            WHERE item->>'product' IS NOT NULL
        """)
        result = await self._session.execute(sql)
        rows = result.mappings().all()

        from collections import Counter

        category_vendors: dict[str, Counter] = {cat: Counter() for cat in keyword_map}

        for row in rows:
            product_lower = (row["product"] or "").lower()
            vname = row["vendor_name"]
            for category, keywords in keyword_map.items():
                if any(kw in product_lower for kw in keywords):
                    category_vendors[category][vname] += 1

        return {
            cat: [v for v, _ in counter.most_common(5)]
            for cat, counter in category_vendors.items()
            if counter
        }
