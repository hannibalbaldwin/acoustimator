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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_db
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.estimates import (
    ComparableProjectResponse,
    EstimateListItem,
    EstimateResponse,
    ScopeResponse,
    UpdateScopeRequest,
)
from src.api.schemas.exports import QuoteRequest, QuoteResponse
from src.db.models import Estimate, EstimateScope, EstimateStatus, Project

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

    scope_responses = [ScopeResponse.from_orm_scope(s) for s in scopes]

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
# POST /api/estimates/{id}/quote  (stub — Phase 6.5)
# ---------------------------------------------------------------------------


@router.post("/{estimate_id}/quote", response_model=QuoteResponse)
async def create_quote(
    estimate_id: UUID,
    body: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """Stub endpoint — quote generation is implemented in Phase 6.5."""
    # Verify estimate exists
    await _fetch_estimate_or_404(estimate_id, db)
    return QuoteResponse(
        quote_id="stub",
        template=body.template,
        message="Quote generation coming in Phase 6.5",
    )
