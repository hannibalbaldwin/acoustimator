"""Train the labor estimation model and report results.

Queries historical scope data with man_days, engineers features,
trains a RandomForestRegressor, and saves the model artifact.

Usage:
    uv run python scripts/train_labor_model.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.session import async_session
from src.models.labor_model import LaborModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "data" / "models" / "labor_model.joblib"
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "models" / "model_manifest.json"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


async def load_data() -> list[dict]:
    """Query scopes with man_days from the database."""
    async with async_session() as session:
        result = await session.execute(
            text("""
            SELECT
                s.scope_type,
                s.product_name,
                s.square_footage,
                s.man_days,
                s.daily_labor_rate,
                s.labor_price,
                s.markup_pct,
                p.name AS project_name,
                (SELECT COUNT(*) FROM scopes s2 WHERE s2.project_id = p.id)
                    AS project_scope_count
            FROM scopes s
            JOIN projects p ON s.project_id = p.id
            WHERE s.man_days IS NOT NULL AND s.man_days > 0
        """)
        )
        rows = result.fetchall()

    data = []
    for row in rows:
        d = dict(row._mapping)
        # Convert Decimal to float
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = float(v)
        data.append(d)

    return data


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def analyze_data(df: pd.DataFrame) -> None:
    """Print exploratory data analysis."""
    print("\n" + "=" * 60)
    print("DATA ANALYSIS")
    print("=" * 60)
    print(f"\nTotal scopes with man_days: {len(df)}")
    print(f"Scopes with square_footage: {df['square_footage'].notna().sum()}")
    print(f"Scopes without square_footage: {df['square_footage'].isna().sum()}")

    print("\nBy scope type:")
    by_type = (
        df.groupby("scope_type")
        .agg(
            count=("man_days", "count"),
            mean_md=("man_days", "mean"),
            median_md=("man_days", "median"),
            min_md=("man_days", "min"),
            max_md=("man_days", "max"),
            sf_count=("square_footage", "count"),
        )
        .round(2)
    )
    print(by_type.to_string())

    print("\nman_days distribution:")
    print(df["man_days"].describe().round(2).to_string())

    # Outlier report
    extreme = df[df["man_days"] > 100]
    if len(extreme):
        print(f"\nExtreme outliers (man_days > 100): {len(extreme)}")
        print(extreme[["scope_type", "product_name", "square_footage", "man_days"]].to_string())

    # SF vs man_days relationship
    df_sf = df[df["square_footage"].notna() & (df["square_footage"] > 0)].copy()
    print(f"\nSubset with SF for correlation: {len(df_sf)} rows")
    if len(df_sf) > 5:
        log_sf = np.log1p(df_sf["square_footage"])
        log_md = np.log1p(df_sf["man_days"])
        log_corr = float(np.corrcoef(log_sf, log_md)[0, 1])
        lin_corr = float(np.corrcoef(df_sf["square_footage"], df_sf["man_days"])[0, 1])
        print(f"  log-log correlation (log_SF vs log_man_days): {log_corr:.3f}")
        print(f"  linear correlation  (SF vs man_days):         {lin_corr:.3f}")

        # Check fixed cost component by looking at intercept
        # Fit log-log: log_md = a * log_sf + b
        # If b >> 0, there's a meaningful fixed component
        coefs = np.polyfit(log_sf, log_md, 1)
        print(f"  log-log fit: log_md = {coefs[0]:.3f}*log_sf + {coefs[1]:.3f}")
        print(f"  Implied: man_days ≈ exp({coefs[1]:.2f}) * SF^{coefs[0]:.3f}")
        print(f"  Fixed component (exp(intercept)): ~{np.exp(coefs[1]):.2f} man-days")

    print()


# ---------------------------------------------------------------------------
# Per-type accuracy report
# ---------------------------------------------------------------------------


def per_type_report(model: LaborModel, records: list[dict]) -> None:
    """Print mean predicted vs actual man-days by scope type."""
    print("\n" + "=" * 60)
    print("PER-SCOPE-TYPE: PREDICTED vs ACTUAL")
    print("=" * 60)

    by_type: dict[str, dict[str, list]] = {}
    for r in records:
        st = r.get("scope_type") or "Unknown"
        if st not in by_type:
            by_type[st] = {"actual": [], "predicted": []}
        pred = model.predict(
            scope_type=r.get("scope_type"),
            square_footage=float(r.get("square_footage") or 0),
            product_name=r.get("product_name"),
            daily_labor_rate=float(r.get("daily_labor_rate") or 725),
            project_scope_count=int(r.get("project_scope_count") or 3),
        )
        by_type[st]["actual"].append(float(r["man_days"]))
        by_type[st]["predicted"].append(pred.man_days)

    print(f"\n{'Scope':<10} {'N':>4} {'Mean Actual':>12} {'Mean Pred':>10} {'MAPE':>8}")
    print("-" * 50)
    for st in sorted(by_type.keys()):
        actuals = np.array(by_type[st]["actual"])
        preds = np.array(by_type[st]["predicted"])
        mape = float(np.mean(np.abs(preds - actuals) / np.maximum(actuals, 0.5)))
        print(
            f"{st:<10} {len(actuals):>4}  "
            f"{np.mean(actuals):>10.2f}  {np.mean(preds):>10.2f}  {mape:>7.1%}"
        )
    print()


# ---------------------------------------------------------------------------
# Sample predictions
# ---------------------------------------------------------------------------


def sample_predictions(model: LaborModel) -> None:
    """Print example predictions for common scenarios."""
    print("\n" + "=" * 60)
    print("SAMPLE PREDICTIONS")
    print("=" * 60)
    print()

    scenarios = [
        # (label, scope_type, SF, product_name, rate)
        ("ACT, 1,000 SF (small room)", "ACT", 1_000, "Ultima High NRC Beveled Tegular", 725),
        ("ACT, 5,000 SF (medium)", "ACT", 5_000, "Ultima High NRC Beveled Tegular", 725),
        ("ACT, 15,000 SF (large)", "ACT", 15_000, "Optima Lay-in", 725),
        ("ACT, 30,000 SF (very large)", "ACT", 30_000, "Optima Lay-in", 725),
        ("AWP, 500 SF", "AWP", 500, "MDC Embossed Walls", 725),
        ("AWP, 2,000 SF", "AWP", 2_000, "MDC Embossed Walls", 725),
        ("AWP, 5,000 SF", "AWP", 5_000, "MDC Embossed Walls", 725),
        ("FW, 300 SF (snap-tex)", "FW", 300, "Snap-Tex Track System", 725),
        ("FW, 1,500 SF", "FW", 1_500, "Snap-Tex Track System", 725),
        ("WW (WoodWorks), 500 SF", "WW", 500, "WoodWorks Blades", 725),
        ("WW (WoodWorks), 2,000 SF", "WW", 2_000, "WoodWorks Blades", 725),
        ("Baffles, 200 SF", "Baffles", 200, "Arktura Atmosphera Swell", 725),
        ("SM (no SF)", "SM", 0, "Vektor Gold Sound Masking", 725),
        ("AP panels (no SF)", "AP", 0, "Acoustic Clouds Fabric-Wrapped", 725),
    ]

    print(f"{'Scenario':<40} {'Man-Days':>9} {'Low':>6} {'High':>6}  {'MD/1kSF':>8}")
    print("-" * 75)
    for label, st, sf, prod, rate in scenarios:
        p = model.predict(
            scope_type=st,
            square_footage=sf,
            product_name=prod,
            daily_labor_rate=rate,
        )
        md_k = f"{p.man_days_per_1000sf:.2f}" if p.man_days_per_1000sf else "  —"
        print(f"{label:<40} {p.man_days:>9.2f} {p.low:>6.2f} {p.high:>6.2f}  {md_k:>8}")
    print()


# ---------------------------------------------------------------------------
# Manifest update
# ---------------------------------------------------------------------------


def update_manifest(metrics: dict) -> None:
    """Add or update the labor_model entry in model_manifest.json."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    manifest["labor_model"] = {
        "path": str(MODEL_PATH.relative_to(Path(__file__).parent.parent)),
        "version": LaborModel.MODEL_VERSION,
        "trained_at": datetime.now(UTC).isoformat(),
        "n_samples": metrics["n_samples"],
        "cv_r2_mean": round(metrics["cv_r2_mean"], 4),
        "cv_r2_std": round(metrics["cv_r2_std"], 4),
        "cv_mape_mean": round(metrics["cv_mape_mean"], 4),
        "features": [
            "scope_type_encoded",
            "log_square_footage",
            "product_tier",
            "labor_rate_normalized",
            "project_scope_count",
            "has_square_footage",
        ],
        "target": "log1p(man_days) → expm1 on output",
        "algorithm": "RandomForestRegressor",
    }

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Manifest updated at %s", MANIFEST_PATH)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    print("\n" + "=" * 60)
    print("ACOUSTIMATOR — LABOR MODEL TRAINING")
    print("=" * 60)

    # 1. Load data
    logger.info("Loading scope data from database...")
    records = await load_data()
    logger.info("Loaded %d scopes with man_days", len(records))

    df = pd.DataFrame(records)

    # 2. Analyze
    analyze_data(df)

    # 3. Filter to usable records
    # Keep all records (including those without SF — model handles via has_sf flag)
    # Drop any with man_days <= 0 (shouldn't exist but safety check)
    clean_records = [r for r in records if r.get("man_days") and float(r["man_days"]) > 0]
    logger.info("Training on %d clean records", len(clean_records))

    # 4. Train
    print("=" * 60)
    print("TRAINING")
    print("=" * 60)
    model = LaborModel()
    logger.info("Training RandomForestRegressor (300 trees)...")
    metrics = model.train(clean_records)

    print("\nTraining results:")
    print(f"  Samples:          {metrics['n_samples']}")
    print(f"  CV R² (log):      {metrics['cv_r2_mean']:.3f} ± {metrics['cv_r2_std']:.3f}")
    print(f"  CV MAPE:          {metrics['cv_mape_mean']:.1%} ± {metrics['cv_mape_std']:.1%}")
    print("  Feature importances:")
    for feat, imp in sorted(metrics["feature_importances"].items(), key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"    {feat:<30} {imp:.3f}  {bar}")

    # 5. Per-type report
    per_type_report(model, clean_records)

    # 6. Sample predictions
    sample_predictions(model)

    # 7. Save
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)

    # 8. Update manifest
    update_manifest(metrics)

    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"  Model: {MODEL_PATH}")
    print(f"  Manifest: {MANIFEST_PATH}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
