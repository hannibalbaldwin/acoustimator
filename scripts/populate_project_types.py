"""One-time migration: populate project_type for all projects where it is NULL.

Imports the keyword classification logic from classify_project_types.py —
does NOT duplicate it.  Only touches rows where project_type IS NULL.

Usage:
    python scripts/populate_project_types.py [--dry-run]

    --dry-run   Show what would be updated without writing to the DB.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import classification logic from the canonical source — never duplicate it.
from scripts.classify_project_types import _classify  # noqa: E402
from src.db.models import Project  # noqa: E402
from src.db.session import async_session  # noqa: E402


async def populate(dry_run: bool = False) -> dict[str, int]:
    """Classify and update all projects where project_type IS NULL.

    Returns a summary dict with keys:
      - per-type counts of updates (e.g. "healthcare": 3)
      - "total_updated": total rows written
      - "remaining_null": rows still NULL after this run (always 0 unless dry_run)
    """
    label = "[DRY RUN] " if dry_run else ""
    print(f"=== {label}Acoustimator: Populate project_type (NULL rows only) ===\n")

    type_counts: dict[str, int] = {}
    updates: list[dict] = []

    async with async_session() as session:
        # Only fetch rows where project_type is currently NULL
        result = await session.execute(
            select(Project).where(Project.project_type.is_(None)).order_by(Project.id)
        )
        null_projects = result.scalars().all()
        print(f"Projects with NULL project_type: {len(null_projects)}\n")

        if not null_projects:
            print("Nothing to do — all projects already have a project_type.")
            return {"total_updated": 0, "remaining_null": 0}

        for project in null_projects:
            ptype, reason = _classify(project.name, project.gc_name)
            type_counts[ptype.value] = type_counts.get(ptype.value, 0) + 1
            updates.append({"id": project.id, "project_type": ptype})
            print(
                f"  [{label}→ {ptype.value:<22}] "
                f"{project.name!r:<50}  gc={project.gc_name!r}  ({reason})"
            )

        if not dry_run:
            print(f"\nApplying {len(updates)} DB updates …")
            for upd in updates:
                await session.execute(
                    update(Project)
                    .where(Project.id == upd["id"])
                    .values(project_type=upd["project_type"])
                )
            await session.commit()
            print("Committed.\n")
        else:
            print(f"\n[DRY RUN] Would apply {len(updates)} updates (skipping DB write).\n")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_updated = len(updates) if not dry_run else 0
    remaining_null = 0 if not dry_run else len(updates)

    print("=" * 60)
    print(f"{label}SUMMARY")
    print("=" * 60)
    print(f"  Projects classified: {len(updates)}")
    print(f"  DB rows written:     {total_updated}")
    print(f"  Remaining NULL:      {remaining_null}")
    print()
    print("  Distribution of newly classified projects:")
    for ptype_val, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ptype_val:<22}  {count:>4}")

    # ------------------------------------------------------------------
    # Verification query (only when we actually wrote)
    # ------------------------------------------------------------------
    if not dry_run:
        print("\n" + "=" * 60)
        print("DB VERIFICATION (project_type distribution after run)")
        print("=" * 60)
        async with async_session() as session:
            from sqlalchemy import text

            rows = await session.execute(
                text(
                    "SELECT project_type, COUNT(*) AS cnt"
                    " FROM projects"
                    " GROUP BY project_type"
                    " ORDER BY cnt DESC"
                )
            )
            null_count = 0
            for row in rows:
                label_col = row[0] if row[0] is not None else "NULL"
                if row[0] is None:
                    null_count = row[1]
                print(f"  {label_col:<22}  {row[1]:>4}")

        remaining_null = null_count

    summary: dict[str, int] = {**type_counts, "total_updated": total_updated, "remaining_null": remaining_null}
    return summary


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(populate(dry_run=dry_run))
