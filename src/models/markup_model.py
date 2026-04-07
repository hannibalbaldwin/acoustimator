"""Markup prediction model for acoustic scope pricing.

Predicts the appropriate markup percentage for a given scope based on its
characteristics (scope type, size, project context, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# Scope types in a deterministic order for label encoding
SCOPE_TYPES = ["ACT", "AWP", "AP", "Baffles", "FW", "SM", "WW", "RPG", "Other", "UNKNOWN"]

# Keywords for project-type inference from project/GC names
HEALTHCARE_KEYWORDS = ["hospital", "medical", "health", "clinic", "surgery", "dental", "care"]
EDUCATION_KEYWORDS = [
    "school",
    "university",
    "college",
    "academy",
    "education",
    "learning",
    "elementary",
    "high school",
]
CHURCH_KEYWORDS = [
    "church",
    "chapel",
    "worship",
    "faith",
    "ministry",
    "cathedral",
    "synagogue",
    "mosque",
]


@dataclass
class MarkupPrediction:
    """Result of a markup prediction."""

    predicted_markup: float
    """Predicted markup as a decimal (e.g., 0.35 = 35%)."""

    low: float
    """Lower bound of the prediction interval (5th percentile estimate)."""

    high: float
    """Upper bound of the prediction interval (95th percentile estimate)."""

    confidence: float
    """Confidence score 0–1 (based on cross-validation consistency)."""

    scope_type: str | None = None
    """Scope type used for prediction."""


class MarkupModel:
    """Gradient boosting model to predict markup percentage for acoustic scopes.

    Features used:
    - scope_type_encoded: label-encoded scope type
    - log_square_footage: log(SF + 1) — normalises skewed area distribution
    - project_scope_count: number of scopes in the project (proxy for project complexity)
    - is_healthcare / is_education / is_church: inferred from project/GC name
    - labor_rate_normalized: daily_labor_rate / 700 (typical range 400–900)
    - has_cost_per_sf: binary flag (1 if cost_per_unit was provided)
    """

    MODEL_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._label_encoder = LabelEncoder()
        self._label_encoder.fit(SCOPE_TYPES)
        self._model: GradientBoostingRegressor | None = None
        self._cv_scores: np.ndarray | None = None
        self._feature_names: list[str] = [
            "scope_type_encoded",
            "log_square_footage",
            "project_scope_count",
            "is_healthcare",
            "is_education",
            "is_church",
            "labor_rate_normalized",
            "has_cost_per_sf",
        ]

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _encode_scope_type(self, scope_type: str | None) -> int:
        st = scope_type if scope_type in SCOPE_TYPES else "UNKNOWN"
        return int(self._label_encoder.transform([st])[0])

    @staticmethod
    def _infer_project_flags(
        project_name: str | None, gc_name: str | None
    ) -> tuple[int, int, int]:
        """Return (is_healthcare, is_education, is_church) from free-text fields."""
        text = " ".join(filter(None, [project_name, gc_name])).lower()
        is_healthcare = int(any(kw in text for kw in HEALTHCARE_KEYWORDS))
        is_education = int(any(kw in text for kw in EDUCATION_KEYWORDS))
        is_church = int(any(kw in text for kw in CHURCH_KEYWORDS))
        return is_healthcare, is_education, is_church

    def _build_feature_row(self, row: dict) -> list[float]:
        scope_type = row.get("scope_type")
        square_footage = row.get("square_footage") or 0.0
        project_scope_count = row.get("project_scope_count") or 1.0
        project_name = row.get("project_name")
        gc_name = row.get("gc_name")
        daily_labor_rate = row.get("daily_labor_rate") or 0.0
        cost_per_sf = row.get("cost_per_sf") or row.get("cost_per_unit")

        is_healthcare, is_education, is_church = self._infer_project_flags(project_name, gc_name)

        return [
            self._encode_scope_type(scope_type),
            float(np.log1p(square_footage)),
            float(project_scope_count),
            float(is_healthcare),
            float(is_education),
            float(is_church),
            float(daily_labor_rate) / 700.0,
            1.0 if cost_per_sf is not None and float(cost_per_sf) > 0 else 0.0,
        ]

    def _build_feature_matrix(self, records: list[dict]) -> np.ndarray:
        return np.array([self._build_feature_row(r) for r in records], dtype=np.float64)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, records: list[dict]) -> dict:
        """Train the model on historical scope records.

        Args:
            records: List of dicts with keys matching the DB query columns.

        Returns:
            Dict with training metrics (cv_mape, cv_r2, n_samples, feature_importances).
        """
        if not records:
            raise ValueError("No records provided for training.")

        X = self._build_feature_matrix(records)
        y = np.array([float(r["markup_pct"]) for r in records], dtype=np.float64)

        self._model = GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=5,
            subsample=0.8,
            loss="huber",
            random_state=42,
        )

        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        self._cv_scores = cross_val_score(self._model, X, y, cv=kf, scoring="r2")
        cv_mape_scores = cross_val_score(
            self._model, X, y, cv=kf, scoring="neg_mean_absolute_percentage_error"
        )

        self._model.fit(X, y)

        importances = dict(zip(self._feature_names, self._model.feature_importances_.tolist()))
        metrics = {
            "n_samples": len(records),
            "cv_r2_mean": float(np.mean(self._cv_scores)),
            "cv_r2_std": float(np.std(self._cv_scores)),
            "cv_mape_mean": float(-np.mean(cv_mape_scores)),
            "feature_importances": importances,
        }
        logger.info(
            "MarkupModel trained: n=%d, cv_r2=%.3f±%.3f, cv_mape=%.3f",
            metrics["n_samples"],
            metrics["cv_r2_mean"],
            metrics["cv_r2_std"],
            metrics["cv_mape_mean"],
        )
        return metrics

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, features_dict: dict) -> MarkupPrediction:
        """Predict markup for a single scope.

        Args:
            features_dict: Dict with optional keys:
                scope_type, square_footage, project_scope_count,
                project_name, gc_name, daily_labor_rate, cost_per_sf.

        Returns:
            MarkupPrediction with predicted_markup, low, high, confidence.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        x = np.array(self._build_feature_row(features_dict), dtype=np.float64).reshape(1, -1)
        pred = float(self._model.predict(x)[0])
        pred = float(np.clip(pred, 0.10, 1.00))

        # Estimate interval using staged predictions spread
        staged_preds = np.array(
            [float(stage_pred[0]) for stage_pred in self._model.staged_predict(x)]
        )
        # Use later half of staged predictions to estimate variance
        spread_std = float(np.std(staged_preds[len(staged_preds) // 2 :]))
        margin = max(spread_std * 1.96, 0.05)

        low = float(np.clip(pred - margin, 0.10, 1.00))
        high = float(np.clip(pred + margin, 0.10, 1.00))

        # Confidence: based on CV R² score (normalised 0–1)
        cv_r2 = float(np.mean(self._cv_scores)) if self._cv_scores is not None else 0.5
        confidence = float(np.clip(cv_r2, 0.0, 1.0))

        return MarkupPrediction(
            predicted_markup=round(pred, 4),
            low=round(low, 4),
            high=round(high, 4),
            confidence=round(confidence, 3),
            scope_type=features_dict.get("scope_type"),
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
            "version": self.MODEL_VERSION,
        }
        joblib.dump(payload, path)
        logger.info("MarkupModel saved to %s", path)

    @classmethod
    def load(cls, path: Path | str) -> MarkupModel:
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
        return instance
