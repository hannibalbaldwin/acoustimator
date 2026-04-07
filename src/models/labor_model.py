"""Labor estimation model for acoustic scope man-days prediction.

Predicts man-days from scope parameters (SF, scope type, product complexity).
Key insight: labor has a fixed setup component + a scaling production component (non-linear).
The model uses log(SF) as a primary feature to capture this fixed+scaling structure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# Scope types in a deterministic order for label encoding
SCOPE_TYPES = ["ACT", "AWP", "AP", "Baffles", "FW", "SM", "WW", "RPG", "Other", "UNKNOWN"]

# Product tier mapping — higher tier = more complex/specialty installation
# 0 = unknown, 1 = basic/commodity, 2 = mid-tier, 3 = specialty
PRODUCT_TIER_KEYWORDS = {
    3: [
        "woodworks",
        "wood",
        "rpg",
        "diffuser",
        "arktura",
        "atmosphera",
        "baffle",
        "clouds",
        "baffles",
        "specialty",
    ],
    2: [
        "mdc",
        "embossed",
        "fabric",
        "fw",
        "snap-tex",
        "snaptex",
        "vektor",
        "lencore",
        "masking",
        "sound masking",
        "spektrum",
    ],
    1: [
        "ultima",
        "optima",
        "cortega",
        "classic",
        "standard",
        "basic",
        "layin",
        "lay-in",
        "prelude",
        "tegular",
        "beveled",
    ],
}

# Current labor rate for normalization
CURRENT_LABOR_RATE = 725.0


def infer_product_tier(product_name: str | None, scope_type: str | None) -> int:
    """Infer product complexity tier 0-3 from product name and scope type."""
    if not product_name and not scope_type:
        return 0

    text = " ".join(filter(None, [product_name, scope_type])).lower()

    for tier, keywords in sorted(PRODUCT_TIER_KEYWORDS.items(), reverse=True):
        if any(kw in text for kw in keywords):
            return tier

    # Fallback by scope type
    if scope_type in ("WW", "RPG", "Baffles"):
        return 3
    if scope_type in ("SM", "FW", "AP"):
        return 2
    if scope_type in ("ACT", "AWP"):
        return 1

    return 1  # default to basic


@dataclass
class LaborPrediction:
    """Result of a labor man-days prediction."""

    man_days: float
    """Predicted man-days."""

    low: float
    """Lower bound of prediction interval (approx 10th percentile)."""

    high: float
    """Upper bound of prediction interval (approx 90th percentile)."""

    man_days_per_1000sf: float | None = None
    """Man-days per 1,000 SF (if SF was provided)."""

    scope_type: str | None = None
    """Scope type used for prediction."""

    product_tier: int | None = None
    """Product complexity tier used (0-3)."""


class LaborModel:
    """Random forest model to predict man-days for acoustic installation scopes.

    Features used:
    - scope_type_encoded: label-encoded scope type
    - log_square_footage: log1p(SF) — captures fixed setup + scaling production
    - product_tier: 0/1/2/3 product complexity (specialty=3, basic ACT=1)
    - labor_rate_normalized: daily_labor_rate / 725 (current rate)
    - project_scope_count: number of scopes in project (complexity proxy)
    - has_square_footage: binary flag

    The model targets log1p(man_days) internally for better residuals,
    then exponentiates for output.
    """

    MODEL_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._label_encoder = LabelEncoder()
        self._label_encoder.fit(SCOPE_TYPES)
        self._model: RandomForestRegressor | None = None
        self._cv_scores: np.ndarray | None = None
        self._train_residual_std: float = 0.0
        self._feature_names: list[str] = [
            "scope_type_encoded",
            "log_square_footage",
            "product_tier",
            "labor_rate_normalized",
            "project_scope_count",
            "has_square_footage",
        ]

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _encode_scope_type(self, scope_type: str | None) -> int:
        st = scope_type if scope_type in SCOPE_TYPES else "UNKNOWN"
        return int(self._label_encoder.transform([st])[0])

    def _build_feature_row(self, row: dict) -> list[float]:
        scope_type = row.get("scope_type")
        square_footage = row.get("square_footage") or 0.0
        product_name = row.get("product_name")
        daily_labor_rate = row.get("daily_labor_rate") or CURRENT_LABOR_RATE
        project_scope_count = row.get("project_scope_count") or 1.0

        product_tier = infer_product_tier(product_name, scope_type)
        has_sf = 1.0 if float(square_footage) > 0 else 0.0

        return [
            float(self._encode_scope_type(scope_type)),
            float(np.log1p(square_footage)),
            float(product_tier),
            float(daily_labor_rate) / CURRENT_LABOR_RATE,
            float(project_scope_count),
            has_sf,
        ]

    def _build_feature_matrix(self, records: list[dict]) -> np.ndarray:
        return np.array([self._build_feature_row(r) for r in records], dtype=np.float64)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, records: list[dict]) -> dict:
        """Train the model on historical scope records.

        Args:
            records: List of dicts with keys: scope_type, product_name, square_footage,
                     man_days, daily_labor_rate, project_scope_count, project_name.

        Returns:
            Dict with training metrics.
        """
        if not records:
            raise ValueError("No records provided for training.")

        X = self._build_feature_matrix(records)
        # Target: log1p(man_days) for better residual distribution
        y_raw = np.array([float(r["man_days"]) for r in records], dtype=np.float64)
        y = np.log1p(y_raw)

        self._model = RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=3,
            min_samples_split=5,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1,
        )

        kf = KFold(n_splits=5, shuffle=True, random_state=42)

        # CV on log scale — report R²
        cv_r2 = cross_val_score(self._model, X, y, cv=kf, scoring="r2")
        self._cv_scores = cv_r2

        # CV MAPE on original scale via manual loop
        mape_scores = []
        for train_idx, val_idx in kf.split(X):
            m = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                min_samples_leaf=3,
                min_samples_split=5,
                max_features="sqrt",
                random_state=42,
                n_jobs=-1,
            )
            m.fit(X[train_idx], y[train_idx])
            preds = np.expm1(m.predict(X[val_idx]))
            actuals = y_raw[val_idx]
            # MAPE clipped to avoid division by near-zero
            mape = np.mean(np.abs(preds - actuals) / np.maximum(actuals, 0.5))
            mape_scores.append(mape)

        self._model.fit(X, y)

        # Compute training residual std for prediction intervals
        train_preds_log = self._model.predict(X)
        self._train_residual_std = float(np.std(y - train_preds_log))

        importances = dict(zip(self._feature_names, self._model.feature_importances_.tolist(), strict=False))
        metrics = {
            "n_samples": len(records),
            "cv_r2_mean": float(np.mean(cv_r2)),
            "cv_r2_std": float(np.std(cv_r2)),
            "cv_mape_mean": float(np.mean(mape_scores)),
            "cv_mape_std": float(np.std(mape_scores)),
            "train_residual_std_log": self._train_residual_std,
            "feature_importances": importances,
        }
        logger.info(
            "LaborModel trained: n=%d, cv_r2=%.3f±%.3f, cv_mape=%.3f",
            metrics["n_samples"],
            metrics["cv_r2_mean"],
            metrics["cv_r2_std"],
            metrics["cv_mape_mean"],
        )
        return metrics

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        scope_type: str | None,
        square_footage: float = 0.0,
        product_name: str | None = None,
        daily_labor_rate: float = CURRENT_LABOR_RATE,
        project_scope_count: int = 3,
    ) -> LaborPrediction:
        """Predict man-days for a scope.

        Args:
            scope_type: Scope type string (e.g. 'ACT', 'AWP', 'FW').
            square_footage: Area in square feet (0 if not applicable).
            product_name: Optional product name for tier inference.
            daily_labor_rate: Crew day rate (defaults to current $725/day).
            project_scope_count: Number of scopes in the project (default 3).

        Returns:
            LaborPrediction with man_days, low, high.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        row = {
            "scope_type": scope_type,
            "square_footage": square_footage,
            "product_name": product_name,
            "daily_labor_rate": daily_labor_rate,
            "project_scope_count": project_scope_count,
        }
        x = np.array(self._build_feature_row(row), dtype=np.float64).reshape(1, -1)

        # Get per-tree predictions for natural prediction interval
        tree_preds_log = np.array([tree.predict(x)[0] for tree in self._model.estimators_])
        pred_log = float(np.mean(tree_preds_log))
        pred_std_log = float(np.std(tree_preds_log))

        # Use max of tree spread and training residual std for robust interval
        interval_std = max(pred_std_log, self._train_residual_std * 0.5)

        man_days = float(np.expm1(pred_log))
        low = float(np.expm1(max(pred_log - 1.28 * interval_std, 0.0)))  # ~10th pct
        high = float(np.expm1(pred_log + 1.28 * interval_std))  # ~90th pct

        # Floor at 0.25 days (minimum viable installation visit)
        man_days = max(man_days, 0.25)
        low = max(low, 0.1)

        md_per_1k: float | None = None
        if square_footage and square_footage > 0:
            md_per_1k = round(man_days / (square_footage / 1000.0), 3)

        product_tier = infer_product_tier(product_name, scope_type)

        return LaborPrediction(
            man_days=round(man_days, 2),
            low=round(low, 2),
            high=round(high, 2),
            man_days_per_1000sf=md_per_1k,
            scope_type=scope_type,
            product_tier=product_tier,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str) -> None:
        """Serialise the trained model to disk."""
        if self._model is None:
            raise RuntimeError("Model has not been trained yet.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self._model,
            "cv_scores": self._cv_scores,
            "label_encoder": self._label_encoder,
            "feature_names": self._feature_names,
            "train_residual_std": self._train_residual_std,
            "version": self.MODEL_VERSION,
        }
        joblib.dump(payload, path)
        logger.info("LaborModel saved to %s", path)

    @classmethod
    def load(cls, path: Path | str) -> LaborModel:
        """Load a serialised model from disk."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        payload = joblib.load(path)
        instance = cls()
        instance._model = payload["model"]
        instance._cv_scores = payload["cv_scores"]
        instance._label_encoder = payload["label_encoder"]
        instance._feature_names = payload["feature_names"]
        instance._train_residual_std = payload.get("train_residual_std", 0.0)
        return instance
