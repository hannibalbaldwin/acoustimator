"""Model retraining orchestrator for Phase 7.2 — Continuous Learning.

Compares new model CV MAPE against the deployed model's MAPE and only
deploys if the new model is better or within a 5% tolerance.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import KFold, cross_val_predict

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT / "data" / "models"
MANIFEST_PATH = MODELS_DIR / "model_manifest.json"

# Minimum actuals recorded to consider retraining
MIN_ACTUALS = 5
# Minimum new projects since last retrain to trigger a retrain
MIN_NEW_SINCE_LAST = 3


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class RetrainResult:
    scope_type: str
    old_mape: float | None
    new_mape: float
    deployed: bool
    reason: str


# ---------------------------------------------------------------------------
# ModelRetrainer
# ---------------------------------------------------------------------------


class ModelRetrainer:
    """Orchestrate retraining of cost, markup, and labor models.

    Compares new model vs. current via cross-validation MAPE.
    Only deploys if new model MAPE <= current MAPE * 1.05 (5% tolerance).
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.models_dir = models_dir
        self.manifest_path = models_dir / "model_manifest.json"

    # ------------------------------------------------------------------
    # should_retrain
    # ------------------------------------------------------------------

    async def should_retrain(self, session: Any) -> tuple[bool, str]:
        """Return (should_retrain, reason).

        Retrain if:
          - estimates with actuals recorded >= MIN_ACTUALS (5), AND
          - projects with actuals since last_retrain >= MIN_NEW_SINCE_LAST (3).
        """
        from sqlalchemy import func, select, text

        from src.db.models import Estimate

        # Count total estimates with actuals
        total_actuals_result = await session.execute(
            select(func.count())
            .select_from(Estimate)
            .where(
                Estimate.actual_total_cost.is_not(None),
                Estimate.actual_total_cost > 0,
            )
        )
        total_actuals: int = total_actuals_result.scalar_one()

        if total_actuals < MIN_ACTUALS:
            return False, f"Only {total_actuals} actuals recorded (need {MIN_ACTUALS})"

        # Read last_retrain from manifest
        last_retrain_dt: datetime | None = None
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text())
                lr_str = manifest.get("last_retrain")
                if lr_str:
                    last_retrain_dt = datetime.fromisoformat(lr_str)
            except Exception as exc:
                logger.warning("Could not parse manifest last_retrain: %s", exc)

        # Count actuals recorded since last_retrain
        if last_retrain_dt is None:
            # No prior retrain — count all actuals
            new_actuals = total_actuals
        else:
            new_actuals_result = await session.execute(
                select(func.count())
                .select_from(Estimate)
                .where(
                    Estimate.actual_total_cost.is_not(None),
                    Estimate.actual_total_cost > 0,
                    Estimate.actual_cost_date.is_not(None),
                    text(f"actual_cost_date > '{last_retrain_dt.date().isoformat()}'"),
                )
            )
            new_actuals = new_actuals_result.scalar_one()

        if new_actuals < MIN_NEW_SINCE_LAST:
            return (
                False,
                f"Only {new_actuals} new actuals since last retrain (need {MIN_NEW_SINCE_LAST})",
            )

        return True, f"{new_actuals} new actuals since last retrain (total: {total_actuals})"

    # ------------------------------------------------------------------
    # retrain_all
    # ------------------------------------------------------------------

    def retrain_all(self, training_csv_path: Path) -> dict[str, RetrainResult]:
        """Retrain cost, markup, and labor models from a training CSV.

        For each model: load current, train new, compare CV MAPE.
        Returns dict of model_name -> RetrainResult.
        """
        if not training_csv_path.exists():
            raise FileNotFoundError(f"Training CSV not found: {training_csv_path}")

        df = pd.read_csv(training_csv_path)
        logger.info("Loaded training CSV: %d rows, %d columns", len(df), len(df.columns))

        results: dict[str, RetrainResult] = {}

        # Retrain cost models (per scope type + general)
        results.update(self._retrain_cost_models(df))

        # Retrain markup model
        results["markup"] = self._retrain_markup_model(df)

        # Retrain labor model
        results["labor"] = self._retrain_labor_model(df)

        return results

    # ------------------------------------------------------------------
    # deploy_if_better
    # ------------------------------------------------------------------

    def deploy_if_better(
        self,
        results: dict[str, RetrainResult],
        dry_run: bool = False,
    ) -> list[str]:
        """Deploy models where new MAPE <= current MAPE * 1.05.

        Overwrites the .joblib files for qualifying models.
        Returns list of deployed model names.
        """
        deployed: list[str] = []
        for name, result in results.items():
            if result.deployed and not dry_run:
                deployed.append(name)
            elif result.deployed and dry_run:
                deployed.append(name)
                logger.info("[dry-run] Would deploy %s", name)
        return deployed

    # ------------------------------------------------------------------
    # update_manifest
    # ------------------------------------------------------------------

    def update_manifest(
        self,
        results: dict[str, RetrainResult],
        deployed: list[str],
    ) -> None:
        """Write last_retrain timestamp and per-model MAPEs to manifest."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {}
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text())
            except Exception:
                pass

        manifest["last_retrain"] = datetime.now(UTC).isoformat()

        for name, result in results.items():
            key = f"{name}_retrain"
            manifest[key] = {
                "scope_type": result.scope_type,
                "old_mape": result.old_mape,
                "new_mape": round(result.new_mape, 4),
                "deployed": result.deployed,
                "reason": result.reason,
                "retrained_at": manifest["last_retrain"],
            }
            # Also update the top-level model entry MAPE if deployed
            if name in deployed:
                # Update the relevant manifest key for deployed model
                for mkey in list(manifest.keys()):
                    if mkey == name or mkey.startswith(f"{name}_") and not mkey.endswith("_retrain"):
                        if isinstance(manifest[mkey], dict):
                            manifest[mkey]["cv_mape"] = round(result.new_mape, 4)
                            manifest[mkey]["last_retrain"] = manifest["last_retrain"]

        self.manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Manifest updated at %s", self.manifest_path)

    # ------------------------------------------------------------------
    # Internal: cost model retraining
    # ------------------------------------------------------------------

    def _retrain_cost_models(self, df: pd.DataFrame) -> dict[str, RetrainResult]:
        from src.models.cost_model import CostModel
        from src.models.features import FeatureEngineer

        results: dict[str, RetrainResult] = {}
        manifest = self._load_manifest()

        available_scope_types = set(df["scope_type"].dropna().unique()) if "scope_type" in df.columns else set()
        scope_types_to_train: list[str | None] = [
            st for st in ["ACT", "AWP", "AP", "Baffles", "FW", "WW"] if st in available_scope_types
        ] + [None]

        fe = FeatureEngineer(raw_data=df.to_dict("records"))

        for scope_type in scope_types_to_train:
            name = scope_type if scope_type is not None else "GENERAL"
            model_file = (
                self.models_dir / f"{scope_type}_cost_model.joblib"
                if scope_type
                else self.models_dir / "general_cost_model.joblib"
            )

            # Get current MAPE from manifest or loaded model
            old_mape = self._get_current_mape(manifest, name, "cv_mape")

            # Train new model
            try:
                new_model = CostModel(scope_type=scope_type, prefer_xgboost=True)
                report = new_model.train(feature_engineer=fe)
                new_mape = report.cv_mape
            except (ValueError, Exception) as exc:
                logger.warning("Cost model retrain failed for %s: %s", name, exc)
                results[name] = RetrainResult(
                    scope_type=name,
                    old_mape=old_mape,
                    new_mape=float("inf"),
                    deployed=False,
                    reason=f"Training failed: {exc}",
                )
                continue

            # Compare and decide
            should_deploy, reason, deployed = self._compare_and_deploy(name, old_mape, new_mape, new_model, model_file)

            results[name] = RetrainResult(
                scope_type=name,
                old_mape=old_mape,
                new_mape=new_mape,
                deployed=deployed,
                reason=reason,
            )

        return results

    # ------------------------------------------------------------------
    # Internal: markup model retraining
    # ------------------------------------------------------------------

    def _retrain_markup_model(self, df: pd.DataFrame) -> RetrainResult:
        manifest = self._load_manifest()
        model_file = self.models_dir / "markup_model.joblib"
        old_mape = self._get_current_mape(manifest, "markup_model", "test_mape")

        # Filter rows with markup_pct
        records = df[df["markup_pct"].notna() & (df["markup_pct"] > 0) & (df["markup_pct"] <= 1.0)].to_dict("records")

        if len(records) < 5:
            return RetrainResult(
                scope_type="markup",
                old_mape=old_mape,
                new_mape=float("inf"),
                deployed=False,
                reason=f"Insufficient data: {len(records)} rows",
            )

        # Compute new CV MAPE
        new_mape = self._markup_cv_mape(records)
        _, reason, deployed = self._compare_and_deploy_markup(old_mape, new_mape, records, model_file)

        return RetrainResult(
            scope_type="markup",
            old_mape=old_mape,
            new_mape=new_mape,
            deployed=deployed,
            reason=reason,
        )

    def _markup_cv_mape(self, records: list[dict]) -> float:
        from src.models.markup_model import MarkupModel

        model = MarkupModel()
        X = model._build_feature_matrix(records)
        y = np.array([float(r["markup_pct"]) for r in records])
        n = len(y)
        k = min(5, n)
        if k < 2:
            return float("inf")
        cv = KFold(n_splits=k, shuffle=True, random_state=42)
        try:
            from sklearn.base import clone

            preds = cross_val_predict(clone(model._model) if model._model else model._model, X, y, cv=cv)
        except Exception:
            # Train full then predict as fallback
            model.train(records)
            preds = model._model.predict(X)
        return float(mean_absolute_percentage_error(y, preds))

    def _compare_and_deploy_markup(
        self,
        old_mape: float | None,
        new_mape: float,
        records: list[dict],
        model_file: Path,
    ) -> tuple[bool, str, bool]:
        from src.models.markup_model import MarkupModel

        tolerance = 1.05
        if old_mape is None or new_mape <= old_mape * tolerance:
            new_model = MarkupModel()
            new_model.train(records)
            self.models_dir.mkdir(parents=True, exist_ok=True)
            new_model.save(model_file)
            reason = (
                "No prior model — deployed new"
                if old_mape is None
                else f"New MAPE {new_mape:.1%} <= old {old_mape:.1%} * 1.05 — deployed"
            )
            return True, reason, True
        reason = f"New MAPE {new_mape:.1%} > old {old_mape:.1%} * 1.05 — kept existing"
        return False, reason, False

    # ------------------------------------------------------------------
    # Internal: labor model retraining
    # ------------------------------------------------------------------

    def _retrain_labor_model(self, df: pd.DataFrame) -> RetrainResult:
        from src.models.labor_model import LaborModel

        manifest = self._load_manifest()
        model_file = self.models_dir / "labor_model.joblib"
        old_mape = self._get_current_mape(manifest, "labor_model", "cv_mape_mean")

        # The training CSV stores man_days_per_sf (not raw man_days).
        # Reconstruct man_days = man_days_per_sf * square_footage when possible;
        # fall back to filtering rows that have both columns > 0.
        if "man_days" not in df.columns and "man_days_per_sf" in df.columns:
            df = df.copy()
            df["man_days"] = df["man_days_per_sf"] * df["square_footage"]
        records = df[df["man_days"].notna() & (df["man_days"] > 0)].to_dict("records")

        if len(records) < 5:
            return RetrainResult(
                scope_type="labor",
                old_mape=old_mape,
                new_mape=float("inf"),
                deployed=False,
                reason=f"Insufficient data: {len(records)} rows",
            )

        # Train and CV
        try:
            new_model = LaborModel()
            metrics = new_model.train(records)
            new_mape = metrics.get("cv_mape_mean", float("inf"))
        except Exception as exc:
            return RetrainResult(
                scope_type="labor",
                old_mape=old_mape,
                new_mape=float("inf"),
                deployed=False,
                reason=f"Training failed: {exc}",
            )

        tolerance = 1.05
        if old_mape is None or new_mape <= old_mape * tolerance:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            new_model.save(model_file)
            reason = (
                "No prior model — deployed new"
                if old_mape is None
                else f"New MAPE {new_mape:.1%} <= old {old_mape:.1%} * 1.05 — deployed"
            )
            deployed = True
        else:
            reason = f"New MAPE {new_mape:.1%} > old {old_mape:.1%} * 1.05 — kept existing"
            deployed = False

        return RetrainResult(
            scope_type="labor",
            old_mape=old_mape,
            new_mape=new_mape,
            deployed=deployed,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Internal: compare + deploy cost model
    # ------------------------------------------------------------------

    def _compare_and_deploy(
        self,
        name: str,
        old_mape: float | None,
        new_mape: float,
        new_model: Any,
        model_file: Path,
    ) -> tuple[bool, str, bool]:
        tolerance = 1.05
        if old_mape is None or new_mape <= old_mape * tolerance:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            new_model.save(str(model_file))
            reason = (
                "No prior model — deployed new"
                if old_mape is None
                else f"New MAPE {new_mape:.1%} <= old {old_mape:.1%} * 1.05 — deployed"
            )
            return True, reason, True
        reason = f"New MAPE {new_mape:.1%} > old {old_mape:.1%} * 1.05 — kept existing"
        return False, reason, False

    # ------------------------------------------------------------------
    # Internal: manifest helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except Exception as exc:
                logger.warning("Could not parse manifest: %s", exc)
        return {}

    def _get_current_mape(
        self,
        manifest: dict[str, Any],
        key: str,
        mape_field: str,
    ) -> float | None:
        entry = manifest.get(key)
        if not isinstance(entry, dict):
            return None
        val = entry.get(mape_field)
        if val is None:
            # Try alternate MAPE field names
            for alt in ("cv_mape", "test_mape", "cv_mape_mean"):
                val = entry.get(alt)
                if val is not None:
                    break
        return float(val) if val is not None else None
