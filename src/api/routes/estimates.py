"""Routes for estimate creation, retrieval, and scope management."""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_db
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.estimates import (
    ComparableProjectResponse,
    EstimateListItem,
    EstimateResponse,
    RecordActualRequest,
    ScopeResponse,
    UpdateEstimateBody,
    UpdateScopeRequest,
)
from src.api.schemas.exports import QuoteRequest
from src.db.models import Estimate, EstimateScope, EstimateStatus, Project, Quote
from src.estimation.catalog import is_known_product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


async def _fetch_estimate_or_404(estimate_id: UUID, db: AsyncSession) -> Estimate:
    """Fetch an Estimate with its scopes, or raise 404."""
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id).options(selectinload(Estimate.estimate_scopes))
    )
    estimate = result.scalar_one_or_none()
    if estimate is None:
        raise HTTPException(status_code=404, detail=f"Estimate {estimate_id} not found")
    return estimate


async def _build_response(estimate: Estimate, db: AsyncSession) -> EstimateResponse:
    """Build an EstimateResponse from an ORM Estimate (with loaded scopes)."""
    scopes = estimate.estimate_scopes or []

    total_cost = float(estimate.total_estimate) if estimate.total_estimate is not None else None
    confidence_score = float(estimate.overall_confidence) if estimate.overall_confidence is not None else None

    # Compute total_sf and man_days from scope estimates
    total_sf: float | None = None
    man_days_total: float | None = None
    sf_sum = Decimal(0)
    md_sum = Decimal(0)
    for s in scopes:
        if s.square_footage is not None:
            sf_sum += s.square_footage
        if s.man_days is not None:
            md_sum += s.man_days
    if sf_sum > 0:
        total_sf = float(sf_sum)
    if md_sum > 0:
        man_days_total = float(md_sum)

    cost_per_sf: float | None = None
    if total_cost and total_sf and total_sf > 0:
        cost_per_sf = total_cost / total_sf

    # Gather comparable project IDs from scope annotations
    comparable_ids: list[str] = []
    for s in scopes:
        ids = s.comparable_project_ids or []
        comparable_ids.extend(str(i) for i in ids)
    comparable_ids = list(dict.fromkeys(comparable_ids))[:5]  # deduplicate, cap at 5

    # Enrich comparable projects with DB data
    comparable_projects: list[ComparableProjectResponse] = []
    if comparable_ids:
        try:
            uuid_list = [UUID(cid) for cid in comparable_ids]
            proj_result = await db.execute(
                select(Project).options(selectinload(Project.scopes)).where(Project.id.in_(uuid_list))
            )
            projects = proj_result.scalars().all()
            proj_map = {str(p.id): p for p in projects}
            for cid in comparable_ids:
                p = proj_map.get(cid)
                if p is None:
                    continue
                # Derive year from quote_date
                year = p.quote_date.year if p.quote_date else None
                # Use first scope's cost_per_sf as representative (if loaded)
                scope_type_val: str | None = None
                area_sf_val: float | None = None
                cost_per_sf_val: float | None = None
                total_cost_val: float | None = None
                if hasattr(p, "scopes") and p.scopes:
                    first_scope = p.scopes[0]
                    scope_type_val = str(first_scope.scope_type) if first_scope.scope_type else None
                    area_sf_val = float(first_scope.square_footage) if first_scope.square_footage else None
                    cost_per_sf_val = float(first_scope.cost_per_unit) if first_scope.cost_per_unit else None
                    total_cost_val = float(first_scope.total) if first_scope.total else None
                comparable_projects.append(
                    ComparableProjectResponse(
                        id=cid,
                        folder_name=p.folder_name or p.name,
                        scope_type=scope_type_val,
                        area_sf=area_sf_val,
                        cost_per_sf=cost_per_sf_val,
                        total_cost=total_cost_val,
                        year=year,
                        similarity_score=0.8,
                    )
                )
        except Exception:
            logger.warning("Failed to enrich comparable projects", exc_info=True)

    # Fallback: parse comparable names from ai_notes if no comparable_project_ids
    if not comparable_ids:
        name_hints: list[str] = []
        for s in scopes:
            if s.ai_notes:
                # ai_notes stores names like "Brandon Library; Seven Rivers HS"
                parts = [p.strip() for p in s.ai_notes.split(";") if p.strip()]
                name_hints.extend(parts)
        name_hints = list(dict.fromkeys(name_hints))[:5]  # deduplicate, cap at 5

        if name_hints:
            try:
                conditions = [func.lower(Project.name).contains(hint.lower()) for hint in name_hints]
                proj_result = await db.execute(
                    select(Project).options(selectinload(Project.scopes)).where(or_(*conditions)).limit(5)
                )
                found_projects = proj_result.scalars().all()
                for p in found_projects:
                    year = p.quote_date.year if p.quote_date else None
                    scope_type_val: str | None = None
                    area_sf_val: float | None = None
                    cost_per_sf_val: float | None = None
                    total_cost_val: float | None = None
                    if hasattr(p, "scopes") and p.scopes:
                        first_scope = p.scopes[0]
                        scope_type_val = str(first_scope.scope_type) if first_scope.scope_type else None
                        area_sf_val = float(first_scope.square_footage) if first_scope.square_footage else None
                        cost_per_sf_val = float(first_scope.cost_per_unit) if first_scope.cost_per_unit else None
                        total_cost_val = float(first_scope.total) if first_scope.total else None
                    comparable_projects.append(
                        ComparableProjectResponse(
                            id=str(p.id),
                            folder_name=p.folder_name or p.name or "",
                            scope_type=scope_type_val,
                            area_sf=area_sf_val,
                            cost_per_sf=cost_per_sf_val,
                            total_cost=total_cost_val,
                            year=year,
                            similarity_score=0.75,
                        )
                    )
            except Exception:
                logger.warning("Failed to enrich comparable projects from ai_notes", exc_info=True)

    scope_responses: list[ScopeResponse] = []
    for s in scopes:
        sr = ScopeResponse.from_orm_scope(s)
        if s.product_name is not None:
            sr = sr.model_copy(update={"unknown_product": not is_known_product(s.product_name)})
        scope_responses.append(sr)

    # Actual cost fields and variance
    actual_total_cost = float(estimate.actual_total_cost) if estimate.actual_total_cost is not None else None
    variance_pct: float | None = None
    if actual_total_cost is not None and actual_total_cost != 0 and total_cost is not None:
        variance_pct = round((actual_total_cost - total_cost) / actual_total_cost * 100, 2)

    # Collect deduplicated unknown product names (product_name set but product_id is null)
    unknown_products: list[str] = list(
        dict.fromkeys(
            s.product_name
            for s in scopes
            if s.product_name is not None and s.product_id is None
        )
    )

    return EstimateResponse(
        id=estimate.id,
        project_name=estimate.name,
        gc_name=estimate.gc_name,
        address=estimate.project_address,
        status=str(estimate.status) if estimate.status else "draft",
        total_cost=total_cost,
        total_sf=total_sf,
        cost_per_sf=cost_per_sf,
        man_days=man_days_total,
        confidence_score=confidence_score,
        confidence_level=_confidence_label(confidence_score),
        created_at=estimate.created_at,
        scopes=scope_responses,
        comparable_projects=comparable_projects,
        actual_total_cost=actual_total_cost,
        actual_cost_date=estimate.actual_cost_date,
        accuracy_note=estimate.accuracy_note,
        variance_pct=variance_pct,
        unknown_products=unknown_products,
    )


# ---------------------------------------------------------------------------
# GET /api/estimates  (list)
# ---------------------------------------------------------------------------


from sqlalchemy import func  # noqa: E402 — placed after router to avoid circular at module level


@router.get("", response_model=PaginatedResponse[EstimateListItem])
async def list_estimates(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[EstimateListItem]:
    """List estimates with optional status filter, ordered by created_at DESC."""
    base_query = select(Estimate).options(selectinload(Estimate.estimate_scopes))

    if status is not None:
        try:
            status_enum = EstimateStatus(status)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}") from err
        base_query = base_query.where(Estimate.status == status_enum)

    # Count total
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total: int = count_result.scalar_one()

    # Fetch page
    page_query = base_query.order_by(Estimate.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(page_query)
    estimates = result.scalars().all()

    items: list[EstimateListItem] = []
    for est in estimates:
        total_cost = float(est.total_estimate) if est.total_estimate is not None else None
        confidence_score = float(est.overall_confidence) if est.overall_confidence is not None else None
        scope_types = list(
            dict.fromkeys(str(s.scope_type) for s in (est.estimate_scopes or []) if s.scope_type is not None)
        )
        scopes = est.estimate_scopes or []
        has_scope_with_sf = any(
            (s.square_footage is not None and s.square_footage > 0) for s in scopes
        )
        has_accepted_scope = any(getattr(s, "manually_adjusted", False) for s in scopes)
        items.append(
            EstimateListItem(
                id=est.id,
                project_name=est.name,
                gc_name=est.gc_name,
                status=str(est.status) if est.status else "draft",
                total_cost=total_cost,
                confidence_level=_confidence_label(confidence_score),
                created_at=est.created_at,
                scope_types=scope_types,
                has_scope_with_sf=has_scope_with_sf,
                has_accepted_scope=has_accepted_scope,
            )
        )

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# POST /api/estimates
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=EstimateResponse)
async def create_estimate(
    plans: list[UploadFile],
    project_name: str = Form(...),
    gc_name: str | None = Form(None),
    address: str | None = Form(None),
    scope_type_hints: list[str] = Form(default=[]),
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Upload one or more plan PDFs and generate a cost estimate."""
    if not plans:
        raise HTTPException(status_code=422, detail="At least one plan file is required")

    # Save uploaded PDFs to a temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_paths: list[Path] = []
        for upload in plans:
            if not upload.filename:
                continue
            dest = Path(tmp_dir) / upload.filename
            content = await upload.read()
            dest.write_bytes(content)
            saved_paths.append(dest)

        if not saved_paths:
            raise HTTPException(status_code=422, detail="No valid PDF files were uploaded")

        # Run plan reading + estimation in executor to avoid blocking the event loop
        from src.estimation.estimator import estimate_from_pdf

        loop = asyncio.get_running_loop()
        project_estimates = []
        for pdf_path in saved_paths:
            try:
                pe = await loop.run_in_executor(
                    None,
                    lambda p=pdf_path: estimate_from_pdf(str(p), use_vision=False),
                )
                project_estimates.append(pe)
            except Exception as exc:
                logger.warning("Failed to estimate %s: %s", pdf_path.name, exc)

    if not project_estimates:
        raise HTTPException(
            status_code=422,
            detail="Could not extract any estimates from the uploaded plans",
        )

    # Merge multi-plan estimates (sum totals, combine scopes)
    from src.estimation.models import ScopeEstimate

    merged_scopes: list[ScopeEstimate] = []
    total_cost = Decimal(0)
    total_man_days = Decimal(0)
    total_area = Decimal(0)
    max_confidence = 0.0

    for pe in project_estimates:
        merged_scopes.extend(pe.scope_estimates)
        total_cost += pe.total_estimated_cost
        total_man_days += pe.estimated_man_days
        if pe.total_area_sf:
            total_area += pe.total_area_sf
        if pe.extraction_confidence > max_confidence:
            max_confidence = pe.extraction_confidence

    # Persist to database
    estimate = Estimate(
        name=project_name,
        gc_name=gc_name,
        project_address=address,
        source_plans=[str(pe.source_plan) for pe in project_estimates],
        status=EstimateStatus.DRAFT,
        total_estimate=total_cost,
        overall_confidence=Decimal(str(max_confidence)),
    )
    db.add(estimate)
    await db.flush()  # get estimate.id

    for se in merged_scopes:
        scope_row = EstimateScope(
            estimate_id=estimate.id,
            tag=se.scope_tag,
            scope_type=se.scope_type,
            product_name=se.product_hint,
            square_footage=se.area_sf,
            material_cost=se.material_cost,
            markup_pct=se.predicted_markup_pct,
            man_days=se.predicted_man_days,
            labor_price=se.labor_cost,
            total=se.total,
            confidence_score=Decimal(str(se.confidence)) if se.confidence is not None else None,
            ai_notes="; ".join(se.comparable_projects) if se.comparable_projects else None,
        )
        db.add(scope_row)

    await db.commit()
    await db.refresh(estimate)

    # Reload with scopes
    estimate = await _fetch_estimate_or_404(estimate.id, db)
    return await _build_response(estimate, db)


# ---------------------------------------------------------------------------
# GET /api/estimates/{id}
# ---------------------------------------------------------------------------


@router.get("/{estimate_id}", response_model=EstimateResponse)
async def get_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Fetch a single estimate by ID."""
    estimate = await _fetch_estimate_or_404(estimate_id, db)
    return await _build_response(estimate, db)


# ---------------------------------------------------------------------------
# DELETE /api/estimates/{id}
# ---------------------------------------------------------------------------


@router.delete("/{estimate_id}", status_code=204)
async def delete_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an estimate and all its scopes (cascade handled by DB)."""
    estimate = await _fetch_estimate_or_404(estimate_id, db)
    await db.delete(estimate)
    await db.commit()


# ---------------------------------------------------------------------------
# PATCH /api/estimates/{id}  — update status
# ---------------------------------------------------------------------------


@router.patch("/{estimate_id}", response_model=EstimateResponse)
async def update_estimate_status(
    estimate_id: UUID,
    body: UpdateEstimateBody,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Update estimate status. Forward transitions are validated; backward transitions are always allowed."""
    estimate = await _fetch_estimate_or_404(estimate_id, db)

    try:
        new_status = EstimateStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}") from exc

    current = estimate.status or EstimateStatus.DRAFT
    STATUS_ORDER = [EstimateStatus.DRAFT, EstimateStatus.REVIEWED, EstimateStatus.FINALIZED, EstimateStatus.EXPORTED]
    current_idx = STATUS_ORDER.index(current)
    new_idx = STATUS_ORDER.index(new_status)

    if new_idx > current_idx:  # Forward — validate
        # Eagerly load scopes for validation
        scope_result = await db.execute(
            select(EstimateScope).where(EstimateScope.estimate_id == estimate_id)
        )
        scopes = list(scope_result.scalars().all())

        if new_status == EstimateStatus.REVIEWED:
            if not scopes:
                raise HTTPException(status_code=422, detail="Add at least one scope before marking as Reviewed.")
            if not any(s.square_footage and s.square_footage > 0 for s in scopes):
                raise HTTPException(
                    status_code=422,
                    detail="At least one scope must have area (SF > 0) before marking as Reviewed.",
                )

        elif new_status in (EstimateStatus.FINALIZED, EstimateStatus.EXPORTED):
            # EXPORTED inherits all FINALIZED requirements — you can't skip Finalized
            if not scopes:
                raise HTTPException(status_code=422, detail="Add at least one scope before finalizing.")
            if not any(getattr(s, "manually_adjusted", None) for s in scopes):
                raise HTTPException(status_code=422, detail="Accept at least one scope before finalizing.")
            if not estimate.gc_name:
                raise HTTPException(
                    status_code=422,
                    detail="GC name is required before finalizing (needed for quote generation).",
                )

    if new_status == current:
        return await _build_response(estimate, db)

    estimate.status = new_status
    await db.commit()
    await db.refresh(estimate)
    estimate = await _fetch_estimate_or_404(estimate.id, db)
    return await _build_response(estimate, db)


# ---------------------------------------------------------------------------
# PATCH /api/estimates/{estimate_id}/scopes/{scope_id}
# ---------------------------------------------------------------------------


@router.patch("/{estimate_id}/scopes/{scope_id}", response_model=EstimateResponse)
async def update_scope(
    estimate_id: UUID,
    scope_id: UUID,
    body: UpdateScopeRequest,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Partially update a scope and recompute the estimate total."""
    estimate = await _fetch_estimate_or_404(estimate_id, db)

    # Find the scope
    scope: EstimateScope | None = None
    for s in estimate.estimate_scopes:
        if s.id == scope_id:
            scope = s
            break

    if scope is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scope {scope_id} not found on estimate {estimate_id}",
        )

    # Apply updates
    if body.product_name is not None:
        scope.product_name = body.product_name
    if body.area_sf is not None:
        scope.square_footage = Decimal(str(body.area_sf))
    if body.markup_pct is not None:
        scope.markup_pct = Decimal(str(body.markup_pct))
    if body.labor_days is not None:
        scope.man_days = Decimal(str(body.labor_days))
    if body.is_accepted is not None:
        scope.manually_adjusted = body.is_accepted

    # Recompute scope total: material_cost * (1 + markup_pct) + labor_price
    material_cost = scope.material_cost or Decimal(0)
    if body.material_cost_per_sf is not None and scope.square_footage:
        material_cost = scope.square_footage * Decimal(str(body.material_cost_per_sf))
        scope.material_cost = material_cost

    markup_pct = scope.markup_pct or Decimal(0)
    labor_price = scope.labor_price or Decimal(0)
    new_total = material_cost * (1 + markup_pct) + labor_price
    scope.total = new_total

    # Recompute estimate total from all scopes
    new_estimate_total = sum((s.total or Decimal(0)) for s in estimate.estimate_scopes)
    estimate.total_estimate = new_estimate_total

    await db.commit()
    await db.refresh(estimate)
    estimate = await _fetch_estimate_or_404(estimate.id, db)
    return await _build_response(estimate, db)


# ---------------------------------------------------------------------------
# DELETE /api/estimates/{estimate_id}/scopes/{scope_id}
# ---------------------------------------------------------------------------


@router.delete("/{estimate_id}/scopes/{scope_id}", status_code=204)
async def delete_scope(
    estimate_id: UUID,
    scope_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a scope line item from an estimate."""
    estimate = await _fetch_estimate_or_404(estimate_id, db)

    scope_to_delete: EstimateScope | None = None
    for s in estimate.estimate_scopes:
        if s.id == scope_id:
            scope_to_delete = s
            break

    if scope_to_delete is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scope {scope_id} not found on estimate {estimate_id}",
        )

    await db.delete(scope_to_delete)

    # Recompute estimate total
    remaining = [s for s in estimate.estimate_scopes if s.id != scope_id]
    new_total = sum((s.total or Decimal(0)) for s in remaining)
    estimate.total_estimate = new_total

    await db.commit()


# ---------------------------------------------------------------------------
# PATCH /api/estimates/{id}/actual
# ---------------------------------------------------------------------------


@router.patch("/{estimate_id}/actual", response_model=EstimateResponse)
async def record_actual_cost(
    estimate_id: UUID,
    body: RecordActualRequest,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Record the actual project cost so model accuracy can be tracked over time."""
    from datetime import date as date_type

    estimate = await _fetch_estimate_or_404(estimate_id, db)

    estimate.actual_total_cost = Decimal(str(body.actual_total_cost))
    try:
        estimate.actual_cost_date = date_type.fromisoformat(body.actual_cost_date)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {body.actual_cost_date}") from err
    if body.accuracy_note is not None:
        estimate.accuracy_note = body.accuracy_note

    await db.commit()
    await db.refresh(estimate)
    estimate = await _fetch_estimate_or_404(estimate.id, db)
    return await _build_response(estimate, db)


# ---------------------------------------------------------------------------
# POST /api/estimates/{id}/export
# ---------------------------------------------------------------------------


@router.post("/{estimate_id}/export")
async def export_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> object:
    """Export an estimate to an Excel buildup spreadsheet."""
    from fastapi.responses import StreamingResponse

    estimate = await _fetch_estimate_or_404(estimate_id, db)

    # Build a ProjectEstimate from DB data
    from decimal import Decimal as D

    from src.estimation.models import ProjectEstimate, ScopeEstimate

    scope_estimates = []
    for s in estimate.estimate_scopes:
        scope_estimates.append(
            ScopeEstimate(
                scope_tag=s.tag or "",
                scope_type=str(s.scope_type) if s.scope_type else "Other",
                area_sf=s.square_footage,
                product_hint=s.product_name,
                predicted_cost_per_sf=None,
                predicted_markup_pct=s.markup_pct,
                predicted_man_days=s.man_days,
                material_cost=s.material_cost,
                labor_cost=s.labor_price,
                total=s.total,
                confidence=float(s.confidence_score) if s.confidence_score is not None else 0.5,
                model_used="db",
                comparable_projects=[],
            )
        )

    pe = ProjectEstimate(
        source_plan=str(estimate.source_plans[0]) if estimate.source_plans else "",
        extraction_confidence=(float(estimate.overall_confidence) if estimate.overall_confidence else 0.5),
        scope_estimates=scope_estimates,
        total_estimated_cost=estimate.total_estimate or D(0),
        total_area_sf=None,
        estimated_man_days=sum((s.man_days or D(0)) for s in estimate.estimate_scopes),
        notes=[],
        created_at=estimate.created_at,
    )

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    from src.estimation.excel_writer import write_estimate_to_excel

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: write_estimate_to_excel(
            pe,
            output_path=tmp_path,
            project_name=estimate.name,
            gc_name=estimate.gc_name or "",
        ),
    )

    # Update status
    estimate.status = EstimateStatus.EXPORTED
    await db.commit()

    xlsx_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    filename = f"estimate_{estimate.name.replace(' ', '_')}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# POST /api/estimates/{id}/quote  (Phase 6.5)
# ---------------------------------------------------------------------------


@router.post("/{estimate_id}/quote")
async def create_quote(
    estimate_id: UUID,
    body: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> object:
    """Generate a quote letter PDF for the given estimate."""
    from datetime import datetime

    from fastapi.responses import StreamingResponse
    from sqlalchemy import extract, func

    estimate = await _fetch_estimate_or_404(estimate_id, db)

    # --- Generate sequential quote number: CA-YYYY-NNNN ---
    current_year = datetime.now().year
    count_result = await db.execute(
        select(func.count(Quote.id)).where(extract("year", Quote.generated_at) == current_year)
    )
    count = count_result.scalar() or 0
    quote_number = f"CA-{current_year}-{count + 1:04d}"

    # Snapshot ORM data into plain objects before handing off to sync executor thread.
    # SQLAlchemy ORM instances are not thread-safe; reading already-loaded attributes is safe
    # but we snapshot to be explicit and avoid any lazy-load surprises.
    class _ScopeSnap:
        __slots__ = ("scope_type", "product_name", "square_footage", "cost_per_unit", "total", "sales_tax")

        def __init__(self, s: EstimateScope) -> None:
            self.scope_type = s.scope_type
            self.product_name = s.product_name
            self.square_footage = s.square_footage
            self.cost_per_unit = s.cost_per_unit
            self.total = s.total
            self.sales_tax = s.sales_tax

    class _EstimateSnap:
        __slots__ = ("name", "gc_name", "project_address", "estimate_scopes")

        def __init__(self, e: Estimate) -> None:
            self.name = e.name
            self.gc_name = e.gc_name
            self.project_address = e.project_address
            self.estimate_scopes = [_ScopeSnap(s) for s in (e.estimate_scopes or [])]

    estimate_snap = _EstimateSnap(estimate)

    # --- Build PDF in executor (reportlab is synchronous) ---
    loop = asyncio.get_running_loop()
    try:
        pdf_bytes: bytes = await loop.run_in_executor(
            None,
            lambda: _build_quote_pdf(estimate_snap, quote_number, body.template),  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.error("Quote PDF generation failed for estimate %s: %s", estimate_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Quote generation failed: {exc}") from exc

    # --- Persist Quote record ---
    quote_record = Quote(
        estimate_id=estimate_id,
        quote_number=quote_number,
        template=body.template,
    )
    db.add(quote_record)
    await db.commit()

    filename = f"quote-{quote_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_quote_pdf(estimate: Estimate, quote_number: str, template: str) -> bytes:
    """Build and return a quote letter PDF as bytes using reportlab."""
    from datetime import date
    from decimal import Decimal as D

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    header_style = ParagraphStyle(
        "ca_header",
        parent=normal,
        fontSize=18,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    subheader_style = ParagraphStyle(
        "ca_subheader",
        parent=normal,
        fontSize=10,
        fontName="Helvetica",
        textColor=colors.HexColor("#555555"),
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "label",
        parent=normal,
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#333333"),
    )
    value_style = ParagraphStyle(
        "value",
        parent=normal,
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#111111"),
    )
    clause_heading_style = ParagraphStyle(
        "clause_heading",
        parent=normal,
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=6,
        spaceAfter=2,
    )
    clause_body_style = ParagraphStyle(
        "clause_body",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#222222"),
        leading=11,
        spaceAfter=4,
    )
    clause_sub_style = ParagraphStyle(
        "clause_sub",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#333333"),
        leading=11,
        leftIndent=14,
        spaceAfter=2,
    )

    story: list = []

    # ---- Header — template-specific ----
    if template == "T-004A":
        gc_display = estimate.gc_name or "General Contractor"
        story.append(Paragraph("COMMERCIAL ACOUSTICS", header_style))
        story.append(Paragraph("6301 N Florida Ave, Tampa, FL 33604 | 888.815.9691", subheader_style))
        story.append(Spacer(1, 0.08 * inch))
        to_style = ParagraphStyle(
            "to_block",
            parent=normal,
            fontSize=9,
            fontName="Helvetica",
            textColor=colors.HexColor("#111111"),
            spaceAfter=2,
        )
        story.append(Paragraph(f"<b>To:</b> {gc_display}", to_style))
        story.append(Paragraph(f"<b>Project:</b> {estimate.name or 'N/A'}", to_style))
        story.append(Spacer(1, 0.06 * inch))
    elif template == "T-004E":
        story.append(Paragraph("COMMERCIAL ACOUSTICS", header_style))
        story.append(
            Paragraph(
                "Sound Masking &amp; Acoustical Systems | Tampa, FL | 888.815.9691",
                subheader_style,
            )
        )
        story.append(Spacer(1, 0.1 * inch))
    else:
        # T-004B default
        story.append(Paragraph("COMMERCIAL ACOUSTICS", header_style))
        story.append(Paragraph("Tampa, FL", subheader_style))
        story.append(Spacer(1, 0.1 * inch))

    # Divider line via single-cell table
    story.append(
        Table(
            [[""]],
            colWidths=[6.5 * inch],
            rowHeights=[2],
            style=TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#222222")),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    # ---- Quote meta ----
    today_str = date.today().strftime("%B %d, %Y")
    meta_data = [
        [
            Paragraph("Quote Number:", label_style),
            Paragraph(quote_number, value_style),
            Paragraph("Template:", label_style),
            Paragraph(template, value_style),
        ],
        [
            Paragraph("Date:", label_style),
            Paragraph(today_str, value_style),
            Paragraph("Valid For:", label_style),
            Paragraph("30 days", value_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[1.2 * inch, 2.0 * inch, 1.2 * inch, 2.1 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.15 * inch))

    # ---- Project info ----
    project_name = estimate.name or "N/A"
    gc_name = estimate.gc_name or "N/A"
    address = estimate.project_address or "N/A"

    proj_data = [
        [Paragraph("Project Name:", label_style), Paragraph(project_name, value_style)],
        [Paragraph("General Contractor:", label_style), Paragraph(gc_name, value_style)],
        [Paragraph("Project Address:", label_style), Paragraph(address, value_style)],
    ]
    proj_table = Table(proj_data, colWidths=[1.5 * inch, 5.0 * inch])
    proj_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(proj_table)
    story.append(Spacer(1, 0.2 * inch))

    # ---- Line items table ----
    col_header_style = ParagraphStyle(
        "col_header",
        parent=normal,
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        "cell",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#111111"),
    )

    table_data = [
        [
            Paragraph("Scope Type", col_header_style),
            Paragraph("Description", col_header_style),
            Paragraph("Area (SF)", col_header_style),
            Paragraph("Unit Cost", col_header_style),
            Paragraph("Total", col_header_style),
        ]
    ]

    subtotal = D(0)
    total_tax = D(0)

    for s in estimate.estimate_scopes:
        scope_type = str(s.scope_type) if s.scope_type else "Other"
        description = s.product_name or "—"
        area = f"{s.square_footage:,.0f}" if s.square_footage else "—"
        unit_cost = f"${s.cost_per_unit:,.4f}" if s.cost_per_unit else "—"
        line_total = s.total or D(0)
        total_str = f"${line_total:,.2f}"

        subtotal += line_total
        total_tax += s.sales_tax or D(0)

        table_data.append(
            [
                Paragraph(scope_type, cell_style),
                Paragraph(description, cell_style),
                Paragraph(area, cell_style),
                Paragraph(unit_cost, cell_style),
                Paragraph(total_str, cell_style),
            ]
        )

    col_widths = [1.0 * inch, 2.3 * inch, 0.9 * inch, 1.0 * inch, 1.3 * inch]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(
        TableStyle(
            [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9f9f9"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # Align numeric columns right
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (2, 0), (-1, 0), "CENTER"),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 0.15 * inch))

    # ---- Totals ----
    grand_total = subtotal + total_tax
    totals_data = [
        ["", "Subtotal:", f"${subtotal:,.2f}"],
        ["", "Sales Tax:", f"${total_tax:,.2f}"],
        ["", "Grand Total:", f"${grand_total:,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[4.0 * inch, 1.5 * inch, 1.0 * inch])

    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEABOVE", (1, 2), (-1, 2), 1, colors.HexColor("#222222")),
                ("FONTNAME", (1, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 0.3 * inch))

    # ---- Template-specific Terms & Conditions ----
    _append_terms(
        story,
        template,
        grand_total,
        clause_heading_style,
        clause_body_style,
        clause_sub_style,
        colors,
        inch,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        ParagraphStyle,
        normal,
    )

    # ---- Signature block ----
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Table(
            [[""]],
            colWidths=[6.5 * inch],
            rowHeights=[1],
            style=TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    sig_label = ParagraphStyle(
        "sig_label",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#555555"),
    )
    sig_value_style = ParagraphStyle(
        "sig_value",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#111111"),
    )
    sig_data = [
        [
            Paragraph("Accepted By:", sig_label),
            Paragraph("_" * 34, sig_value_style),
            Paragraph("Date:", sig_label),
            Paragraph("_" * 16, sig_value_style),
        ],
        [
            Paragraph("Name/Title:", sig_label),
            Paragraph("_" * 34, sig_value_style),
            "",
            "",
        ],
        [
            Paragraph("Commercial Acoustics:", sig_label),
            Paragraph("_" * 34, sig_value_style),
            Paragraph("Date:", sig_label),
            Paragraph("_" * 16, sig_value_style),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[1.4 * inch, 2.8 * inch, 0.6 * inch, 1.7 * inch])
    sig_table.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )
    story.append(sig_table)

    doc.build(story)
    return buf.getvalue()


def _append_terms(  # noqa: PLR0913
    story: list,
    template: str,
    grand_total: object,
    heading_style: object,
    body_style: object,
    sub_style: object,
    colors: object,
    inch: object,
    Table: object,  # noqa: N803
    TableStyle: object,  # noqa: N803
    Paragraph: object,  # noqa: N803
    Spacer: object,  # noqa: N803
    ParagraphStyle: object,  # noqa: N803
    normal: object,
) -> None:
    """Append template-specific Terms & Conditions clauses to the story list."""

    def _clause(heading: str, body: str) -> None:
        story.append(Paragraph(heading, heading_style))
        story.append(Paragraph(body, body_style))
        story.append(Spacer(1, 0.1 * inch))

    def _clause_with_subs(heading: str, intro: str, subs: list) -> None:
        story.append(Paragraph(heading, heading_style))
        if intro:
            story.append(Paragraph(intro, body_style))
        for sub in subs:
            story.append(Paragraph(sub, sub_style))
        story.append(Spacer(1, 0.1 * inch))

    section_title_style = ParagraphStyle(
        "section_title",
        parent=normal,
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6,
        spaceBefore=4,
    )
    story.append(Paragraph("Terms of Proposal", section_title_style))
    story.append(
        Table(
            [[""]],
            colWidths=[6.5 * inch],
            rowHeights=[1],
            style=TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#1a1a2e")),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    if template == "T-004A":
        _append_terms_t004a(_clause, _clause_with_subs, grand_total)
    elif template == "T-004E":
        _append_terms_t004e(_clause, _clause_with_subs)
    else:
        # T-004B and any unknown template
        _append_terms_t004b(_clause, _clause_with_subs)


def _append_terms_t004b(_clause: object, _clause_with_subs: object) -> None:
    """T-004B: Acoustic Panel Fab & Install — standard install terms."""
    _clause(
        "1. Quote Validity & Payment",
        "Quote valid for 30 days. Credit Card payments will require a 3% processing fee to be paid "
        "by the client. Billing is milestone-based per the schedule of values agreed upon at "
        "contract execution. All credit terms for Net 30 accounts are subject to approval prior to "
        "the order being released into production.",
    )
    _clause(
        "2. Lead Time & Schedule",
        "1–2 week lead-time. 1–2 week install duration. Lead time may vary by 1–2 weeks in extreme cases.",
    )
    _clause(
        "3. Material Warranty",
        "A 1-year limited warranty applies to all material. Material warranty is limited to the "
        "price of Commercial Acoustics materials included in this proposal.",
    )
    _clause_with_subs(
        "4. Installation Requirements",
        "The following conditions apply to all installation work:",
        [
            "a. A Hard Date for initial mobilization shall be set in writing no less than 2 weeks "
            "in advance. Client certifies at this time that the site is ready to receive the system "
            "installation. If the site is not ready upon arrival, the client may be subject to a "
            "rescheduling fee.",
            "b. Go-Backs, Punch Lists, or Change Order items shall require a minimum 72-hour notification, in writing.",
            "c. Installation duration is an estimate only and is heavily dependent on site "
            "conditions. No authority to reduce scope of work by supplementing with external labor "
            "shall be granted without prior written approval by Commercial Acoustics.",
            "d. Room will be clear and broom-clean prior to arrival. Finish products shall not be "
            "exposed to areas that are not sufficiently clean and dust-free.",
            "e. Assumes permits and inspections are complete prior to installation team arrival.",
            "f. If ceiling installation, assumes that ceiling is constructed of gypsum or corrugated "
            "metal. If Client or Contractor is aware of deficient ceiling substrate or material, "
            "Client or Contractor shall disclose this known deficiency.",
            "g. If after-hours or overnight installation is required, this will be subject to a "
            "$500/day after-hours fee.",
            "h. If no layout is provided by client, best practices shall be utilized to ensure equal "
            "spacing between panels. All obstructions, protrusions, and cut-outs must be disclosed "
            "prior to installation. Custom-cutting panels around undocumented obstructions will "
            "incur a Change Order fee.",
        ],
    )
    _clause(
        "5. Acoustic Panel Specifications",
        "Includes Guilford of Maine acoustically-transparent fabric. Contact salesperson for fabric "
        "swatches or additional fabric options. First Piece Panels off the production line are "
        "available for client approval prior to delivery. Custom-made products such as acoustic "
        "fabric panels are made to specifications and are not subject to return under any conditions.",
    )
    _clause(
        "6. Sales Tax",
        "If sales tax exempt, the purchaser must have a valid Sales Tax Certificate on file with "
        "Commercial Acoustics at time of order. Payment of local and state taxes are not included "
        "in this quote if outside of the states of FL and LA, and are the responsibility of the "
        "purchaser.",
    )
    _clause(
        "7. Insurance",
        "This quote includes General Liability coverage of $2,000,000 and Workers Compensation "
        "coverage of $1,000,000. Does not include Waivers of Subrogation (WoS), Additional Insured "
        "(AI), or Primary Non-Contributory (PNC) endorsements. Additional insurance requirements, "
        "endorsements, or waivers may require an additional fee. If a sample Certificate of "
        "Insurance (COI) is available, please provide during the bidding process.",
    )
    _clause(
        "8. Retainage",
        "Price in proposal assumes no retainage in contract. If retainage is required, additional "
        "financing fees may be incurred.",
    )
    _clause(
        "9. Client Representative & Acceptance",
        "Client shall have a representative on-site with authority to approve final quality of "
        "installation on the last day of installation and at completion of regular intervals. If no "
        "representative is available or does not have sufficient authority, a Go-Back or Change "
        "Order may be submitted to client if additional mobilization is required.",
    )


def _append_terms_t004a(_clause: object, _clause_with_subs: object, grand_total: object) -> None:
    """T-004A: General quote template for larger GC/commercial projects — 14 clauses."""
    _clause(
        "1. Quote Validity & Payment Terms",
        "Quote valid for 30 days. A 50% Down Payment is due prior to commencement of work. "
        "Remainder of payment is due 15 days from installation completion. A service charge of "
        "1.5% per month (18% per year) will apply to all delinquent invoices. Credit Card payments "
        "will require a 3% processing fee to be paid by the client. All credit terms for Net 30 "
        "accounts are subject to approval prior to the order being released into production.",
    )
    _clause(
        "2. Lead Time & Schedule",
        "3-week lead-time. 1–2 week install duration. Lead time may vary by 1–2 weeks in extreme cases.",
    )
    _clause(
        "3. Material Warranty",
        "A 1-year limited warranty applies to all material. Material warranty is limited to the "
        "price of Commercial Acoustics materials included in this proposal.",
    )
    _clause_with_subs(
        "4. Installation Requirements",
        "The following conditions apply to all installation work:",
        [
            "a. A Hard Date for initial mobilization shall be set in writing no less than 2 weeks "
            "in advance. Client certifies at this time that the site is ready to receive the system "
            "installation. If the site is not ready upon arrival, the client may be subject to a "
            "rescheduling fee.",
            "b. Go-Backs, Punch Lists, or Change Order items shall require a minimum 72-hour notification, in writing.",
            "c. Installation duration is an estimate only and is heavily dependent on site "
            "conditions. No authority to reduce scope of work by supplementing with external labor "
            "shall be granted without prior written approval by Commercial Acoustics.",
            "d. Room will be clear and broom-clean prior to arrival. Finish products shall not be "
            "exposed to areas that are not sufficiently clean and dust-free.",
            "e. Assumes permits and inspections are complete prior to installation team arrival.",
            "f. If ceiling installation, assumes that ceiling is constructed of gypsum or corrugated "
            "metal. If Client or Contractor is aware of deficient ceiling substrate or material, "
            "Client or Contractor shall disclose this known deficiency.",
            "g. If after-hours or overnight installation is required, this will be subject to a "
            "$500/day after-hours fee.",
            "h. If applicable, the client shall approve a completed first piece prior to "
            "commencement of installation. This shall serve as the basis of future quality standard "
            "throughout the rest of the project.",
            "i. If no layout is provided by client, best practices shall be utilized to ensure "
            "equal spacing between panels. All obstructions, protrusions, and cut-outs must be "
            "disclosed prior to installation. Custom-cutting panels around undocumented obstructions "
            "will incur a Change Order fee.",
        ],
    )
    _clause(
        "5. Acoustic Panel Specifications",
        "Includes Guilford of Maine acoustically-transparent fabric. Contact salesperson for fabric "
        "swatches or additional fabric options. First Piece Panels off the production line are "
        "available for client approval prior to delivery. Custom-made products such as acoustic "
        "fabric panels are made to specifications and are not subject to return under any conditions.",
    )
    _clause(
        "6. Sales Tax",
        "If sales tax exempt, the purchaser must have a valid Sales Tax Certificate on file with "
        "Commercial Acoustics at time of order. Payment of local and state taxes are not included "
        "in this quote if outside of the states of FL and LA, and are the responsibility of the "
        "purchaser.",
    )
    _clause(
        "7. Insurance Requirements",
        "This quote includes General Liability coverage of $2,000,000 and Workers Compensation "
        "coverage of $1,000,000. Does not include Waivers of Subrogation (WoS), Additional Insured "
        "(AI), or Primary Non-Contributory (PNC) endorsements. Additional insurance requirements, "
        "endorsements, or waivers may require an additional fee. If a sample Certificate of "
        "Insurance (COI) is available, please provide during the bidding process.",
    )
    _clause(
        "8. Retainage",
        "Price in proposal assumes no retainage in contract. If retainage is required, additional "
        "financing fees may be incurred.",
    )
    bond_cost = float(grand_total) * 0.03
    _clause(
        "9. Payment & Performance Bond",
        f"If a Payment and Performance (P&amp;P) Bond is required by the Owner or GC, a bond fee "
        f"of 3% of the total contract value will be added to this proposal. At the current contract "
        f"value, the estimated bond cost would be ${bond_cost:,.2f}. Bond requirement must be "
        f"disclosed at time of subcontract execution.",
    )
    _clause(
        "10. Lien Waiver",
        "Conditional lien waivers will be provided upon receipt of payment for each billing period. "
        "Unconditional lien waivers will be provided upon receipt of final payment in full. "
        "Commercial Acoustics reserves all rights under applicable state lien law until payment "
        "is received in full.",
    )
    _clause(
        "11. Subcontract Terms",
        "If this Proposal is adopted as a portion of a Subcontract or Scope of Work, these Terms "
        "and Conditions shall not be over-ridden or superseded by the Terms and Conditions of the "
        "Subcontract, and shall remain wholly in effect.",
    )
    _clause(
        "12. Client Representative & Acceptance",
        "Client shall have a representative on-site with authority to approve final quality of "
        "installation on the last day of installation and at completion of regular intervals. If no "
        "representative is available or does not have sufficient authority, a Go-Back or Change "
        "Order may be submitted to client if additional mobilization is required.",
    )
    _clause(
        "13. Non-Interference",
        "CONTRACTOR agrees to refrain from any and all interference in the progress of "
        "SUBCONTRACTOR's performance of the work. CONTRACTOR shall be liable to SUBCONTRACTOR for "
        "any and all damages, expenses, and losses incurred as a result of such delay, including "
        "any liquidated damages (LDs) assessed against SUBCONTRACTOR, all incidental and "
        "consequential damages, and costs for continued Project supervision, job overhead, "
        "insurance, Project facilities, and other costs.",
    )
    _clause(
        "14. Scope Integrity",
        "No authority to reduce scope of work by supplementing with external labor shall be "
        "granted without prior written approval by Commercial Acoustics. Any scope reductions or "
        "deletions requested after contract execution will be subject to a formal Change Order "
        "process.",
    )


def _append_terms_t004e(_clause: object, _clause_with_subs: object) -> None:
    """T-004E: Sound Masking quote template — Lencore/Vektor SM-specific clauses."""
    _clause(
        "1. Quote Validity & Payment Terms",
        "Quote valid for 30 days. A 50% Deposit is required prior to order placement. Remainder of "
        "payment is due 15 days from completion of installation. A service charge of 1.5% per "
        "month (18% per year) will apply to all delinquent invoices. Credit Card payments will "
        "require a 3% processing fee to be paid by the client.",
    )
    _clause(
        "2. Lead Time & Schedule",
        "3–6 weeks lead-time for sound masking equipment. Lead time may vary by 1–2 weeks in "
        "extreme cases. Installation scheduling to be coordinated with Contractor no less than "
        "2 weeks prior to mobilization.",
    )
    _clause(
        "3. Sound Masking System Scope",
        "Scope includes furnishing and installing a Lencore or Vektor sound masking system per "
        "plans and specifications. Includes all emitters, controllers, cabling, and hardware "
        "required for a complete and operational system. System is designed to provide broadband "
        "masking coverage across the designated coverage area per the approved layout.",
    )
    _clause(
        "4. System Commissioning",
        "Sound masking systems require a dedicated commissioning/startup visit following "
        "installation. During commissioning, the system will be tuned and balanced to achieve "
        "target masking levels per ASTM E1130 or project-specified criteria. Commissioning is "
        "included in this proposal unless otherwise noted. Any additional tuning visits requested "
        "after commissioning is complete will be subject to a separate service call fee.",
    )
    _clause(
        "5. Material & Equipment Warranty",
        "A 1-year limited warranty applies to all material and equipment. Manufacturer's warranty "
        "terms for Lencore/Vektor equipment apply and are available upon request. Material warranty "
        "is limited to the price of Commercial Acoustics materials and equipment included in this "
        "proposal.",
    )
    _clause_with_subs(
        "6. Installation Requirements",
        "The following conditions apply to all sound masking installation work:",
        [
            "a. A Hard Date for initial mobilization shall be set in writing no less than 2 weeks "
            "in advance. Client certifies that the site is ready, including above-ceiling access "
            "and completed overhead MEP rough-in.",
            "b. Go-Backs, Punch Lists, or Change Order items shall require a minimum 72-hour notification, in writing.",
            "c. Room will be clear and broom-clean prior to arrival. System components shall not be "
            "exposed to areas that are not sufficiently clean and dust-free.",
            "d. Assumes permits and inspections are complete prior to installation team arrival.",
            "e. If ceiling installation, assumes that ceiling grid is installed and accessible. "
            "Emitter placement will follow the approved layout drawing.",
            "f. If after-hours or overnight installation is required, this will be subject to a "
            "$500/day after-hours fee.",
        ],
    )
    _clause(
        "7. Acoustic Ceiling Tile (ACT) — If Applicable",
        "If ACT is included in this proposal, scope includes furnishing and installing acoustical "
        "ceiling tile per plans and specifications. Includes Guilford of Maine acoustically-"
        "transparent fabric on any fabric-wrapped panels. Custom-made products are not subject to "
        "return under any conditions.",
    )
    _clause(
        "8. Sales Tax",
        "If sales tax exempt, the purchaser must have a valid Sales Tax Certificate on file with "
        "Commercial Acoustics at time of order. Payment of local and state taxes are not included "
        "in this quote if outside of the states of FL and LA, and are the responsibility of the "
        "purchaser.",
    )
    _clause(
        "9. Insurance",
        "This quote includes General Liability coverage of $2,000,000 and Workers Compensation "
        "coverage of $1,000,000. Does not include Waivers of Subrogation (WoS), Additional Insured "
        "(AI), or Primary Non-Contributory (PNC) endorsements. Additional insurance requirements, "
        "endorsements, or waivers may require an additional fee.",
    )
    _clause(
        "10. Subcontract Terms",
        "If this Proposal is adopted as a portion of a Subcontract or Scope of Work, these Terms "
        "and Conditions shall not be over-ridden or superseded by the Terms and Conditions of the "
        "Subcontract, and shall remain wholly in effect.",
    )
