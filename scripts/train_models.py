#!/usr/bin/env python
"""
Phase 3.2 + 3.3: Train and validate per-scope-type cost/SF prediction models.

Trains separate models for each scope type with ≥10 rows of cost_per_sf_total,
plus a GENERAL model over all scope types combined.

Outputs
-------
data/models/{SCOPE_TYPE}_cost_model.joblib   — serialised model
data/models/general_cost_model.joblib        — general model
data/models/model_manifest.json              — metadata for all models
data/models/training_data.csv               — feature-engineered dataset
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup path so we can import from src/
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_models")

MODELS_DIR = ROOT / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Scope types to train individual models for (need ≥10 rows with cost_per_sf_total)
PER_TYPE_CANDIDATES = ["ACT", "AWP", "AP", "Baffles", "FW", "WW"]
# Excluded: SM (no cost_per_sf), Other (heterogeneous), RPG (<5 rows)

MIN_ROWS = 10  # minimum rows to train a per-type model


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"


def _mape_color(mape: float, target: float) -> str:
    if mape <= target:
        return GREEN
    elif mape <= target * 1.5:
        return YELLOW
    return RED


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def print_report_header(label: str) -> None:
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  {label}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")


def print_model_result(report: TrainingReport, target_mape: float) -> None:  # noqa: F821
    color = _mape_color(report.test_mape, target_mape)
    tick = f"{GREEN}✓{RESET}" if report.target_met else f"{RED}✗{RESET}"
    print(f"\n  Model type    : {report.model_type}")
    print(f"  Training rows : {report.n_training_rows}")
    print(f"  Test rows     : {report.n_test_rows}")
    print(f"  Train MAPE    : {_fmt_pct(report.train_mape)}")
    print(
        f"  Test MAPE     : {color}{_fmt_pct(report.test_mape)}{RESET}  {tick}  (target ≤ {_fmt_pct(target_mape)})"
    )
    print(f"  Test R²       : {report.test_r2:.4f}")
    print(f"  CV MAPE       : {_fmt_pct(report.cv_mape)}")
    top3 = list(report.feature_importances.items())[:3]
    print(f"  Top 3 features: {', '.join(f'{k}={v:.3f}' for k, v in top3)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    from src.models.cost_model import CostModel
    from src.models.features import FeatureEngineer

    print_report_header("Phase 3.1 — Feature Engineering")
    logger.info("Loading and engineering features from DB…")
    fe = FeatureEngineer()
    df = fe.to_dataframe()

    csv_path = MODELS_DIR / "training_data.csv"
    fe.save_training_csv(str(csv_path))

    # Summary of available data
    print("\n  Scope type coverage:")
    print(f"  {'Scope':<10} {'Total':>6} {'w/ cost_per_sf':>14}")
    print(f"  {'-' * 32}")
    for st in sorted(df["scope_type"].unique()):
        total = (df["scope_type"] == st).sum()
        with_target = ((df["scope_type"] == st) & df["cost_per_sf_total"].notna()).sum()
        note = " ← will train" if with_target >= MIN_ROWS else " ← skip (insufficient)"
        print(f"  {st:<10} {total:>6} {with_target:>14}{note}")

    manifest: dict[str, dict] = {}

    # ----------------------------------------------------------------
    # Per-scope-type models
    # ----------------------------------------------------------------
    print_report_header("Phase 3.2 — Per-Scope-Type Model Training")

    for st in PER_TYPE_CANDIDATES:
        subset = df[(df["scope_type"] == st) & df["cost_per_sf_total"].notna()]
        n_available = len(subset)

        if n_available < MIN_ROWS:
            logger.warning(
                "Skipping %s — only %d rows with cost_per_sf_total (need ≥ %d)",
                st,
                n_available,
                MIN_ROWS,
            )
            print(f"\n  [{st}] SKIPPED — only {n_available} rows (need ≥ {MIN_ROWS})")
            manifest[st] = {
                "status": "skipped",
                "reason": f"only {n_available} rows with cost_per_sf_total",
            }
            continue

        print(f"\n{BOLD}  [{st}] n={n_available} rows{RESET}")

        try:
            model = CostModel(scope_type=st, prefer_xgboost=True)
            report = model.train(feature_engineer=fe)
        except ValueError as exc:
            logger.error("[%s] Training failed: %s", st, exc)
            print(f"  ERROR: {exc}")
            manifest[st] = {"status": "error", "error": str(exc)}
            continue

        target_mape = CostModel.MAPE_TARGETS.get(st, 0.25)
        print_model_result(report, target_mape)

        model_path = MODELS_DIR / f"{st}_cost_model.joblib"
        model.save(str(model_path))

        manifest[st] = {
            "status": "trained",
            "model_type": report.model_type,
            "scope_type": st,
            "target": model.target,
            "training_date": str(date.today()),
            "n_training_rows": report.n_training_rows,
            "n_test_rows": report.n_test_rows,
            "train_mape": round(report.train_mape, 4),
            "test_mape": round(report.test_mape, 4),
            "test_r2": round(report.test_r2, 4),
            "cv_mape": round(report.cv_mape, 4),
            "target_mape": target_mape,
            "target_met": report.target_met,
            "feature_names": report.feature_names,
            "feature_importances": {k: round(v, 4) for k, v in report.feature_importances.items()},
            "model_path": str(model_path.relative_to(ROOT)),
        }

    # ----------------------------------------------------------------
    # General model (all scope types combined, scope_type as feature)
    # ----------------------------------------------------------------
    print_report_header("Phase 3.3 — General Model (All Scope Types)")

    # Filter to rows where we have a target value and are not SM/Other
    trainable_types = ["ACT", "AWP", "AP", "Baffles", "FW", "WW", "RPG"]
    general_df = df[df["scope_type"].isin(trainable_types) & df["cost_per_sf_total"].notna()]
    n_general = len(general_df)
    print(
        f"\n  General model n={n_general} rows across {general_df['scope_type'].nunique()} scope types"
    )

    if n_general >= MIN_ROWS:
        try:
            general_model = CostModel(scope_type=None, prefer_xgboost=True)
            gen_report = general_model.train(feature_engineer=fe)
        except ValueError as exc:
            logger.error("General model training failed: %s", exc)
            print(f"  ERROR: {exc}")
            gen_report = None

        if gen_report:
            target_mape = CostModel.MAPE_TARGETS.get(None, 0.25)
            print_model_result(gen_report, target_mape)

            general_path = MODELS_DIR / "general_cost_model.joblib"
            general_model.save(str(general_path))

            manifest["GENERAL"] = {
                "status": "trained",
                "model_type": gen_report.model_type,
                "scope_type": None,
                "target": general_model.target,
                "training_date": str(date.today()),
                "n_training_rows": gen_report.n_training_rows,
                "n_test_rows": gen_report.n_test_rows,
                "train_mape": round(gen_report.train_mape, 4),
                "test_mape": round(gen_report.test_mape, 4),
                "test_r2": round(gen_report.test_r2, 4),
                "cv_mape": round(gen_report.cv_mape, 4),
                "target_mape": target_mape,
                "target_met": gen_report.target_met,
                "feature_names": gen_report.feature_names,
                "feature_importances": {
                    k: round(v, 4) for k, v in gen_report.feature_importances.items()
                },
                "model_path": str(general_path.relative_to(ROOT)),
            }
    else:
        print(f"  SKIPPED — only {n_general} rows")
        manifest["GENERAL"] = {
            "status": "skipped",
            "reason": f"only {n_general} rows",
        }

    # ----------------------------------------------------------------
    # Save manifest
    # ----------------------------------------------------------------
    manifest_path = MODELS_DIR / "model_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print_report_header("Summary")
    trained = [k for k, v in manifest.items() if v.get("status") == "trained"]
    skipped = [k for k, v in manifest.items() if v.get("status") == "skipped"]
    errors = [k for k, v in manifest.items() if v.get("status") == "error"]

    print(f"\n  Trained  : {', '.join(trained) if trained else 'none'}")
    if skipped:
        print(f"  Skipped  : {', '.join(skipped)}")
    if errors:
        print(f"  Errors   : {', '.join(errors)}")

    # MAPE summary
    print(f"\n  {'Scope':<10} {'Test MAPE':>10} {'R²':>8} {'Target':>8} {'Met':>5}")
    print(f"  {'-' * 45}")
    for k, v in manifest.items():
        if v.get("status") == "trained":
            tm = v.get("test_mape", 0)
            r2 = v.get("test_r2", 0)
            target = v.get("target_mape", 0)
            met = f"{GREEN}Yes{RESET}" if v.get("target_met") else f"{RED}No{RESET}"
            print(f"  {k:<10} {_fmt_pct(tm):>10} {r2:>8.4f} {_fmt_pct(target):>8} {met:>5}")

    print(f"\n  Manifest saved to: {manifest_path}")
    print(f"  Models saved to  : {MODELS_DIR}\n")


if __name__ == "__main__":
    main()
