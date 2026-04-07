"""
PriceIndex: Historical cost normalization for Phase 3 ML pipeline.

Adjusts historical scope costs to current dollars by normalizing the labor
component from the rate in force at quote time to the current rate. This
allows the ML model to train on comparable cost data regardless of when the
project was quoted.

Labor Rate History (from docs/ANALYSIS.md):
  $486/day  — lowest observed (pre-2023)
  $504/day  — 2023 – early 2024  (8h x $45 x 1.40 approx)
  $522/day  — early-mid 2024     (8h x $45 x 1.45)
  $540/day  — mid 2024           (8h x $45 x 1.50)
  $558/day  — late 2024-2025     (8h x $45 x 1.55)
  $580–650  — 2025               (various multipliers)
  $725/day  — current            (10h x $50 x 1.45)

Usage (Phase 3 ML integration):
    from src.enrichment.price_indexer import PriceIndex

    idx = PriceIndex()

    # Adjust a single scope's labor cost to current rate
    normalized_labor = idx.normalize_labor(
        man_days=6.0,
        original_rate=522.0,          # rate at quote time
    )

    # Get a full cost-basis dict ready for ML features
    features = idx.cost_features(scope_row)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# Labor rate schedule (ascending). Used when daily_labor_rate is unknown
# but a quote date is available (future use once dates are populated).
# ---------------------------------------------------------------------------
LABOR_RATE_SCHEDULE: list[tuple[str, float]] = [
    ("2020-01-01", 486.0),
    ("2023-01-01", 504.0),
    ("2023-07-01", 522.0),
    ("2024-04-01", 540.0),
    ("2024-09-01", 558.0),
    ("2025-03-01", 580.0),
    ("2026-01-01", 725.0),
]

CURRENT_RATE: float = 725.0  # $/day — normalize everything to this

# Outlier bounds — cost/SF values outside these ranges are flagged
COST_PER_SF_BOUNDS: dict[str, tuple[float, float]] = {
    "ACT": (0.80, 20.0),
    "AWP": (5.0, 60.0),
    "AP": (2.0, 80.0),
    "Baffles": (5.0, 200.0),
    "FW": (1.0, 25.0),
    "SM": (0.5, 50.0),
    "WW": (5.0, 80.0),
    "RPG": (3.0, 300.0),
    "Other": (0.5, 300.0),
}


@dataclass
class NormalizedScope:
    """A scope record with labor costs adjusted to the current rate."""

    scope_id: str
    project_name: str
    scope_type: str
    product_name: str | None

    # Original values
    original_daily_rate: float | None
    man_days: float | None
    square_footage: float | None
    cost_per_unit: float | None  # $/SF material cost before markup
    markup_pct: float | None  # as decimal (e.g. 0.35)
    original_labor: float | None  # total labor price in original dollars
    material_price: float | None
    original_total: float | None

    # Normalized values
    normalized_labor: float | None  # labor recalculated at CURRENT_RATE
    normalization_factor: float | None  # current_rate / original_rate
    normalized_total: float | None  # material_price + normalized_labor + sales_tax (approx)

    # Derived features for ML
    labor_per_sf: float | None  # normalized $/SF labor
    material_per_sf: float | None  # $/SF material cost (cost_per_unit, pre-markup)
    price_per_sf: float | None  # normalized total $/SF
    is_outlier: bool = False
    outlier_reasons: list[str] = field(default_factory=list)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class PriceIndex:
    """
    Normalizes historical scope costs to current labor rates.

    Intended for use in the Phase 3 ML pipeline to produce comparable
    cost features across projects quoted at different labor rates.
    """

    def __init__(self, current_rate: float = CURRENT_RATE) -> None:
        self.current_rate = current_rate

    # ------------------------------------------------------------------
    # Core normalization methods
    # ------------------------------------------------------------------

    def normalize_labor(
        self,
        man_days: float | None = None,
        original_rate: float | None = None,
        original_labor: float | None = None,
    ) -> float | None:
        """
        Return labor cost normalized to self.current_rate.

        Priority:
        1. man_days * current_rate  (most accurate — no assumption needed)
        2. original_labor * (current_rate / original_rate)  (scaling)
        3. None  (insufficient data)
        """
        if man_days is not None and man_days > 0:
            return round(man_days * self.current_rate, 2)
        if original_labor is not None and original_rate and original_rate > 0:
            factor = self.current_rate / original_rate
            return round(original_labor * factor, 2)
        return None

    def normalization_factor(self, original_rate: float | None) -> float | None:
        """Return the multiplier to convert original-rate labor to current rate."""
        if original_rate and original_rate > 0:
            return round(self.current_rate / original_rate, 4)
        return None

    def rate_from_date(self, quote_date_str: str | None) -> float:
        """
        Look up the labor rate that was in effect on a given date string (ISO format).
        Falls back to current rate if date is None or unparseable.

        This enables forward use once the DB quote_date fields are populated.
        """
        if quote_date_str is None:
            return self.current_rate
        try:
            from datetime import date

            target = date.fromisoformat(str(quote_date_str))
            applicable_rate = LABOR_RATE_SCHEDULE[0][1]
            for dt_str, rate in LABOR_RATE_SCHEDULE:
                if target >= date.fromisoformat(dt_str):
                    applicable_rate = rate
                else:
                    break
            return applicable_rate
        except (ValueError, TypeError):
            return self.current_rate

    # ------------------------------------------------------------------
    # Scope-level normalization
    # ------------------------------------------------------------------

    def normalize_scope(self, row: dict[str, Any]) -> NormalizedScope:
        """
        Accept a raw scope dict (from DB or extracted JSON) and return
        a NormalizedScope with all values adjusted to current_rate.

        Expected keys (all optional except scope_type):
            scope_id, project_name, scope_type, product_name,
            cost_per_unit, markup_pct, man_days, square_footage,
            daily_labor_rate, labor_price, material_price, total
        """
        scope_type = str(row.get("scope_type", "Other"))
        man_days = _to_float(row.get("man_days"))
        original_rate = _to_float(row.get("daily_labor_rate"))
        original_labor = _to_float(row.get("labor_price"))
        cost_per_unit = _to_float(row.get("cost_per_unit"))
        markup_pct = _to_float(row.get("markup_pct"))
        sf = _to_float(row.get("square_footage"))
        material_price = _to_float(row.get("material_price"))
        original_total = _to_float(row.get("total"))

        norm_labor = self.normalize_labor(man_days, original_rate, original_labor)
        factor = self.normalization_factor(original_rate)

        # Reconstruct normalized total: material_price + norm_labor + ~sales_tax
        # If we can't compute labor, fall back to original total
        if norm_labor is not None and material_price is not None:
            # Approximate 6% sales tax on material_price (most common FL rate)
            approx_tax = material_price * 0.06
            norm_total: float | None = round(material_price + norm_labor + approx_tax, 2)
        else:
            norm_total = original_total

        # Per-SF derived features
        labor_per_sf = round(norm_labor / sf, 4) if (norm_labor and sf and sf > 0) else None
        material_per_sf = cost_per_unit  # already $/SF by definition
        price_per_sf = round(norm_total / sf, 4) if (norm_total and sf and sf > 0) else None

        # Outlier detection
        outlier_reasons: list[str] = []
        is_outlier = False
        if cost_per_unit is not None:
            bounds = COST_PER_SF_BOUNDS.get(scope_type, (0.5, 300.0))
            if cost_per_unit < bounds[0]:
                outlier_reasons.append(f"cost_per_unit {cost_per_unit:.2f} < lower bound {bounds[0]}")
                is_outlier = True
            if cost_per_unit > bounds[1]:
                outlier_reasons.append(f"cost_per_unit {cost_per_unit:.2f} > upper bound {bounds[1]}")
                is_outlier = True
        if markup_pct is not None and not (-0.20 <= markup_pct <= 2.50):
            outlier_reasons.append(f"markup_pct {markup_pct:.2%} outside [-20%, 250%]")
            is_outlier = True

        return NormalizedScope(
            scope_id=str(row.get("scope_id") or row.get("id") or ""),
            project_name=str(row.get("project_name") or ""),
            scope_type=scope_type,
            product_name=row.get("product_name"),
            original_daily_rate=original_rate,
            man_days=man_days,
            square_footage=sf,
            cost_per_unit=cost_per_unit,
            markup_pct=markup_pct,
            original_labor=original_labor,
            material_price=material_price,
            original_total=original_total,
            normalized_labor=norm_labor,
            normalization_factor=factor,
            normalized_total=norm_total,
            labor_per_sf=labor_per_sf,
            material_per_sf=material_per_sf,
            price_per_sf=price_per_sf,
            is_outlier=is_outlier,
            outlier_reasons=outlier_reasons,
        )

    def normalize_batch(self, rows: list[dict[str, Any]]) -> list[NormalizedScope]:
        """Normalize a list of scope dicts."""
        return [self.normalize_scope(r) for r in rows]

    # ------------------------------------------------------------------
    # Feature extraction for ML
    # ------------------------------------------------------------------

    def cost_features(self, row: dict[str, Any]) -> dict[str, float | None]:
        """
        Return a flat feature dict suitable for ML model input.

        All dollar amounts are normalized to current_rate. Categorical fields
        (scope_type, product) are NOT one-hot encoded here — do that in the
        ML pipeline using sklearn's ColumnTransformer.
        """
        ns = self.normalize_scope(row)
        return {
            "scope_type": ns.scope_type,
            "product_name": ns.product_name,
            "square_footage": ns.square_footage,
            "cost_per_sf_material": ns.material_per_sf,
            "markup_pct": ns.markup_pct,
            "man_days": ns.man_days,
            "labor_per_sf_normalized": ns.labor_per_sf,
            "price_per_sf_normalized": ns.price_per_sf,
            "normalization_factor": ns.normalization_factor,
            "is_outlier": ns.is_outlier,
        }

    # ------------------------------------------------------------------
    # Batch utilities
    # ------------------------------------------------------------------

    def filter_valid(
        self,
        normalized: list[NormalizedScope],
        require_cost_per_unit: bool = True,
        require_man_days: bool = False,
        exclude_outliers: bool = False,
    ) -> list[NormalizedScope]:
        """Filter normalized scopes to those suitable for ML training."""
        out = normalized
        if require_cost_per_unit:
            out = [s for s in out if s.cost_per_unit is not None]
        if require_man_days:
            out = [s for s in out if s.man_days is not None]
        if exclude_outliers:
            out = [s for s in out if not s.is_outlier]
        return out

    def to_training_records(
        self,
        normalized: list[NormalizedScope],
        scope_type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert NormalizedScope list to training record dicts.

        Each record contains only the features and target(s) needed for ML:
          Features: square_footage, cost_per_sf_material, markup_pct, man_days
          Targets:  price_per_sf_normalized, normalized_labor
        """
        records = normalized
        if scope_type_filter:
            records = [r for r in records if r.scope_type == scope_type_filter]
        return [
            {
                "scope_id": r.scope_id,
                "project": r.project_name,
                "scope_type": r.scope_type,
                "product_name": r.product_name,
                # Features
                "square_footage": r.square_footage,
                "cost_per_sf_material": r.material_per_sf,
                "markup_pct": r.markup_pct,
                "man_days": r.man_days,
                "normalization_factor": r.normalization_factor,
                # Targets
                "price_per_sf_normalized": r.price_per_sf,
                "normalized_labor_total": r.normalized_labor,
                "is_outlier": r.is_outlier,
            }
            for r in records
        ]
