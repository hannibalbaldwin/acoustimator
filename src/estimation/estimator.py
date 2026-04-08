"""Core plan-to-estimate pipeline for Acoustimator (Phase 5.1).

Public functions
----------------
estimate_from_plan_result(plan_result, ...) -> ProjectEstimate
    Convert a PlanReadResult (from Phase 4) into a full cost estimate.

estimate_from_pdf(pdf_path, ...) -> ProjectEstimate
    Convenience wrapper: read_plan → estimate_from_plan_result.
"""

from __future__ import annotations

import csv
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded model singletons
# ---------------------------------------------------------------------------

_cost_models: dict[str, Any] = {}  # keyed by model name, e.g. "ACT_cost_model"
_markup_model: Any = None
_labor_model: Any = None

# Scope types that have dedicated cost models
_DEDICATED_MODEL_SCOPE_TYPES: frozenset[str] = frozenset({"ACT", "AWP", "AP", "FW"})


def _models_dir() -> Path:
    """Return the directory that holds the .joblib model files.

    Uses config.settings when available; falls back to a relative path so the
    module can be imported in environments without a .env file.
    """
    try:
        from src.config import settings

        base = Path(str(settings.data_source_path)).parent  # data/raw → data/
        candidate = base / "models"
        if candidate.exists():
            return candidate
    except Exception:
        pass
    # Fallback: repo root relative path
    here = Path(__file__).resolve().parent  # src/estimation/
    return here.parent.parent / "data" / "models"


def _load_cost_model(model_name: str) -> Any | None:
    """Load (and cache) a CostModel by name, e.g. 'ACT_cost_model'.

    Returns None if the file does not exist rather than raising.
    """
    if model_name in _cost_models:
        return _cost_models[model_name]

    try:
        from src.models.cost_model import CostModel
    except ImportError:
        logger.warning("ML dependencies not available; cost model disabled")
        _cost_models[model_name] = None
        return None

    path = _models_dir() / f"{model_name}.joblib"
    if not path.exists():
        logger.warning("Cost model file not found: %s", path)
        _cost_models[model_name] = None
        return None

    try:
        model = CostModel.load(str(path))
        _cost_models[model_name] = model
        logger.info("Loaded cost model: %s", model_name)
        return model
    except Exception as exc:
        logger.error("Failed to load cost model %s: %s", model_name, exc)
        _cost_models[model_name] = None
        return None


def _get_markup_model() -> Any | None:
    """Lazy-load the shared MarkupModel singleton."""
    global _markup_model
    if _markup_model is not None:
        return _markup_model

    try:
        from src.models.markup_model import MarkupModel
    except ImportError:
        logger.warning("ML dependencies not available; markup model disabled")
        return None

    path = _models_dir() / "markup_model.joblib"
    if not path.exists():
        logger.warning("Markup model file not found: %s", path)
        return None

    try:
        _markup_model = MarkupModel.load(str(path))
        logger.info("Loaded markup model")
        return _markup_model
    except Exception as exc:
        logger.error("Failed to load markup model: %s", exc)
        return None


def _get_labor_model() -> Any | None:
    """Lazy-load the shared LaborModel singleton."""
    global _labor_model
    if _labor_model is not None:
        return _labor_model

    try:
        from src.models.labor_model import LaborModel
    except ImportError:
        logger.warning("ML dependencies not available; labor model disabled")
        return None

    path = _models_dir() / "labor_model.joblib"
    if not path.exists():
        logger.warning("Labor model file not found: %s", path)
        return None

    try:
        _labor_model = LaborModel.load(str(path))
        logger.info("Loaded labor model")
        return _labor_model
    except Exception as exc:
        logger.error("Failed to load labor model: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Comparable projects lookup
# ---------------------------------------------------------------------------

_training_rows: list[dict[str, Any]] | None = None


def _get_training_rows() -> list[dict[str, Any]]:
    """Load training_data.csv once and cache in memory."""
    global _training_rows
    if _training_rows is not None:
        return _training_rows

    csv_path = _models_dir() / "training_data.csv"
    if not csv_path.exists():
        logger.warning("training_data.csv not found at %s", csv_path)
        _training_rows = []
        return _training_rows

    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            _training_rows = [row for row in reader]
        logger.info("Loaded %d training rows for comparable lookup", len(_training_rows))
    except Exception as exc:
        logger.warning("Could not load training_data.csv: %s", exc)
        _training_rows = []

    return _training_rows


def _find_comparable_projects(scope_type: str, area_sf: float, top_n: int = 3) -> list[str]:
    """Return top_n historical project names with the closest area and same scope type."""
    rows = _get_training_rows()
    if not rows:
        return []

    candidates: list[tuple[float, str]] = []
    for row in rows:
        if row.get("scope_type") != scope_type:
            continue
        pname = row.get("project_name") or ""
        if not pname:
            continue
        try:
            row_sf = float(row.get("square_footage") or 0)
        except (TypeError, ValueError):
            continue
        if row_sf <= 0:
            continue
        dist = abs(row_sf - area_sf)
        candidates.append((dist, pname))

    # Sort by distance, deduplicate project names, take top_n
    candidates.sort(key=lambda t: t[0])
    seen: set[str] = set()
    result: list[str] = []
    for _, name in candidates:
        if name not in seen:
            seen.add(name)
            result.append(name)
        if len(result) >= top_n:
            break

    return result


# ---------------------------------------------------------------------------
# Heuristic fallbacks (used when a model file is missing)
# ---------------------------------------------------------------------------

# Median cost/SF by scope type (from training data analysis)
_HEURISTIC_COST_PER_SF: dict[str, float] = {
    "ACT": 6.50,
    "AWP": 18.00,
    "AP": 22.00,
    "FW": 14.00,
    "WW": 45.00,
    "Baffles": 30.00,
    "RPG": 55.00,
    "SM": 12.00,
}
_HEURISTIC_COST_PER_SF_DEFAULT = 12.00

_HEURISTIC_MARKUP: dict[str, float] = {
    "ACT": 0.30,
    "AWP": 0.35,
    "AP": 0.35,
    "FW": 0.35,
    "WW": 0.45,
    "Baffles": 0.40,
    "RPG": 0.50,
    "SM": 0.40,
}
_HEURISTIC_MARKUP_DEFAULT = 0.33

# Man-days per 1,000 SF heuristic
_HEURISTIC_MD_PER_1KSF: dict[str, float] = {
    "ACT": 0.70,
    "AWP": 1.80,
    "AP": 2.00,
    "FW": 1.50,
    "WW": 3.00,
    "Baffles": 2.50,
    "RPG": 4.00,
    "SM": 1.00,
}
_HEURISTIC_MD_PER_1KSF_DEFAULT = 1.20


def _to_decimal(v: float | int | None) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(round(v, 4)))
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Core scope estimation
# ---------------------------------------------------------------------------


def _cost_model_name(scope_type: str) -> tuple[str, float]:
    """Return (model_name, model_confidence) for a scope type.

    model_confidence is 1.0 for dedicated models, 0.6 for general.
    """
    if scope_type in _DEDICATED_MODEL_SCOPE_TYPES:
        return f"{scope_type}_cost_model", 1.0
    return "general_cost_model", 0.6


def _estimate_scope(
    scope: Any,
    project_scope_count: int,
    daily_labor_rate: float,
    sales_tax_pct: float,
) -> tuple[Any, list[str]]:
    """Estimate a single ScopeSuggestion.  Returns (ScopeEstimate, notes)."""
    from src.estimation.models import ScopeEstimate

    scope_type: str = scope.scope_type
    scope_tag: str = scope.scope_tag
    area_sf_decimal: Decimal | None = scope.area_sf
    product_hint: str | None = scope.product_hint
    plan_confidence: float = scope.confidence

    area_sf_float = float(area_sf_decimal) if area_sf_decimal is not None else None
    notes: list[str] = []

    model_name, model_confidence = _cost_model_name(scope_type)
    combined_confidence = 0.6 * plan_confidence + 0.4 * model_confidence

    # --- Predict cost/SF ---
    cost_per_sf: float | None = None
    cost_model = _load_cost_model(model_name)

    if cost_model is not None and area_sf_float is not None:
        try:
            features: dict[str, Any] = {
                "square_footage": area_sf_float,
                "scope_type": scope_type,
                "product_name": product_hint,
                "daily_labor_rate": daily_labor_rate,
                "project_scope_count": project_scope_count,
                "markup_pct": _HEURISTIC_MARKUP.get(scope_type, _HEURISTIC_MARKUP_DEFAULT),
            }
            cost_pred = cost_model.predict(features)
            cost_per_sf = cost_pred.predicted_cost_per_sf
        except Exception as exc:
            logger.warning("CostModel.predict failed for %s: %s", scope_tag, exc)
            notes.append(f"{scope_tag}: cost model prediction failed — using heuristic")
    else:
        if cost_model is None:
            notes.append(f"{scope_tag}: {model_name} not available — using heuristic")

    if cost_per_sf is None:
        cost_per_sf = _HEURISTIC_COST_PER_SF.get(scope_type, _HEURISTIC_COST_PER_SF_DEFAULT)
        # Heuristic model names are flagged separately
        model_name = f"{model_name}[heuristic]"

    # --- Predict markup ---
    markup_pct: float | None = None
    markup_model = _get_markup_model()

    if markup_model is not None and area_sf_float is not None:
        try:
            markup_features: dict[str, Any] = {
                "scope_type": scope_type,
                "square_footage": area_sf_float,
                "project_scope_count": project_scope_count,
                "daily_labor_rate": daily_labor_rate,
                "cost_per_sf": cost_per_sf,
            }
            markup_pred = markup_model.predict(markup_features)
            markup_pct = markup_pred.predicted_markup
        except Exception as exc:
            logger.warning("MarkupModel.predict failed for %s: %s", scope_tag, exc)

    if markup_pct is None:
        markup_pct = _HEURISTIC_MARKUP.get(scope_type, _HEURISTIC_MARKUP_DEFAULT)

    # --- Predict man-days ---
    man_days: float | None = None
    labor_model = _get_labor_model()

    if labor_model is not None and area_sf_float is not None:
        try:
            labor_pred = labor_model.predict(
                scope_type=scope_type,
                square_footage=area_sf_float,
                product_name=product_hint,
                daily_labor_rate=daily_labor_rate,
                project_scope_count=project_scope_count,
            )
            man_days = labor_pred.man_days
        except Exception as exc:
            logger.warning("LaborModel.predict failed for %s: %s", scope_tag, exc)

    if man_days is None and area_sf_float is not None:
        rate = _HEURISTIC_MD_PER_1KSF.get(scope_type, _HEURISTIC_MD_PER_1KSF_DEFAULT)
        man_days = area_sf_float / 1000.0 * rate

    # --- Compute costs ---
    material_cost: float | None = None
    labor_cost: float | None = None
    total: float | None = None

    if area_sf_float is not None and cost_per_sf is not None and markup_pct is not None:
        # cost_per_sf is the TOTAL $/SF (includes markup).  Back out material:
        # total_per_sf = material_per_sf * (1 + markup_pct)
        # → material_per_sf = total_per_sf / (1 + markup_pct)
        material_per_sf = cost_per_sf / (1.0 + markup_pct)
        material_cost = area_sf_float * material_per_sf
        labor_cost = (man_days or 0.0) * daily_labor_rate
        total = material_cost * (1.0 + markup_pct) + labor_cost + material_cost * sales_tax_pct

    # --- Comparable projects ---
    comparables: list[str] = []
    if area_sf_float is not None:
        comparables = _find_comparable_projects(scope_type, area_sf_float)

    return ScopeEstimate(
        scope_tag=scope_tag,
        scope_type=scope_type,
        area_sf=area_sf_decimal,
        product_hint=product_hint,
        predicted_cost_per_sf=_to_decimal(cost_per_sf),
        predicted_markup_pct=_to_decimal(markup_pct),
        predicted_man_days=_to_decimal(man_days),
        material_cost=_to_decimal(material_cost),
        labor_cost=_to_decimal(labor_cost),
        total=_to_decimal(total),
        confidence=round(combined_confidence, 4),
        model_used=model_name,
        comparable_projects=comparables,
    ), notes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_from_plan_result(
    plan_result: Any,
    daily_labor_rate: float = 725.0,
    sales_tax_pct: float = 0.075,
) -> Any:
    """Convert a PlanReadResult into a ProjectEstimate.

    Parameters
    ----------
    plan_result :
        A ``PlanReadResult`` instance returned by ``src.extraction.plan_reader.read_plan``.
    daily_labor_rate :
        Crew day rate in USD.  Defaults to the current Commercial Acoustics rate ($725/day).
    sales_tax_pct :
        FL sales tax fraction applied to material cost.  Defaults to 7.5 %.

    Returns
    -------
    ProjectEstimate
    """
    from src.estimation.models import ProjectEstimate

    scope_suggestions = plan_result.scope_suggestions or []
    project_scope_count = len(scope_suggestions)
    all_notes: list[str] = []

    if not scope_suggestions:
        all_notes.append("No scope suggestions found in plan — estimate is empty.")

    if plan_result.extraction_confidence < 0.5:
        all_notes.append(
            f"Low plan extraction confidence ({plan_result.extraction_confidence:.0%}); estimates may be inaccurate."
        )

    scope_estimates = []

    for scope in scope_suggestions:
        # Skip low-confidence or area-less scopes
        if scope.confidence < 0.3:
            logger.debug("Skipping scope %s: confidence %.2f < 0.3", scope.scope_tag, scope.confidence)
            all_notes.append(f"Skipped {scope.scope_tag}: plan confidence {scope.confidence:.0%} too low.")
            continue

        if scope.area_sf is None or scope.area_sf <= 0:
            logger.debug("Skipping scope %s: no area_sf", scope.scope_tag)
            all_notes.append(f"Skipped {scope.scope_tag}: no measurable area — cannot estimate.")
            continue

        se, scope_notes = _estimate_scope(
            scope=scope,
            project_scope_count=project_scope_count,
            daily_labor_rate=daily_labor_rate,
            sales_tax_pct=sales_tax_pct,
        )
        all_notes.extend(scope_notes)
        scope_estimates.append(se)

        if se.confidence < 0.5:
            all_notes.append(f"Low confidence on {scope.scope_tag} ({se.confidence:.0%}): review estimate carefully.")

    # Aggregate totals
    total_cost = Decimal("0")
    total_man_days = Decimal("0")
    total_area: Decimal | None = None

    for se in scope_estimates:
        if se.total is not None:
            total_cost += se.total
        if se.predicted_man_days is not None:
            total_man_days += se.predicted_man_days
        if se.area_sf is not None:
            total_area = (total_area or Decimal("0")) + se.area_sf

    # Use plan reader's total_area_sf if we couldn't aggregate from scopes
    if total_area is None and plan_result.total_area_sf is not None:
        total_area = plan_result.total_area_sf

    return ProjectEstimate(
        source_plan=plan_result.source_file,
        extraction_confidence=plan_result.extraction_confidence,
        scope_estimates=scope_estimates,
        total_estimated_cost=total_cost,
        total_area_sf=total_area,
        estimated_man_days=total_man_days,
        notes=all_notes,
        created_at=datetime.now(tz=UTC),
    )


def estimate_from_pdf(
    pdf_path: str | Path,
    use_vision: bool = False,
    daily_labor_rate: float = 725.0,
    sales_tax_pct: float = 0.075,
) -> Any:
    """Read a plan PDF and produce a full ProjectEstimate in one call.

    Parameters
    ----------
    pdf_path :
        Path to the architectural drawing PDF.
    use_vision :
        Pass ``True`` to enable the Claude Vision API fallback for raster pages
        (incurs API cost).  Defaults to ``False``.
    daily_labor_rate :
        Crew day rate in USD.
    sales_tax_pct :
        FL sales tax fraction applied to material cost.

    Returns
    -------
    ProjectEstimate
    """
    from src.extraction.plan_reader import read_plan

    pdf_path = Path(pdf_path)
    logger.info("Reading plan: %s", pdf_path)
    plan_result = read_plan(pdf_path, use_vision=use_vision)

    return estimate_from_plan_result(
        plan_result,
        daily_labor_rate=daily_labor_rate,
        sales_tax_pct=sales_tax_pct,
    )
