"""Database loader for persisting ExtractionResult objects to PostgreSQL.

Handles upsert logic for projects, scopes, additional costs, and extraction run
audit records. Designed to be idempotent — re-running on the same data produces
the same result via a clean delete-and-replace pattern.

Usage:
    from src.db.loader import load_extraction_result, load_all_results
    from src.db.session import async_session

    async with async_session() as session:
        project = await load_extraction_result(session, result)
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AdditionalCost,
    AdditionalCostType,
    ExtractionRun,
    ExtractionStatus,
    Project,
    Scope,
    ScopeType,
)
from src.db.session import async_session
from src.extraction.excel_parser import ExtractedProject, ExtractedScope, ExtractionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enum mapping helpers
# ---------------------------------------------------------------------------

# Map raw extraction strings to ScopeType enum values (case-insensitive lookup
# is handled by normalising to title-case and falling back to OTHER).
_SCOPE_TYPE_MAP: dict[str, ScopeType] = {
    "act": ScopeType.ACT,
    "awp": ScopeType.AWP,
    "ap": ScopeType.AP,
    "baffles": ScopeType.BAFFLES,
    "baffle": ScopeType.BAFFLES,
    "fw": ScopeType.FW,
    "sm": ScopeType.SM,
    "ww": ScopeType.WW,
    "rpg": ScopeType.RPG,
    "other": ScopeType.OTHER,
}

# Map raw additional_cost cost_type strings to AdditionalCostType enum values.
_ADDITIONAL_COST_TYPE_MAP: dict[str, AdditionalCostType] = {
    "lift_rental": AdditionalCostType.LIFT_RENTAL,
    "lift rental": AdditionalCostType.LIFT_RENTAL,
    "travel_per_diem": AdditionalCostType.TRAVEL_PER_DIEM,
    "travel per diem": AdditionalCostType.TRAVEL_PER_DIEM,
    "per diem": AdditionalCostType.TRAVEL_PER_DIEM,
    "travel_flights": AdditionalCostType.TRAVEL_FLIGHTS,
    "travel flights": AdditionalCostType.TRAVEL_FLIGHTS,
    "flights": AdditionalCostType.TRAVEL_FLIGHTS,
    "travel_hotels": AdditionalCostType.TRAVEL_HOTELS,
    "travel hotels": AdditionalCostType.TRAVEL_HOTELS,
    "hotels": AdditionalCostType.TRAVEL_HOTELS,
    "equipment": AdditionalCostType.EQUIPMENT,
    "consumables": AdditionalCostType.CONSUMABLES,
    "bond": AdditionalCostType.BOND,
    "p&p bond": AdditionalCostType.BOND,
    "pp bond": AdditionalCostType.BOND,
    "site_visit": AdditionalCostType.SITE_VISIT,
    "site visit": AdditionalCostType.SITE_VISIT,
    "punch_list": AdditionalCostType.PUNCH_LIST,
    "punch list": AdditionalCostType.PUNCH_LIST,
    "punch": AdditionalCostType.PUNCH_LIST,
    "setup_unload": AdditionalCostType.SETUP_UNLOAD,
    "setup unload": AdditionalCostType.SETUP_UNLOAD,
    "setup/unload": AdditionalCostType.SETUP_UNLOAD,
    "commission": AdditionalCostType.COMMISSION,
    "other": AdditionalCostType.OTHER,
}


def _map_scope_type(raw: str) -> ScopeType:
    """Map a raw extraction scope_type string to a ScopeType enum value.

    Falls back to ScopeType.OTHER for unrecognised strings.
    """
    return _SCOPE_TYPE_MAP.get(raw.strip().lower(), ScopeType.OTHER)


def _map_additional_cost_type(raw: str | None) -> AdditionalCostType:
    """Map a raw cost_type string to an AdditionalCostType enum value.

    Falls back to AdditionalCostType.OTHER for unrecognised or missing strings.
    """
    if not raw:
        return AdditionalCostType.OTHER
    return _ADDITIONAL_COST_TYPE_MAP.get(raw.strip().lower(), AdditionalCostType.OTHER)


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _build_scope(project_id: object, extracted: ExtractedScope, source_file: str) -> Scope:
    """Construct a Scope ORM instance from an ExtractedScope.

    Does not add the instance to any session — the caller is responsible for
    that.
    """
    return Scope(
        project_id=project_id,
        tag=extracted.tag,
        scope_type=_map_scope_type(extracted.scope_type),
        product_name=extracted.product_name,
        square_footage=extracted.square_footage,
        cost_per_unit=extracted.cost_per_sf,
        material_cost=extracted.material_cost,
        markup_pct=extracted.markup_pct,
        material_price=extracted.material_price,
        man_days=extracted.man_days,
        daily_labor_rate=extracted.daily_labor_rate,
        labor_base_rate=extracted.labor_base_rate,
        labor_hours_per_day=extracted.labor_hours_per_day,
        labor_multiplier=extracted.labor_multiplier,
        labor_price=extracted.labor_price,
        sales_tax_pct=extracted.sales_tax_pct,
        sales_tax=extracted.sales_tax,
        county_surtax_rate=extracted.county_surtax_rate,
        county_surtax_cap=extracted.county_surtax_cap,
        scrap_rate=extracted.scrap_rate,
        total=extracted.total,
        notes=extracted.notes,
        drawing_references=extracted.drawing_references or [],
        source_file=source_file,
        source_sheet=extracted.source_sheet,
    )


def _build_additional_cost(project_id: object, raw: dict, source_file: str) -> AdditionalCost:
    """Construct an AdditionalCost ORM instance from a raw additional-cost dict.

    Expected keys (all optional): cost_type, description, amount, notes.
    """
    raw_amount = raw.get("amount")
    amount: Decimal | None = None
    if raw_amount is not None:
        try:
            amount = Decimal(str(raw_amount))
        except Exception:
            amount = None

    return AdditionalCost(
        project_id=project_id,
        cost_type=_map_additional_cost_type(raw.get("cost_type")),
        description=raw.get("description"),
        amount=amount,
        notes=raw.get("notes"),
        source_file=source_file,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _parse_date(raw: str | None) -> date | None:
    """Parse a free-form date string extracted by Claude into a Python date.

    Handles ISO dates, US formats, month-name variants, and garbage values.
    Returns None for anything that can't be parsed or is clearly not a date.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s or s.upper() in ("NA", "N/A", "NONE", "TBD", "TBA", "-"):
        return None

    # ISO: 2025-05-28
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # US numeric: 9/26 → assume current year; 9/26/25 or 9/26/2025
    m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", s)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year_raw = m.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = date.today().year
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # Month name variants: "Sept 3", "January 29", "Sep 3 2025"
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2})(?:[\s,]+(\d{4}))?$", s)
    if m:
        mon_str = m.group(1)[:3].lower()
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else date.today().year
        month = month_map.get(mon_str)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


async def load_extraction_result(
    session: AsyncSession,
    result: ExtractionResult,
) -> Project | None:
    """Persist an ExtractionResult to the database.

    If a project with the same folder_name already exists, its scopes and
    additional costs are deleted and replaced with the new values (clean
    re-extract pattern).  ON CONFLICT is intentionally avoided in favour of an
    explicit select + delete + insert flow for clarity and compatibility.

    An ExtractionRun audit record is always written, regardless of whether the
    extraction succeeded.

    Returns the Project ORM instance on success, None on failure.
    """
    if not result.success or result.project is None:
        # Still record the failed run if we have enough info to identify the
        # source file.
        source_file = result.project.source_file if result.project else (result.error or "unknown")
        run = ExtractionRun(
            source_file=source_file,
            file_type="xlsx",
            extraction_status=ExtractionStatus.FAILED,
            error_message=result.error,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )
        session.add(run)
        await session.commit()
        return None

    extracted: ExtractedProject = result.project

    # ------------------------------------------------------------------
    # 1. Upsert the Project row
    # ------------------------------------------------------------------
    stmt = select(Project).where(Project.folder_name == extracted.folder_name)
    db_result = await session.execute(stmt)
    project: Project | None = db_result.scalar_one_or_none()

    bid_due_date = _parse_date(extracted.bid_due_date)

    if project is None:
        project = Project(
            name=extracted.project_name,
            folder_name=extracted.folder_name,
            source_path=extracted.source_file,
            address=extracted.project_address,
            gc_name=extracted.gc_name,
            gc_contact=extracted.gc_contact,
            bid_due_date=bid_due_date,
            notes=extracted.raw_notes,
        )
        session.add(project)
        await session.flush()  # Obtain the server-generated UUID
    else:
        # Update mutable fields; leave status / project_type as-is so manual
        # edits are not overwritten.
        project.name = extracted.project_name
        project.source_path = extracted.source_file
        project.address = extracted.project_address
        project.gc_name = extracted.gc_name
        project.gc_contact = extracted.gc_contact
        project.bid_due_date = bid_due_date
        project.notes = extracted.raw_notes

        # ------------------------------------------------------------------
        # 2. Delete old child records so they can be replaced cleanly
        # ------------------------------------------------------------------
        old_scopes_stmt = select(Scope).where(Scope.project_id == project.id)
        old_scopes = (await session.execute(old_scopes_stmt)).scalars().all()
        for scope in old_scopes:
            await session.delete(scope)

        old_costs_stmt = select(AdditionalCost).where(AdditionalCost.project_id == project.id)
        old_costs = (await session.execute(old_costs_stmt)).scalars().all()
        for cost in old_costs:
            await session.delete(cost)

        await session.flush()

    # ------------------------------------------------------------------
    # 3. Insert new Scope rows
    # ------------------------------------------------------------------
    for extracted_scope in extracted.scopes:
        scope_orm = _build_scope(project.id, extracted_scope, extracted.source_file)
        session.add(scope_orm)

    # ------------------------------------------------------------------
    # 4. Insert new AdditionalCost rows
    # ------------------------------------------------------------------
    for raw_cost in extracted.additional_costs:
        cost_orm = _build_additional_cost(project.id, raw_cost, extracted.source_file)
        session.add(cost_orm)

    # ------------------------------------------------------------------
    # 5. Always create an ExtractionRun audit record
    # ------------------------------------------------------------------
    confidence_decimal: Decimal | None = None
    try:
        confidence_decimal = Decimal(str(extracted.extraction_confidence))
    except Exception:
        pass

    run = ExtractionRun(
        source_file=extracted.source_file,
        file_type="xlsx",
        extraction_status=ExtractionStatus.SUCCESS,
        confidence=confidence_decimal,
        model_used=result.model_used,
        tokens_used=result.tokens_used,
        project_id=project.id,
    )
    session.add(run)

    await session.commit()
    return project


async def load_all_results(
    results: list[ExtractionResult],
    show_progress: bool = True,
) -> dict[str, int]:
    """Load a list of ExtractionResults to the database.

    Uses one session per result to isolate failures — a single bad record does
    not roll back the entire batch.

    Returns a dict with keys: "success", "failed", "skipped".
    """
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    counts: dict[str, int] = {"success": 0, "failed": 0, "skipped": 0}

    progress_ctx = (
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )
        if show_progress
        else None
    )

    async def _load_one(extraction_result: ExtractionResult) -> str:
        """Load a single result in its own session; return outcome key."""
        try:
            async with async_session() as session:
                project = await load_extraction_result(session, extraction_result)
            if project is not None:
                return "success"
            # None means the extraction itself failed (no project data) — skip, don't count as error
            return "skipped" if not extraction_result.success else "failed"
        except Exception as exc:
            source = extraction_result.project.source_file if extraction_result.project else "unknown"
            logger.error("Failed to load %s: %s", source, exc)
            return "failed"

    if progress_ctx is not None:
        with progress_ctx as progress:
            task = progress.add_task("Loading to database...", total=len(results))
            for res in results:
                outcome = await _load_one(res)
                counts[outcome] += 1
                progress.advance(task)
    else:
        for res in results:
            outcome = await _load_one(res)
            counts[outcome] += 1

    return counts


async def get_project_count(session: AsyncSession) -> int:
    """Return the total number of projects in the database."""
    result = await session.execute(select(func.count()).select_from(Project))
    return result.scalar_one()


async def get_scope_count(session: AsyncSession) -> int:
    """Return the total number of scopes in the database."""
    result = await session.execute(select(func.count()).select_from(Scope))
    return result.scalar_one()
