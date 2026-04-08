"""Confidence scoring module for Acoustimator Phase 5.3.

Computes combined confidence scores from plan-reading and ML-model accuracy,
and generates human-readable flags and recommendations for the estimate UI.

No database dependency and no model loading — pure computation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from src.estimation.models import ScopeEstimate
from src.extraction.plan_parser.models import PlanReadResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLAN_WEIGHT: float = 0.6
MODEL_WEIGHT: float = 0.4

# Model accuracy scores (1 - MAPE) per scope type
_MODEL_ACCURACY: dict[str, float] = {
    "ACT": 0.87,  # 1 - 0.135
    "AWP": 0.82,  # 1 - 0.184
    "FW": 0.79,  # 1 - 0.21
}
_GENERAL_MODEL_ACCURACY: float = 0.73  # fallback (1 - 0.27)

# SF out-of-training-distribution bounds
_SF_MIN: float = 100.0
_SF_MAX: float = 50_000.0
_SF_OOD_PENALTY: float = 0.85

# ConfidenceLevel thresholds
_HIGH_THRESHOLD: float = 0.75
_MEDIUM_THRESHOLD: float = 0.50


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ConfidenceLevel(enum.StrEnum):
    HIGH = "high"  # >= 0.75
    MEDIUM = "medium"  # 0.50 – 0.74
    LOW = "low"  # < 0.50


@dataclass
class ConfidenceReport:
    overall_score: float  # 0.0–1.0
    level: ConfidenceLevel
    plan_reading_score: float  # from extraction_confidence
    model_score: float  # weighted by scope type accuracy
    flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def _level_from_score(score: float) -> ConfidenceLevel:
    """Map a numeric score to a ConfidenceLevel bucket."""
    if score >= _HIGH_THRESHOLD:
        return ConfidenceLevel.HIGH
    if score >= _MEDIUM_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _model_accuracy_for_scope(scope_type: str) -> float:
    """Return the model accuracy score for the given scope type."""
    return _MODEL_ACCURACY.get(scope_type.upper(), _GENERAL_MODEL_ACCURACY)


def _sf_penalty(area_sf: float | None) -> float:
    """Return 1.0 for in-distribution SF, _SF_OOD_PENALTY otherwise."""
    if area_sf is None:
        return 1.0
    if area_sf < _SF_MIN or area_sf > _SF_MAX:
        return _SF_OOD_PENALTY
    return 1.0


def compute_scope_confidence(
    plan_confidence: float,
    scope_type: str,
    area_sf: float | None,
    model_used: str,  # noqa: ARG001 — reserved for future per-model overrides
) -> float:
    """Compute a combined confidence score for a single scope estimate.

    Formula:
        plan_weight * plan_confidence + model_weight * model_score * sf_penalty

    Args:
        plan_confidence: Confidence extracted from the plan reader (0.0–1.0).
        scope_type: Scope category string, e.g. ``"ACT"``, ``"AWP"``, ``"FW"``.
        area_sf: Measured area in square feet; ``None`` if unknown.
        model_used: Name of the ML model used (reserved for future overrides).

    Returns:
        Combined confidence score in [0.0, 1.0].
    """
    model_score = _model_accuracy_for_scope(scope_type)
    penalty = _sf_penalty(area_sf)
    return PLAN_WEIGHT * plan_confidence + MODEL_WEIGHT * model_score * penalty


def compute_project_confidence(
    plan_result: PlanReadResult,
    scope_estimates: list[ScopeEstimate],
) -> ConfidenceReport:
    """Compute a full confidence report for a project estimate.

    Args:
        plan_result: Output of the plan-reading phase.
        scope_estimates: Per-scope estimate objects produced by the estimation
            engine.

    Returns:
        A :class:`ConfidenceReport` with scores, a level badge, flags, and
        recommendations.
    """
    plan_reading_score: float = plan_result.extraction_confidence

    # ------------------------------------------------------------------
    # Weighted-average model score (weight = area_sf; equal weight when None)
    # ------------------------------------------------------------------
    total_weight: float = 0.0
    weighted_model_sum: float = 0.0
    for scope in scope_estimates:
        weight = float(scope.area_sf) if scope.area_sf is not None else 1.0
        accuracy = _model_accuracy_for_scope(scope.scope_type)
        weighted_model_sum += accuracy * weight
        total_weight += weight

    model_score: float = weighted_model_sum / total_weight if total_weight > 0.0 else _GENERAL_MODEL_ACCURACY

    # ------------------------------------------------------------------
    # Overall score
    # ------------------------------------------------------------------
    overall_score: float = PLAN_WEIGHT * plan_reading_score + MODEL_WEIGHT * model_score
    level: ConfidenceLevel = _level_from_score(overall_score)

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------
    flags: list[str] = []

    scope_count = len(scope_estimates)

    if scope_count == 0:
        flags.append("No scopes extracted — plans may be raster-only or non-acoustic")
    else:
        # Low extraction confidence
        if plan_reading_score < 0.6:
            flags.append("Plan reading used keyword/text extraction only — review scope types manually")

        # Perfect confidence → Bluebeam annotations
        if plan_reading_score == 1.0:
            flags.append("Bluebeam annotations found — high SF accuracy")

        # Per-scope low confidence
        low_conf_tags = [s.scope_tag for s in scope_estimates if s.confidence < 0.5]
        if low_conf_tags:
            flags.append(f"{len(low_conf_tags)} scope(s) flagged as low confidence: " + ", ".join(low_conf_tags))

        # Scopes using the general (fallback) model
        general_model_scopes = [s for s in scope_estimates if s.scope_type.upper() not in _MODEL_ACCURACY]
        if general_model_scopes:
            unique_types = sorted({s.scope_type for s in general_model_scopes})
            flags.append(
                f"{len(general_model_scopes)} scope(s) estimated with general model "
                f"— less accurate for {', '.join(unique_types)}"
            )

    # Missing total SF
    if plan_result.total_area_sf is None:
        flags.append("No total SF extracted from plans — manual SF verification required")

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    recommendations: list[str] = []

    if level == ConfidenceLevel.LOW:
        recommendations.append("Upload Bluebeam-annotated takeoff drawings for best accuracy")
    elif level == ConfidenceLevel.MEDIUM:
        recommendations.append("Review highlighted scopes before sending quote")
    else:  # HIGH
        recommendations.append("Estimate ready for review — verify product selections")

    return ConfidenceReport(
        overall_score=overall_score,
        level=level,
        plan_reading_score=plan_reading_score,
        model_score=model_score,
        flags=flags,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# UI helper
# ---------------------------------------------------------------------------

_BADGE_EMOJI: dict[ConfidenceLevel, str] = {
    ConfidenceLevel.HIGH: "🟢",
    ConfidenceLevel.MEDIUM: "🟡",
    ConfidenceLevel.LOW: "🔴",
}

_BADGE_LABEL: dict[ConfidenceLevel, str] = {
    ConfidenceLevel.HIGH: "High",
    ConfidenceLevel.MEDIUM: "Medium",
    ConfidenceLevel.LOW: "Low",
}


def format_confidence_badge(score: float) -> str:
    """Return a short emoji + label string for the estimate UI.

    Examples::

        format_confidence_badge(0.87)  # "🟢 High (87%)"
        format_confidence_badge(0.61)  # "🟡 Medium (61%)"
        format_confidence_badge(0.34)  # "🔴 Low (34%)"

    Args:
        score: Confidence score in [0.0, 1.0].

    Returns:
        Formatted badge string.
    """
    level = _level_from_score(score)
    pct = round(score * 100)
    return f"{_BADGE_EMOJI[level]} {_BADGE_LABEL[level]} ({pct}%)"
