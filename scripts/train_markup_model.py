#!/usr/bin/env python3
"""Train the markup prediction model and save to data/models/.

Usage:
    uv run python scripts/train_markup_model.py

Outputs:
    data/models/markup_model.joblib   — serialised trained model
    data/models/model_manifest.json   — updated model registry entry
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
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy import text

# Ensure project root is on path when run directly
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.session import async_session  # noqa: E402
from src.models.markup_model import MarkupModel  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "data" / "models"
MODEL_PATH = MODELS_DIR / "markup_model.joblib"
MANIFEST_PATH = MODELS_DIR / "model_manifest.json"

QUERY = """
    SELECT
        s.scope_type,
        s.product_name,
        s.square_footage,
        s.cost_per_unit,
        s.markup_pct,
        s.man_days,
        s.daily_labor_rate,
        s.total,
        p.name         AS project_name,
        p.gc_name,
        p.project_type,
        (SELECT COUNT(*) FROM scopes s2 WHERE s2.project_id = p.id) AS project_scope_count
    FROM scopes s
    JOIN projects p ON s.project_id = p.id
    WHERE s.markup_pct IS NOT NULL
      AND s.markup_pct > 0
      AND s.markup_pct <= 1.0
"""


async def fetch_records() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(text(QUERY))
        rows = []
        for r in result:
            row = {}
            for k, v in dict(r._mapping).items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
                elif v is None:
                    row[k] = None
                else:
                    row[k] = str(v) if not isinstance(v, (int, float, bool)) else v
            rows.append(row)
        return rows


def print_per_type_report(
    records_test: list[dict],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    from collections import defaultdict

    type_data: dict[str, dict] = defaultdict(lambda: {"true": [], "pred": []})
    for rec, yt, yp in zip(records_test, y_true, y_pred):
        st = rec.get("scope_type") or "None"
        type_data[st]["true"].append(yt)
        type_data[st]["pred"].append(yp)

    print("\n--- Per-scope-type results (test set) ---")
    print(f"{'Type':<12} {'N':>4}  {'Actual mean':>12}  {'Pred mean':>10}  {'Δ':>8}")
    print("-" * 55)
    for st in sorted(type_data):
        trues = np.array(type_data[st]["true"])
        preds = np.array(type_data[st]["pred"])
        delta = np.mean(preds) - np.mean(trues)
        print(
            f"{st:<12} {len(trues):>4}  {np.mean(trues):>11.1%}  {np.mean(preds):>9.1%}  {delta:>+8.1%}"
        )
    print()


def update_manifest(metrics: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    else:
        manifest = {}

    manifest["markup_model"] = {
        "version": MarkupModel.MODEL_VERSION,
        "path": str(MODEL_PATH.relative_to(PROJECT_ROOT)),
        "trained_at": datetime.now(UTC).isoformat(),
        "n_train": metrics["n_train"],
        "n_test": metrics["n_test"],
        "test_mape": round(metrics["test_mape"], 4),
        "test_r2": round(metrics["test_r2"], 4),
        "cv_r2_mean": round(metrics["cv_r2_mean"], 4),
        "cv_r2_std": round(metrics["cv_r2_std"], 4),
        "feature_importances": metrics["feature_importances"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    log.info("Manifest updated at %s", MANIFEST_PATH)


def main() -> None:
    log.info("Fetching scope records from database...")
    records = asyncio.run(fetch_records())
    log.info("Fetched %d records (markup_pct 0–100%%)", len(records))

    if len(records) < 20:
        log.error("Too few records (%d) to train a reliable model.", len(records))
        sys.exit(1)

    # ------------------------------------------------------------------
    # 80/20 train/test split (stratified by scope_type where possible)
    # ------------------------------------------------------------------
    indices = list(range(len(records)))
    scope_types = [r.get("scope_type") or "None" for r in records]

    try:
        train_idx, test_idx = train_test_split(
            indices, test_size=0.20, random_state=42, stratify=scope_types
        )
    except ValueError:
        # Stratification fails if any class has <2 samples
        log.warning("Stratified split failed; falling back to random split.")
        train_idx, test_idx = train_test_split(indices, test_size=0.20, random_state=42)

    records_train = [records[i] for i in train_idx]
    records_test = [records[i] for i in test_idx]
    log.info("Split: %d train / %d test", len(records_train), len(records_test))

    # ------------------------------------------------------------------
    # Train
    # ------------------------------------------------------------------
    model = MarkupModel()
    log.info("Training MarkupModel (GradientBoostingRegressor)...")
    train_metrics = model.train(records_train)
    log.info(
        "CV R² = %.3f ± %.3f | CV MAPE = %.1f%%",
        train_metrics["cv_r2_mean"],
        train_metrics["cv_r2_std"],
        train_metrics["cv_mape_mean"] * 100,
    )

    # ------------------------------------------------------------------
    # Evaluate on held-out test set
    # ------------------------------------------------------------------
    y_true = np.array([float(r["markup_pct"]) for r in records_test])

    # Build feature matrix for test set using model internals
    X_test = model._build_feature_matrix(records_test)
    y_pred = model._model.predict(X_test)
    y_pred = np.clip(y_pred, 0.10, 1.00)

    test_mape = mean_absolute_percentage_error(y_true, y_pred)
    test_r2 = r2_score(y_true, y_pred)

    print("\n========================================")
    print("  Markup Model — Training Results")
    print("========================================")
    print(f"  Training samples : {len(records_train)}")
    print(f"  Test samples     : {len(records_test)}")
    print(
        f"  CV R²            : {train_metrics['cv_r2_mean']:.3f} ± {train_metrics['cv_r2_std']:.3f}"
    )
    print(f"  Test MAPE        : {test_mape:.1%}")
    print(f"  Test R²          : {test_r2:.3f}")
    print()
    print("  Feature importances:")
    for feat, imp in sorted(train_metrics["feature_importances"].items(), key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"    {feat:<28} {imp:.3f}  {bar}")

    print_per_type_report(records_test, y_true, y_pred)

    # ------------------------------------------------------------------
    # Sanity check — sample predictions
    # ------------------------------------------------------------------
    print("--- Sample predictions ---")
    sample_cases = [
        {
            "scope_type": "ACT",
            "square_footage": 5000,
            "project_scope_count": 4,
            "daily_labor_rate": 600,
        },
        {
            "scope_type": "FW",
            "square_footage": 1200,
            "project_scope_count": 2,
            "daily_labor_rate": 650,
        },
        {
            "scope_type": "WW",
            "square_footage": 800,
            "project_scope_count": 3,
            "daily_labor_rate": 550,
        },
        {
            "scope_type": "AWP",
            "square_footage": 3000,
            "project_scope_count": 5,
            "daily_labor_rate": 580,
        },
        {
            "scope_type": "SM",
            "square_footage": None,
            "project_scope_count": 6,
            "daily_labor_rate": 700,
        },
        {
            "scope_type": "Baffles",
            "square_footage": 600,
            "project_scope_count": 2,
            "daily_labor_rate": 620,
        },
    ]
    for case in sample_cases:
        pred = model.predict(case)
        print(
            f"  {case['scope_type']:<8} SF={case.get('square_footage') or 'N/A':>5}  "
            f"→ {pred.predicted_markup:.1%}  [{pred.low:.1%}–{pred.high:.1%}]"
        )

    # ------------------------------------------------------------------
    # Save model + manifest
    # ------------------------------------------------------------------
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    log.info("Model saved to %s", MODEL_PATH)

    all_metrics = {
        **train_metrics,
        "n_train": len(records_train),
        "n_test": len(records_test),
        "test_mape": test_mape,
        "test_r2": test_r2,
    }
    update_manifest(all_metrics)

    print("\nDone. Model saved to:", MODEL_PATH)


if __name__ == "__main__":
    main()
