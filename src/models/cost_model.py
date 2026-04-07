"""
CostModel: per-scope-type cost/SF prediction models (Phase 3.2 + 3.3).

Supports RandomForest and XGBoost regressors.  Automatically selects the
better-performing algorithm (lower test MAPE) when both are available.

Usage::

    model = CostModel(scope_type="ACT")
    model.train()
    result = model.predict({"square_footage": 3500, "product_name": "Cirrus on Prelude"})
    print(result.predicted_cost_per_sf, result.confidence_interval)

    model.save("data/models/ACT_cost_model.joblib")
    model2 = CostModel.load("data/models/ACT_cost_model.joblib")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import KFold, LeaveOneOut, cross_val_predict, train_test_split

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CostPrediction:
    """Output of CostModel.predict()."""

    predicted_cost_per_sf: float
    confidence_interval: tuple[float, float]  # (low, high) — ±1.5 * std of CV residuals
    mape_on_test: float | None = None
    scope_type: str | None = None
    model_type: str | None = None


@dataclass
class TrainingReport:
    """Summary produced after model.train()."""

    scope_type: str | None
    model_type: str
    n_training_rows: int
    n_test_rows: int
    train_mape: float
    test_mape: float
    test_r2: float
    cv_mape: float
    feature_importances: dict[str, float] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)
    target_met: bool = False


# ---------------------------------------------------------------------------
# CostModel
# ---------------------------------------------------------------------------


class CostModel:
    """
    Wraps a scikit-learn or XGBoost regressor for cost/SF prediction.

    Parameters
    ----------
    scope_type : str | None
        ACT, AWP, etc.  None = train on all scope types (general model).
    target : str
        Column to predict.  Default 'cost_per_sf_total' (total price / SF).
    prefer_xgboost : bool
        If True and xgboost is installed, try XGBoost first (then RF if worse).
    """

    MAPE_TARGETS: dict[str | None, float] = {
        "ACT": 0.15,
        "AWP": 0.20,
        "AP": 0.25,
        "Baffles": 0.25,
        "FW": 0.25,
        "WW": 0.25,
        "RPG": 0.30,
        None: 0.25,  # general model
    }

    def __init__(
        self,
        scope_type: str | None = None,
        target: str = "cost_per_sf_total",
        prefer_xgboost: bool = True,
    ) -> None:
        self.scope_type = scope_type
        self.target = target
        self.prefer_xgboost = prefer_xgboost

        self._model: Any = None
        self._feature_names: list[str] = []
        self._cv_std: float = 0.0
        self._report: TrainingReport | None = None

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        raw_data: list[dict[str, Any]] | None = None,
        feature_engineer: Any | None = None,
        test_size: float = 0.20,
        random_state: int = 42,
    ) -> TrainingReport:
        """
        Train the model.  Returns a TrainingReport.

        Parameters
        ----------
        raw_data : list of dicts | None
            Raw DB rows.  If None (and feature_engineer is None), fetched from DB.
        feature_engineer : FeatureEngineer | None
            Pre-built FeatureEngineer instance (avoids redundant DB fetches).
        """
        from src.models.features import FeatureEngineer

        if feature_engineer is not None:
            fe = feature_engineer
        else:
            fe = FeatureEngineer(raw_data=raw_data)
        X, y, feature_names = fe.get_training_data(
            scope_type=self.scope_type,
            target=self.target,
        )
        self._feature_names = feature_names

        n = len(y)
        logger.info("Training CostModel scope_type=%s  n=%d", self.scope_type, n)

        # Train/test split
        if n < 5:
            raise ValueError(f"Insufficient data for scope_type={self.scope_type!r}: only {n} rows")

        if n < 10:
            # Very small — use all for training, CV only
            X_train, X_test = X, X
            y_train, y_test = y, y
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )

        # Try both algorithms, keep the one with lower CV MAPE
        rf_model, rf_mape = self._fit_rf(X_train, y_train)
        xgb_model, xgb_mape = self._fit_xgb(X_train, y_train)

        if xgb_model is not None and xgb_mape < rf_mape:
            best_model = xgb_model
            model_type = "XGBoost"
            cv_mape = xgb_mape
        else:
            best_model = rf_model
            model_type = "RandomForest"
            cv_mape = rf_mape

        self._model = best_model

        # Cross-validate for CI width
        cv_preds = self._cross_val_predict(X_train, y_train, best_model)
        residuals = np.abs(cv_preds - y_train)
        self._cv_std = float(np.std(residuals))

        # Train metrics
        train_preds = best_model.predict(X_train)
        train_mape = float(mean_absolute_percentage_error(y_train, train_preds))

        # Test metrics
        test_preds = best_model.predict(X_test)
        test_mape = float(mean_absolute_percentage_error(y_test, test_preds))
        test_r2 = float(r2_score(y_test, test_preds))

        # Feature importances
        importances = self.feature_importances()

        target_threshold = self.MAPE_TARGETS.get(self.scope_type, 0.25)
        target_met = test_mape <= target_threshold

        self._report = TrainingReport(
            scope_type=self.scope_type,
            model_type=model_type,
            n_training_rows=len(y_train),
            n_test_rows=len(y_test),
            train_mape=train_mape,
            test_mape=test_mape,
            test_r2=test_r2,
            cv_mape=cv_mape,
            feature_importances=importances,
            feature_names=feature_names,
            target_met=target_met,
        )

        logger.info(
            "%s scope_type=%s  train_mape=%.1f%%  test_mape=%.1f%%  R²=%.3f  target_met=%s",
            model_type,
            self.scope_type,
            train_mape * 100,
            test_mape * 100,
            test_r2,
            target_met,
        )
        return self._report

    def cross_validate(
        self,
        raw_data: list[dict[str, Any]] | None = None,
        feature_engineer: Any | None = None,
        k: int | None = None,
    ) -> dict[str, float]:
        """
        Run cross-validation and return metrics.

        k : None = auto-select (5 for ACT/AWP, 3 for 10-20 rows, LOOCV for <10)
        """
        from src.models.features import FeatureEngineer

        fe = (
            feature_engineer if feature_engineer is not None else FeatureEngineer(raw_data=raw_data)
        )
        X, y, _ = fe.get_training_data(
            scope_type=self.scope_type,
            target=self.target,
        )
        n = len(y)

        if k is None:
            if n >= 30:
                k = 5
            elif n >= 10:
                k = 3
            else:
                k = n  # LOOCV

        model = self._make_best_estimator()

        if k == n:
            cv = LeaveOneOut()
        else:
            cv = KFold(n_splits=k, shuffle=True, random_state=42)

        preds = cross_val_predict(model, X, y, cv=cv)
        mape = float(mean_absolute_percentage_error(y, preds))
        r2 = float(r2_score(y, preds))

        return {
            "cv_mape": mape,
            "cv_r2": r2,
            "n_folds": k,
            "n_samples": n,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, features_dict: dict[str, Any]) -> CostPrediction:
        """
        Predict cost/SF from a feature dict.

        Keys should match FEATURE_NAMES in FeatureEngineer.
        Missing keys are filled with sensible defaults.
        """
        if self._model is None:
            raise RuntimeError("Model not trained yet — call .train() first")

        # Build feature vector
        x = self._features_from_dict(features_dict)
        pred = float(self._model.predict(x.reshape(1, -1))[0])
        pred = max(0.5, pred)  # floor

        # Confidence interval: ±1.5 * cv_std, clipped to ≥0
        delta = 1.5 * self._cv_std
        ci = (max(0.0, pred - delta), pred + delta)

        return CostPrediction(
            predicted_cost_per_sf=round(pred, 4),
            confidence_interval=(round(ci[0], 4), round(ci[1], 4)),
            mape_on_test=self._report.test_mape if self._report else None,
            scope_type=self.scope_type,
            model_type=self._report.model_type if self._report else None,
        )

    # ------------------------------------------------------------------
    # Feature importances
    # ------------------------------------------------------------------

    def feature_importances(self) -> dict[str, float]:
        """Return {feature_name: importance} sorted descending."""
        if self._model is None:
            return {}
        try:
            imp = self._model.feature_importances_
        except AttributeError:
            return {}
        names = self._feature_names or [f"f{i}" for i in range(len(imp))]
        result = dict(zip(names, imp.tolist()))
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialise model + metadata to a joblib file."""
        payload = {
            "scope_type": self.scope_type,
            "target": self.target,
            "feature_names": self._feature_names,
            "cv_std": self._cv_std,
            "model": self._model,
            "report": self._report,
        }
        joblib.dump(payload, path)
        logger.info("Saved model to %s", path)

    @classmethod
    def load(cls, path: str) -> CostModel:
        """Load a previously saved model."""
        payload = joblib.load(path)
        obj = cls(
            scope_type=payload["scope_type"],
            target=payload["target"],
        )
        obj._feature_names = payload["feature_names"]
        obj._cv_std = payload["cv_std"]
        obj._model = payload["model"]
        obj._report = payload["report"]
        return obj

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fit_rf(self, X_train: np.ndarray, y_train: np.ndarray) -> tuple[Any, float]:
        """Fit RandomForest; return (model, cv_mape)."""
        n = len(y_train)
        n_estimators = 200 if n >= 30 else 100
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=None,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        cv_mape = self._quick_cv_mape(model, X_train, y_train)
        model.fit(X_train, y_train)
        return model, cv_mape

    def _fit_xgb(self, X_train: np.ndarray, y_train: np.ndarray) -> tuple[Any | None, float]:
        """Fit XGBoost; return (model, cv_mape) or (None, inf) if not available."""
        try:
            from xgboost import XGBRegressor
        except ImportError:
            logger.debug("xgboost not installed — skipping XGB")
            return None, float("inf")

        n = len(y_train)
        n_estimators = 300 if n >= 30 else 100
        model = XGBRegressor(
            n_estimators=n_estimators,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=2,
            random_state=42,
            verbosity=0,
            n_jobs=-1,
        )
        cv_mape = self._quick_cv_mape(model, X_train, y_train)
        model.fit(X_train, y_train)
        return model, cv_mape

    def _quick_cv_mape(self, estimator: Any, X: np.ndarray, y: np.ndarray) -> float:
        """3-fold CV MAPE for algorithm selection."""
        n = len(y)
        k = min(3, n)
        if k < 2:
            return float("inf")
        cv = KFold(n_splits=k, shuffle=True, random_state=42)
        try:
            preds = cross_val_predict(estimator, X, y, cv=cv)
            return float(mean_absolute_percentage_error(y, preds))
        except Exception as exc:
            logger.warning("CV failed: %s", exc)
            return float("inf")

    def _cross_val_predict(self, X: np.ndarray, y: np.ndarray, model: Any) -> np.ndarray:
        n = len(y)
        if n < 5:
            return model.predict(X)  # not enough for CV
        k = 5 if n >= 30 else (3 if n >= 10 else n)
        cv = LeaveOneOut() if k == n else KFold(n_splits=k, shuffle=True, random_state=42)
        try:
            # Clone to avoid refitting the actual model
            from sklearn.base import clone

            return cross_val_predict(clone(model), X, y, cv=cv)
        except Exception:
            return model.predict(X)

    def _make_best_estimator(self) -> Any:
        """Return a fresh estimator of the same type as the fitted model."""
        if self._model is None:
            return RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=42)
        if "XGB" in type(self._model).__name__:
            from xgboost import XGBRegressor

            return XGBRegressor(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            )
        return RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=42)

    def _features_from_dict(self, d: dict[str, Any]) -> np.ndarray:
        """Convert a user-facing dict to the feature vector expected by the model."""
        import numpy as np

        from src.models.features import (
            CHURCH_KEYWORDS,
            CURRENT_LABOR_RATE,
            EDUCATION_KEYWORDS,
            HEALTHCARE_KEYWORDS,
            FeatureEngineer,
            _keyword_flag,
            _product_tier,
        )

        sf = d.get("square_footage") or 1000.0
        log_sf = float(np.log1p(sf))

        # Scope type encoding — map to known int or default 0
        st = d.get("scope_type") or self.scope_type or "ACT"
        # We need the fitted label encoder; use a hardcoded fallback map
        ST_MAP = {
            "ACT": 0,
            "AP": 1,
            "AWP": 2,
            "Baffles": 3,
            "FW": 4,
            "Other": 5,
            "RPG": 6,
            "SM": 7,
            "WW": 8,
        }
        st_enc = ST_MAP.get(st, 0)

        labor_rate = d.get("daily_labor_rate")
        has_lr = labor_rate is not None and float(labor_rate) > 0
        lr_norm = float(labor_rate) / CURRENT_LABOR_RATE if has_lr else 1.0

        project_scope_count = int(d.get("project_scope_count") or 3)
        product_tier = _product_tier(d.get("product_name"))

        pn = d.get("project_name") or ""
        gc = d.get("gc_name") or ""
        is_health = int(_keyword_flag(pn, gc, HEALTHCARE_KEYWORDS))
        is_edu = int(_keyword_flag(pn, gc, EDUCATION_KEYWORDS))
        is_church = int(_keyword_flag(pn, gc, CHURCH_KEYWORDS))

        markup = d.get("markup_pct", 0.30)
        man_days_per_sf = float(d["man_days"]) / float(sf) if d.get("man_days") and sf else 0.003
        mat_cost = d.get("material_cost") or d.get("material_price") or 0.0
        material_cost_per_sf = float(mat_cost) / float(sf) if mat_cost and sf else 0.0

        # Build vector in same order as FEATURE_NAMES
        vec = np.array(
            [
                log_sf,
                st_enc,
                int(has_lr),
                lr_norm,
                project_scope_count,
                product_tier,
                is_health,
                is_edu,
                is_church,
                float(markup),
                man_days_per_sf,
                material_cost_per_sf,
            ],
            dtype=float,
        )

        # Slice to only the features the model was trained on
        if self._feature_names:
            fn = self._feature_names
            all_names = FeatureEngineer.FEATURE_NAMES
            idx = [all_names.index(f) for f in fn if f in all_names]
            vec = vec[idx]

        return vec
