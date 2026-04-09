"""Comprehensive data enrichment for the Acoustimator projects table.

Populates quote_date (and opportunistically gc_name) for projects that are
missing them, using a multi-source priority chain:

  Priority 1 — Real date from quotes/*.json extractions
               (i.e. the Claude-extracted quote_date is NOT the bogus 2024-02-29
               placeholder that Claude hallucinated when it couldn't find a date)

  Priority 2 — Modification date of the Quote PDF in the project folder
               (Quote PDFs are only saved/synced when the quote is issued, so
               their mtime is a reliable proxy for the quote date)

  Priority 3 — Date embedded in the Excel buildup filename
               (Many files are named like "BayCare Carrollwood 8.27.25.xlsx",
               giving an exact buildup-date which closely tracks the quote date)

  Priority 4 — Modification date of the Excel buildup
               (Least precise, but gives the right year and approximate month)

For quote_date fields that already hold the 2024-02-29 bogus value (set by the
previous backfill run), the script replaces them with the best available date
from the priority chain above.  Real dates that are already in the DB are left
unchanged.

gc_name enrichment: sourced only from the buildup extraction JSONs
(data/extracted/*.json) since the quotes JSONs contain garbage gc_name values.
Only updates projects where gc_name is currently NULL.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Project  # noqa: E402
from src.db.session import async_session  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITB_DIR = Path(
    "/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs"
)
EXTRACTED_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted"
QUOTES_DIR = EXTRACTED_DIR / "quotes"

# Claude's fabricated fallback date — treat as NULL
BOGUS_DATE = date(2024, 2, 29)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(raw: str | None) -> date | None:
    """Parse a free-form date string into a Python date.

    Handles ISO dates, US M/D/Y formats, and long month-name variants.
    Returns None for anything that can't be parsed or is the known bogus date.
    """
    if not raw:
        return None
    s = raw.strip()
    if s.upper() in ("NA", "N/A", "NONE", "TBD", "TBA", "-", ""):
        return None

    for fmt in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
    ):
        try:
            d = datetime.strptime(s, fmt).date()
            return d if d != BOGUS_DATE else None
        except ValueError:
            pass
    return None


def _folder_path(folder_name: str) -> Path:
    """Return the absolute path to a project folder in the ITB directory.

    Some DB folder_name values are missing the leading '+' that appears on disk
    (e.g. DB stores 'District Flats' but the folder is '+District Flats').
    We try the exact name first, then the '+'-prefixed variant.
    """
    exact = ITB_DIR / folder_name
    if exact.is_dir():
        return exact
    plus = ITB_DIR / f"+{folder_name}"
    if plus.is_dir():
        return plus
    return exact  # return exact path so callers see "not found"


def _extract_itb_folder(source_file: str) -> str | None:
    """Derive the project folder name from a source_file path.

    Strips the +ITBs prefix (and ++Archive sub-directory if present) and
    returns the next path component.
    """
    parts = re.split(r"[/\\]", source_file)
    try:
        idx = next(i for i, p in enumerate(parts) if p == "+ITBs")
    except StopIteration:
        return None
    remaining = parts[idx + 1 :]
    if not remaining:
        return None
    if remaining[0] == "++Archive":
        remaining = remaining[1:]
    return remaining[0].strip() or None if remaining else None


# ---------------------------------------------------------------------------
# Source 1: quotes/*.json extractions (real dates only)
# ---------------------------------------------------------------------------


def _build_quotes_date_map() -> dict[str, date]:
    """Return {folder_name: earliest_real_date} from all quotes/*.json files.

    Skips the BOGUS_DATE placeholder and only returns folders where at least
    one quote had a genuinely extracted date.
    """
    folder_best: dict[str, date] = {}

    if not QUOTES_DIR.exists():
        print(f"  [WARN] quotes directory not found: {QUOTES_DIR}")
        return folder_best

    for jf in QUOTES_DIR.glob("*.json"):
        try:
            data = json.loads(jf.read_text())
        except Exception as exc:
            print(f"  [WARN] Could not read {jf.name}: {exc}")
            continue

        quote = data.get("quote") or {}
        raw_date = quote.get("quote_date")
        source_file = quote.get("source_file", "") or ""

        folder = _extract_itb_folder(source_file)
        if not folder:
            continue

        parsed = _parse_date(raw_date)  # returns None for BOGUS_DATE
        if parsed is None:
            continue

        if folder not in folder_best or parsed < folder_best[folder]:
            folder_best[folder] = parsed

    return folder_best


# ---------------------------------------------------------------------------
# Source 2: File-system dates (Quote PDFs and Excel buildups)
# ---------------------------------------------------------------------------


def _file_date_for_folder(folder_name: str) -> tuple[Optional[date], str]:
    """Return (best_date, source_description) from files in the project folder.

    Priority within the folder:
      1. Earliest Quote*.pdf modification date
      2. Date embedded in an Excel filename (e.g. "Buildup 8.27.25.xlsx")
      3. Earliest Excel modification date
    """
    folder_path = _folder_path(folder_name)
    if not folder_path.is_dir():
        return None, "folder not found"

    quote_pdf_dates: list[date] = []
    excel_name_dates: list[date] = []
    excel_mtime_dates: list[date] = []

    try:
        entries = list(folder_path.iterdir())
    except OSError:
        return None, "os error"

    for entry in entries:
        if not entry.is_file():
            continue
        name = entry.name
        if name.startswith(".") or name.startswith("~$"):
            continue
        suffix = entry.suffix.lower()

        if suffix == ".pdf" and re.match(r"quote", name, re.IGNORECASE):
            # Quote PDF — use modification time
            try:
                dt = datetime.fromtimestamp(entry.stat().st_mtime).date()
                quote_pdf_dates.append(dt)
            except OSError:
                pass

        elif suffix == ".xlsx":
            # Try to parse a date from the filename (e.g. "Buildup 8.27.25.xlsx")
            dm = re.search(r"(\d{1,2})[._](\d{1,2})[._](\d{2,4})", name)
            if dm:
                try:
                    mon, day, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                    if yr < 100:
                        yr += 2000
                    if 2019 <= yr <= 2027 and 1 <= mon <= 12 and 1 <= day <= 31:
                        excel_name_dates.append(date(yr, mon, day))
                except (ValueError, OSError):
                    pass
            else:
                # Fall back to modification time
                try:
                    dt = datetime.fromtimestamp(entry.stat().st_mtime).date()
                    excel_mtime_dates.append(dt)
                except OSError:
                    pass

    if quote_pdf_dates:
        return min(quote_pdf_dates), "quote_pdf_mtime"
    if excel_name_dates:
        return min(excel_name_dates), "xlsx_filename_date"
    if excel_mtime_dates:
        return min(excel_mtime_dates), "xlsx_mtime"
    return None, "no files"


# ---------------------------------------------------------------------------
# Source 3: Excel buildup extractions (gc_name only)
# ---------------------------------------------------------------------------


def _build_gc_map() -> dict[str, str]:
    """Return {folder_name: gc_name} from data/extracted/*.json buildup files.

    These are the only reliable source of gc_name for the active projects.
    """
    gc_map: dict[str, str] = {}

    if not EXTRACTED_DIR.exists():
        return gc_map

    for jf in EXTRACTED_DIR.glob("*.json"):
        try:
            data = json.loads(jf.read_text())
        except Exception:
            continue

        if not isinstance(data, dict):
            continue
        proj = data.get("project")
        if not isinstance(proj, dict):
            continue

        folder = proj.get("folder_name")
        gc = proj.get("gc_name")
        if folder and gc and str(gc).strip():
            gc_map[folder] = str(gc).strip()

    return gc_map


# ---------------------------------------------------------------------------
# Main enrichment routine
# ---------------------------------------------------------------------------


async def enrich() -> None:
    print("=== Acoustimator Data Enrichment: quote_date + gc_name ===\n")

    # Build lookup tables
    print("Building date lookup from quotes/*.json …")
    quotes_dates = _build_quotes_date_map()
    print(f"  → {len(quotes_dates)} folders with real dates from quote extractions\n")

    print("Building gc_name lookup from data/extracted/*.json …")
    gc_map = _build_gc_map()
    print(f"  → {len(gc_map)} folders with gc_name from buildup extractions\n")

    # Stats
    stats = {
        "already_real": 0,        # had a non-bogus date — skipped
        "bogus_replaced": 0,      # had BOGUS_DATE → replaced
        "null_filled_quotes": 0,  # NULL → date from quotes JSON
        "null_filled_files": 0,   # NULL → date from file system
        "null_unfilled": 0,       # NULL → still NULL (no data found)
        "gc_updated": 0,          # gc_name updated
        "gc_skipped": 0,          # gc_name already set
    }

    async with async_session() as session:
        result = await session.execute(select(Project))
        projects = result.scalars().all()
        print(f"Projects in DB: {len(projects)}\n")

        updates: list[dict] = []  # collect all updates, apply in one pass

        for project in projects:
            folder = (project.folder_name or "").strip()
            if not folder:
                continue

            # ------------------------------------------------------------------
            # Determine new quote_date
            # ------------------------------------------------------------------
            current_date = project.quote_date
            new_date: date | None = None
            date_source: str = ""

            if current_date is not None and current_date != BOGUS_DATE:
                # Already has a real date — leave it alone
                stats["already_real"] += 1
                new_date = current_date  # no change needed
            else:
                # Need to find a date (either NULL or BOGUS)
                is_bogus = current_date == BOGUS_DATE

                # Priority 1: quotes JSON real date
                if folder in quotes_dates:
                    new_date = quotes_dates[folder]
                    date_source = "quotes_json"
                else:
                    # Priority 2-4: file system
                    fs_date, fs_source = _file_date_for_folder(folder)
                    if fs_date is not None:
                        new_date = fs_date
                        date_source = fs_source

                if new_date is not None:
                    if is_bogus:
                        stats["bogus_replaced"] += 1
                        print(
                            f"  [BOGUS→REAL] {folder}: {current_date} → {new_date}  ({date_source})"
                        )
                    else:
                        stats["null_filled_quotes" if date_source == "quotes_json" else "null_filled_files"] += 1
                        print(
                            f"  [NULL→DATE ] {folder}: → {new_date}  ({date_source})"
                        )
                else:
                    if not is_bogus:
                        stats["null_unfilled"] += 1
                        print(f"  [NO DATA   ] {folder}: still NULL")

            # ------------------------------------------------------------------
            # Determine new gc_name
            # ------------------------------------------------------------------
            new_gc: str | None = None
            if project.gc_name is None and folder in gc_map:
                new_gc = gc_map[folder]
                stats["gc_updated"] += 1
                print(f"  [GC UPDATE ] {folder}: gc_name → {new_gc!r}")
            elif project.gc_name is not None:
                stats["gc_skipped"] += 1

            # ------------------------------------------------------------------
            # Queue update if anything changed
            # ------------------------------------------------------------------
            update_vals: dict = {}
            if new_date is not None and new_date != current_date:
                update_vals["quote_date"] = new_date
            if new_gc is not None:
                update_vals["gc_name"] = new_gc

            if update_vals:
                updates.append({"id": project.id, **update_vals})

        # Apply all updates
        print(f"\nApplying {len(updates)} DB updates …")
        for upd in updates:
            project_id = upd.pop("id")
            await session.execute(
                update(Project).where(Project.id == project_id).values(**upd)
            )
        await session.commit()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ENRICHMENT SUMMARY")
    print("=" * 60)
    total = sum(stats.values())
    print(f"  Projects with real quote_date (unchanged):  {stats['already_real']}")
    print(f"  Bogus 2024-02-29 dates replaced:            {stats['bogus_replaced']}")
    print(f"  NULL dates filled (from quotes JSON):       {stats['null_filled_quotes']}")
    print(f"  NULL dates filled (from file system):       {stats['null_filled_files']}")
    print(f"  NULL dates — no source found:               {stats['null_unfilled']}")
    print(f"  gc_name updated:                            {stats['gc_updated']}")
    print(f"  gc_name already set (skipped):              {stats['gc_skipped']}")
    filled = stats["bogus_replaced"] + stats["null_filled_quotes"] + stats["null_filled_files"]
    total_with_date = stats["already_real"] + filled
    print(
        f"\n  Total projects with quote_date after run:   {total_with_date} / "
        f"{stats['already_real'] + stats['bogus_replaced'] + stats['null_filled_quotes'] + stats['null_filled_files'] + stats['null_unfilled']} "
        f"({100 * total_with_date // max(1, stats['already_real'] + stats['bogus_replaced'] + stats['null_filled_quotes'] + stats['null_filled_files'] + stats['null_unfilled'])}%)"
    )


if __name__ == "__main__":
    asyncio.run(enrich())
