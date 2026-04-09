"""Backfill quote_date for all projects from extracted quote JSONs.

Scans data/extracted/quotes/*.json, extracts quote_date and source_file,
derives the project folder_name from source_file, matches to a project row,
and updates quote_date if not already set.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select, update

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.loader import _parse_date  # noqa: E402
from src.db.models import Project  # noqa: E402
from src.db.session import async_session  # noqa: E402

QUOTES_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted" / "quotes"


def _extract_folder_name(source_file: str) -> str | None:
    """Derive the project folder_name from a source_file path.

    Rule:
      - Find the '+ITBs/' segment
      - Skip '++Archive/' if present as the next component
      - Return the next path component as the folder name
    """
    # Normalise separators
    parts = re.split(r"[/\\]", source_file)
    try:
        idx = next(i for i, p in enumerate(parts) if p == "+ITBs")
    except StopIteration:
        return None

    remaining = parts[idx + 1 :]
    if not remaining:
        return None

    # Skip the archive prefix folder if present
    if remaining[0] == "++Archive":
        remaining = remaining[1:]

    if not remaining:
        return None

    return remaining[0].strip() or None


async def backfill() -> None:
    json_files = sorted(QUOTES_DIR.glob("*.json"))
    print(f"Found {len(json_files)} quote JSON files in {QUOTES_DIR}")

    # Build a mapping: folder_name (lower) -> list of parsed dates
    folder_dates: dict[str, list] = {}
    unresolvable: list[str] = []

    for jf in json_files:
        try:
            data = json.loads(jf.read_text())
        except Exception as exc:
            print(f"  [WARN] Could not read {jf.name}: {exc}")
            continue

        quote = data.get("quote") or {}
        raw_date = quote.get("quote_date")
        source_file = quote.get("source_file", "")

        folder = _extract_folder_name(source_file)
        if not folder:
            unresolvable.append(jf.name)
            continue

        parsed = _parse_date(raw_date)
        key = folder.lower()
        if key not in folder_dates:
            folder_dates[key] = []
        if parsed is not None:
            folder_dates[key].append(parsed)

    print(f"  Resolved {len(folder_dates)} unique folder names from JSONs")
    print(f"  Unresolvable source_file paths: {len(unresolvable)}")

    # Now update the database
    matched = 0
    updated = 0
    no_match = 0
    no_date = 0

    async with async_session() as session:
        # Load all projects
        result = await session.execute(select(Project))
        projects = result.scalars().all()
        print(f"\nProjects in DB: {len(projects)}")

        for project in projects:
            fn = (project.folder_name or "").lower().strip()
            if not fn:
                continue

            if fn not in folder_dates:
                no_match += 1
                continue

            matched += 1
            dates = folder_dates[fn]

            if not dates:
                no_date += 1
                continue

            # Use the earliest date found across all quotes for this project
            chosen = min(dates)

            if project.quote_date is None or project.quote_date != chosen:
                await session.execute(update(Project).where(Project.id == project.id).values(quote_date=chosen))
                updated += 1

        await session.commit()

    print("\n--- Backfill Summary ---")
    print(f"  Projects in DB:          {len(projects)}")
    print(f"  Matched to JSON data:    {matched}")
    print(f"  Updated (quote_date set):{updated}")
    print(f"  Matched but no date:     {no_date}")
    print(f"  No folder match:         {no_match}")
    print(f"  Unresolvable source_file:{len(unresolvable)}")


if __name__ == "__main__":
    asyncio.run(backfill())
