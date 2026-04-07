"""Load extracted vendor quote JSONs into the Neon DB vendor_quotes table.

Reads all 192 JSON files from data/extracted/vendor_quotes/, deserializes each
into a VendorExtractionResult, then for each successful extraction:
  1. Upserts the vendor into the vendors table (by canonical name).
  2. Looks up the project by folder_name (derived from the JSON filename).
  3. Inserts a vendor_quotes row linked to the vendor (and project if found).

Usage:
    uv run python scripts/load_vendor_quotes.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure repo root is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Project, Vendor, VendorQuote
from src.db.session import async_session
from src.extraction.vendor_parser import VendorExtractionResult

VENDOR_QUOTES_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted" / "vendor_quotes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_folder_name(json_filename: str) -> str:
    """Extract the project folder_name from the JSON filename.

    JSON files are named: <folder_name>__<quote_filename>.json
    The folder_name is everything before the first '__'.
    """
    stem = Path(json_filename).stem  # strip .json
    sep = "__"
    if sep in stem:
        return stem[: stem.index(sep)]
    return stem


def _safe_decimal(value: str | float | int | None) -> Decimal | None:
    """Convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _parse_quote_date(raw: str | None):
    """Parse a date string into a Python date object, returning None on failure."""
    if not raw:
        return None
    import re
    from datetime import date

    # Try common patterns — m is a tuple of groups (0-indexed)
    patterns = [
        # MM/DD/YYYY or M/D/YYYY
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", lambda m: date(int(m[2]), int(m[0]), int(m[1]))),
        # MM/DD/YY (2-digit year)
        (r"^(\d{1,2})/(\d{1,2})/(\d{2})$", lambda m: date(2000 + int(m[2]), int(m[0]), int(m[1]))),
        # YYYY-MM-DD
        (r"^(\d{4})-(\d{2})-(\d{2})$", lambda m: date(int(m[0]), int(m[1]), int(m[2]))),
        # Month DD, YYYY
        (
            r"^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$",
            None,  # handled separately
        ),
    ]

    import calendar

    month_map = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
    month_map.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})

    for pat, converter in patterns:
        m = re.match(pat, raw.strip())
        if m and converter:
            try:
                return converter(m.groups())
            except (ValueError, TypeError):
                return None

    # Try Month DD, YYYY pattern
    m = re.match(r"^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$", raw.strip())
    if m:
        month_str, day_str, year_str = m.groups()
        month_num = month_map.get(month_str[:3].lower())
        if month_num:
            try:
                return date(int(year_str), month_num, int(day_str))
            except (ValueError, TypeError):
                return None

    return None


def _items_to_jsonb(items: list) -> list[dict]:
    """Convert VendorLineItem list to JSON-serializable list of dicts."""
    result = []
    for item in items:
        d = {
            "product": item.product,
            "sku": item.sku,
            "quantity": str(item.quantity) if item.quantity is not None else None,
            "unit": item.unit,
            "unit_cost": str(item.unit_cost) if item.unit_cost is not None else None,
            "total": str(item.total) if item.total is not None else None,
            "notes": item.notes,
        }
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


async def upsert_vendor(session: AsyncSession, vendor_name: str) -> Vendor:
    """Find or create a Vendor row by canonical name."""
    stmt = select(Vendor).where(Vendor.name == vendor_name)
    result = await session.execute(stmt)
    vendor = result.scalar_one_or_none()

    if vendor is None:
        vendor = Vendor(name=vendor_name)
        session.add(vendor)
        await session.flush()  # get the UUID

    return vendor


async def find_project(session: AsyncSession, folder_name: str) -> Project | None:
    """Look up a Project by its folder_name."""
    stmt = select(Project).where(Project.folder_name == folder_name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def load_one_quote(
    session: AsyncSession,
    extraction: VendorExtractionResult,
    folder_name: str,
    source_json_path: str,
) -> str:
    """Load a single VendorExtractionResult into the DB.

    Returns: "loaded", "skipped", or "failed:<reason>"
    """
    if not extraction.success or extraction.quote is None:
        return "skipped:extraction_failed"

    quote = extraction.quote

    # --- Vendor upsert ---
    vendor: Vendor | None = None
    if quote.vendor_name:
        try:
            vendor = await upsert_vendor(session, quote.vendor_name)
        except Exception as e:
            return f"failed:vendor_upsert:{e}"

    # --- Project lookup ---
    project: Project | None = await find_project(session, folder_name)

    # --- Build VendorQuote row ---
    items_jsonb = _items_to_jsonb(quote.items)
    quote_date = _parse_quote_date(quote.quote_date)

    vq = VendorQuote(
        project_id=project.id if project else None,
        vendor_id=vendor.id if vendor else None,
        quote_number=quote.quote_number,
        quote_date=quote_date,
        items=items_jsonb,
        freight=_safe_decimal(quote.freight),
        sales_tax=_safe_decimal(quote.sales_tax),
        total=_safe_decimal(quote.grand_total),
        lead_time=quote.lead_time,
        source_file=quote.source_file,
        notes=(f"extraction_method={quote.extraction_method} confidence={quote.extraction_confidence:.2f}"),
    )
    session.add(vq)
    await session.flush()
    return "loaded"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    json_files = sorted(VENDOR_QUOTES_DIR.glob("*.json"))
    total = len(json_files)
    print(f"Found {total} JSON files in {VENDOR_QUOTES_DIR}")

    counts = {"loaded": 0, "skipped": 0, "failed": 0, "no_project": 0}
    failures: list[str] = []

    for i, json_path in enumerate(json_files, 1):
        folder_name = _parse_folder_name(json_path.name)

        # Deserialize
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            extraction = VendorExtractionResult.model_validate(raw)
        except Exception as e:
            counts["failed"] += 1
            failures.append(f"  PARSE_ERROR  {json_path.name}: {e}")
            print(f"  [{i:3d}/{total}] PARSE_ERROR  {json_path.name}")
            continue

        if not extraction.success or extraction.quote is None:
            counts["skipped"] += 1
            print(f"  [{i:3d}/{total}] SKIP (extraction failed)  {json_path.name}")
            continue

        # Load into DB — one session per file for isolation
        try:
            async with async_session() as session:
                # Check project match before loading
                project = await find_project(session, folder_name)
                if project is None:
                    counts["no_project"] += 1

                outcome = await load_one_quote(session, extraction, folder_name, str(json_path))
                await session.commit()

            if outcome == "loaded":
                counts["loaded"] += 1
                project_tag = f"project={folder_name!r}" if project else "project=NULL"
                vendor_tag = extraction.quote.vendor_name or "unknown vendor"
                print(f"  [{i:3d}/{total}] OK  {vendor_tag} | {project_tag}")
            elif outcome.startswith("skipped"):
                counts["skipped"] += 1
                print(f"  [{i:3d}/{total}] SKIP  {json_path.name}: {outcome}")
            else:
                counts["failed"] += 1
                failures.append(f"  LOAD_ERROR   {json_path.name}: {outcome}")
                print(f"  [{i:3d}/{total}] FAIL  {json_path.name}: {outcome}")

        except Exception as e:
            counts["failed"] += 1
            failures.append(f"  DB_ERROR     {json_path.name}: {type(e).__name__}: {e}")
            print(f"  [{i:3d}/{total}] DB_ERROR  {json_path.name}: {type(e).__name__}: {e}")

    # Summary
    print()
    print("=" * 60)
    print(f"SUMMARY ({total} files processed)")
    print(f"  Loaded:      {counts['loaded']}")
    print(f"  Skipped:     {counts['skipped']}")
    print(f"  Failed:      {counts['failed']}")
    print(f"  No project:  {counts['no_project']} (loaded with NULL project_id)")
    print("=" * 60)

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f)

    # Final DB counts
    print()
    async with async_session() as session:
        vq_count = (await session.execute(text("SELECT COUNT(*) FROM vendor_quotes"))).scalar()
        vendor_count = (await session.execute(text("SELECT COUNT(*) FROM vendors"))).scalar()
        print(f"DB state: {vendor_count} vendors, {vq_count} vendor_quotes")


if __name__ == "__main__":
    asyncio.run(main())
