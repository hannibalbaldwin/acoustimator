"""
Feature engineering for Acoustimator cost models (Phase 3.1).

Pulls raw scope + project data from the DB and engineers a training-ready
feature matrix.  The prediction target is cost_per_sf — either:
  - cost_per_unit  (material $/SF, pre-markup)    — primary when available
  - total / square_footage                         — derived total $/SF
Both are stored; `get_training_data` uses total $/SF as the target by default
since that reflects the actual quoted price per SF delivered to the GC.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_LABOR_RATE: float = 725.0  # $/day — normalize all labor to this

# Scope types to include in cost models (exclude SM, Other, RPG standalone)
MODELLED_SCOPE_TYPES: list[str] = ["ACT", "AWP", "AP", "Baffles", "FW", "WW", "RPG"]

# Product tier keyword mapping  (checked in order — first match wins)
PRODUCT_TIER_KEYWORDS: list[tuple[int, list[str]]] = [
    (3, ["woodworks", "wood", "rpg", "specialty", "custom", "curved", "radius"]),
    (
        2,
        [
            "premium",
            "high nrc",
            "clima plus",
            "fine fissured",
            "dune",
            "cortega supreme",
            "mineral fiber",
            "snap-tex",
            "fabricmate",
            "kirei",
            "ultima",
        ],
    ),
    (
        1,
        [
            "standard",
            "cirrus",
            "eclipse",
            "mars",
            "cortega",
            "interlude",
            "prelude",
            "beveled",
            "tegular",
            "2x2",
            "2x4",
            "lay-in",
        ],
    ),
    (0, ["economy", "basic", "budget"]),
]

# Healthcare keywords (project_name / gc_name)
HEALTHCARE_KEYWORDS: list[str] = [
    "hospital",
    "health",
    "medical",
    "baycare",
    "hca",
    "tgh",
    "moffitt",
    "clinic",
    "surgery",
    "rehab",
    "nursing",
    "dental",
    "ortho",
    "pediatric",
    "urology",
    "cardiac",
    "oncology",
    "radiology",
    "pharmacy",
]

# Education keywords
EDUCATION_KEYWORDS: list[str] = [
    "school",
    "university",
    "college",
    "usf",
    "ucf",
    "fau",
    "fsu",
    "elementary",
    "middle school",
    "high school",
    " hs ",
    "academy",
    "charter",
    "campus",
    "classroom",
    "gymnasium",
    "library",
]

# Worship / church keywords
CHURCH_KEYWORDS: list[str] = [
    "church",
    "chapel",
    "parish",
    "sanctuary",
    "faith",
    "worship",
    "cathedral",
    "temple",
    "mosque",
    "synagogue",
    "ministry",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _product_tier(product_name: str | None) -> int:
    """Return 0-3 product tier from product name keywords."""
    if not product_name or not isinstance(product_name, str):
        return 1  # assume standard if unknown
    pn_lower = product_name.lower()
    for tier, kws in PRODUCT_TIER_KEYWORDS:
        if any(kw in pn_lower for kw in kws):
            return tier
    return 1  # default standard


def _keyword_flag(text1: str | None, text2: str | None, keywords: list[str]) -> bool:
    t1 = text1 if isinstance(text1, str) else ""
    t2 = text2 if isinstance(text2, str) else ""
    combined = f"{t1} {t2}".lower()
    return any(kw in combined for kw in keywords)


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------


async def _fetch_all_scopes() -> list[dict[str, Any]]:
    """Async fetch all scopes joined with project data from the DB."""
    from sqlalchemy import text

    from src.db.session import async_session

    async with async_session() as s:
        rows = await s.execute(
            text("""
            SELECT
                s.id,
                s.scope_type,
                s.tag       AS scope_tag,
                s.product_name,
                s.square_footage,
                s.cost_per_unit,
                s.markup_pct,
                s.man_days,
                s.labor_price,
                s.material_cost,
                s.material_price,
                s.total,
                s.daily_labor_rate,
                p.name         AS project_name,
                p.gc_name,
                p.project_type,
                p.bid_due_date,
                (SELECT COUNT(*) FROM scopes s2
                 WHERE s2.project_id = p.id) AS project_scope_count
            FROM scopes s
            JOIN projects p ON s.project_id = p.id
        """)
        )
        data: list[dict[str, Any]] = []
        for r in rows:
            row = dict(r._mapping)
            # Normalise types
            clean: dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, Decimal):
                    clean[k] = float(v)
                elif v is not None:
                    clean[k] = v
                else:
                    clean[k] = None
            data.append(clean)
    return data


def _fetch_all_scopes_sync() -> list[dict[str, Any]]:
    return asyncio.run(_fetch_all_scopes())


# ---------------------------------------------------------------------------
# FeatureEngineer
# ---------------------------------------------------------------------------


class FeatureEngineer:
    """
    Transforms raw DB scope rows into a training-ready feature matrix.

    Usage::

        fe = FeatureEngineer()
        X, y, feature_names = fe.get_training_data(scope_type="ACT")
        df = fe.to_dataframe()
    """

    # Mapping from DB project_type string to a numeric label.
    # 0 = other/unknown (safe default), 1-6 = known types.
    PROJECT_TYPE_MAP: dict[str, int] = {
        "other": 0,
        "healthcare": 1,
        "education": 2,
        "commercial_office": 3,
        "worship": 4,
        "government": 5,
        "residential": 6,
    }

    # Features produced (order matters for array indexing)
    FEATURE_NAMES: list[str] = [
        "log_square_footage",
        "scope_type_encoded",
        "has_labor_rate",
        "labor_rate_normalized",
        "project_scope_count",
        "product_tier",
        "is_healthcare",
        "is_education",
        "is_church",
        "project_type_encoded",
        # extra numeric features (only when non-null — filled with median)
        "markup_pct",
        "man_days_per_sf",
        "material_cost_per_sf",
    ]

    def __init__(self, raw_data: list[dict[str, Any]] | None = None) -> None:
        if raw_data is not None:
            self._raw = raw_data
        else:
            logger.info("Fetching scope data from DB…")
            self._raw = _fetch_all_scopes_sync()
        logger.info("Loaded %d raw scope rows", len(self._raw))

        self._le = LabelEncoder()
        self._df: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Return the fully engineered feature DataFrame (including target cols)."""
        if self._df is None:
            self._df = self._build_dataframe()
        return self._df

    def get_training_data(
        self,
        scope_type: str | None = None,
        target: str = "cost_per_sf_total",
        outlier_bounds: tuple[float, float] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """
        Return (X, y, feature_names) for model training.

        Parameters
        ----------
        scope_type : str | None
            Filter to a single scope type; None = use all.
        target : str
            Column to use as y.  Options:
              'cost_per_sf_total'   — total / square_footage  (default)
              'cost_per_sf_material'— cost_per_unit (material $/SF pre-markup)
        outlier_bounds : tuple[float, float] | None
            (min, max) for the target.  Rows outside this range are dropped.
            If None, uses per-scope-type defaults from PriceIndexer bounds.
        """
        from src.enrichment.price_indexer import COST_PER_SF_BOUNDS

        df = self.to_dataframe().copy()

        # Filter scope type
        if scope_type is not None:
            df = df[df["scope_type"] == scope_type]
        else:
            # General model: exclude scope types with no useful cost_per_sf data
            excluded = ["SM", "Other"]
            df = df[~df["scope_type"].isin(excluded)]

        # Filter to rows with valid target
        df = df[df[target].notna() & (df[target] > 0)]

        # Apply outlier bounds
        if outlier_bounds is None:
            st = scope_type or "Other"
            lo, hi = COST_PER_SF_BOUNDS.get(st, (0.5, 300.0))
        else:
            lo, hi = outlier_bounds

        # Relax upper bound for "total" target (includes labor, markup, tax)
        if target == "cost_per_sf_total":
            hi = hi * 3.0  # material $/SF * markup * (1 + labor_frac) ≈ 2-5x

        df = df[(df[target] >= lo) & (df[target] <= hi)]

        if df.empty:
            raise ValueError(f"No valid training rows for scope_type={scope_type!r}, target={target!r}")

        # Build feature matrix
        feature_cols = [c for c in self.FEATURE_NAMES if c in df.columns]
        X = df[feature_cols].values.astype(float)
        y = df[target].values.astype(float)

        logger.info(
            "Training data: scope_type=%s  n=%d  target=%s  y_mean=%.2f",
            scope_type or "ALL",
            len(y),
            target,
            y.mean(),
        )
        return X, y, feature_cols

    def save_training_csv(self, path: str) -> None:
        """Save the complete engineered DataFrame to a CSV file."""
        df = self.to_dataframe()
        df.to_csv(path, index=False)
        logger.info("Saved training CSV to %s  (%d rows, %d cols)", path, len(df), len(df.columns))
        print(f"Saved {len(df)} rows to {path}")

    # ------------------------------------------------------------------
    # Internal build
    # ------------------------------------------------------------------

    def _build_dataframe(self) -> pd.DataFrame:
        records: list[dict[str, Any]] = []

        # Fit label encoder on all scope types present
        all_types = [r.get("scope_type") or "Other" for r in self._raw]
        self._le.fit(all_types)

        # Compute per-SF medians for imputation (per scope type)
        markup_medians: dict[str, float] = {}
        for st in set(all_types):
            vals = [
                float(r["markup_pct"])
                for r in self._raw
                if r.get("scope_type") == st and r.get("markup_pct") is not None
            ]
            markup_medians[st] = float(np.median(vals)) if vals else 0.30

        # Detect whether raw_data rows come from the pre-engineered CSV
        # (i.e. already have derived features like man_days_per_sf).
        # If so, we reuse those values rather than recomputing from missing raw columns.
        _sample = self._raw[0] if self._raw else {}
        _pre_engineered = "man_days_per_sf" in _sample

        for row in self._raw:
            st = row.get("scope_type") or "Other"
            sf = _to_float(row.get("square_footage"))
            cost_per_unit = _to_float(row.get("cost_per_unit"))
            total = _to_float(row.get("total"))
            markup_pct = _to_float(row.get("markup_pct"))
            _pn = row.get("project_name")
            project_name = _pn if isinstance(_pn, str) else ""
            _gn = row.get("gc_name")
            gc_name = _gn if isinstance(_gn, str) else ""
            project_scope_count = int(row.get("project_scope_count") or 1)

            # Derived target: total price / SF
            cost_per_sf_total: float | None = _to_float(row.get("cost_per_sf_total"))
            if cost_per_sf_total is None and total and sf and sf > 0:
                cost_per_sf_total = round(total / sf, 4)

            if _pre_engineered:
                # Reuse pre-computed features from the CSV — avoids recomputing from
                # raw columns that are absent in the serialised training data.
                log_sf = _to_float(row.get("log_square_footage"))
                has_labor_rate_val = int(row.get("has_labor_rate") or 0)
                has_labor_rate = bool(has_labor_rate_val)
                labor_rate_normalized = _to_float(row.get("labor_rate_normalized")) or 1.0
                man_days_per_sf = _to_float(row.get("man_days_per_sf"))
                material_cost_per_sf = _to_float(row.get("material_cost_per_sf"))
            else:
                material_cost = _to_float(row.get("material_cost"))
                material_price = _to_float(row.get("material_price"))
                man_days = _to_float(row.get("man_days"))
                labor_rate = _to_float(row.get("daily_labor_rate"))

                # Normalise labor rate
                has_labor_rate = labor_rate is not None and labor_rate > 0
                labor_rate_normalized = labor_rate / CURRENT_LABOR_RATE if has_labor_rate else None

                # log(1 + SF)
                log_sf = float(np.log1p(sf)) if sf and sf > 0 else None

                # man_days per SF
                man_days_per_sf = None
                if man_days and sf and sf > 0:
                    man_days_per_sf = round(man_days / sf, 6)

                # material cost per SF (from material_cost, not the per_unit price)
                material_cost_per_sf = None
                if (material_cost or material_price) and sf and sf > 0:
                    mc = material_cost or material_price
                    if mc:
                        material_cost_per_sf = round(mc / sf, 4)

            # project_type_encoded: use DB field when available, else fall back to 0 (other)
            # Guard against NaN floats that can arrive when FeatureEngineer is fed CSV rows
            _pt_raw = row.get("project_type")
            if _pt_raw is None or (isinstance(_pt_raw, float) and _pt_raw != _pt_raw):
                project_type = ""
            else:
                project_type = str(_pt_raw).strip()
            pt_lower = project_type.lower() if project_type else ""

            # When pre-engineered CSV rows already have project_type_encoded, reuse it;
            # otherwise compute from the DB-sourced project_type string.
            if _pre_engineered and "project_type_encoded" in row:
                _pte = row.get("project_type_encoded")
                project_type_encoded = int(_pte) if isinstance(_pte, (int, float)) and _pte == _pte else 0
            else:
                project_type_encoded = self.PROJECT_TYPE_MAP.get(pt_lower, 0)

            # Context flags — prefer DB project_type; fall back to keyword inference
            if _pre_engineered and "is_healthcare" in row:
                is_healthcare = bool(int(row.get("is_healthcare") or 0))
                is_education = bool(int(row.get("is_education") or 0))
                is_church = bool(int(row.get("is_church") or 0))
            elif pt_lower in self.PROJECT_TYPE_MAP and pt_lower != "other":
                is_healthcare = pt_lower == "healthcare"
                is_education = pt_lower == "education"
                is_church = pt_lower == "worship"
            else:
                is_healthcare = _keyword_flag(project_name, gc_name, HEALTHCARE_KEYWORDS)
                is_education = _keyword_flag(project_name, gc_name, EDUCATION_KEYWORDS)
                is_church = _keyword_flag(project_name, gc_name, CHURCH_KEYWORDS)

            rec: dict[str, Any] = {
                # Identifiers
                "id": row.get("id"),
                "scope_type": st,
                "scope_tag": row.get("scope_tag"),
                "product_name": row.get("product_name"),
                "project_name": project_name,
                "gc_name": gc_name,
                "project_type": project_type,
                # Raw numeric
                "square_footage": sf,
                "cost_per_unit": cost_per_unit,
                "total": total,
                # Target columns
                "cost_per_sf_material": cost_per_unit,  # material $/SF
                "cost_per_sf_total": cost_per_sf_total,  # total price $/SF
                # Features
                "log_square_footage": log_sf,
                "scope_type_encoded": int(self._le.transform([st])[0]),
                "has_labor_rate": int(has_labor_rate),
                "labor_rate_normalized": labor_rate_normalized if has_labor_rate else 1.0,  # default = current rate
                "project_scope_count": project_scope_count,
                "product_tier": _product_tier(row.get("product_name")),
                "is_healthcare": int(is_healthcare),
                "is_education": int(is_education),
                "is_church": int(is_church),
                "project_type_encoded": project_type_encoded,
                "markup_pct": markup_pct if markup_pct is not None else markup_medians.get(st, 0.30),
                "man_days_per_sf": man_days_per_sf,  # imputed below
                "material_cost_per_sf": material_cost_per_sf,  # imputed below
            }
            records.append(rec)

        df = pd.DataFrame(records)

        # Impute man_days_per_sf and material_cost_per_sf with per-scope-type medians
        for col in ["man_days_per_sf", "material_cost_per_sf"]:
            medians = df.groupby("scope_type")[col].median()
            for st in df["scope_type"].unique():
                mask = df["scope_type"] == st
                med = medians.get(st)
                if med is not None and not pd.isna(med):
                    df.loc[mask & df[col].isna(), col] = med
            # Global fallback
            global_med = df[col].median()
            df[col] = df[col].fillna(global_med if not pd.isna(global_med) else 0.0)

        # Impute log_square_footage with global median
        sf_med = df["log_square_footage"].median()
        df["log_square_footage"] = df["log_square_footage"].fillna(sf_med if not pd.isna(sf_med) else 0.0)

        logger.info("Built feature DataFrame: %d rows, %d columns", len(df), len(df.columns))
        return df
