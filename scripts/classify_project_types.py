"""Classify project_type for all projects using keyword rules.

Applies keyword-based heuristics to the project name and gc_name fields to
populate the project_type enum column for all 124 projects.

ProjectType enum values (from src/db/models.py):
  commercial_office, healthcare, education, worship, hospitality,
  residential, government, entertainment, mixed_use, other

Keyword → enum mapping:
  healthcare       → healthcare
  education        → education
  government       → government
  hospitality      → hospitality
  corporate/office → commercial_office
  religious        → worship
  multifamily      → residential
  retail/sports    → other (no dedicated enum value)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Project, ProjectType  # noqa: E402
from src.db.session import async_session  # noqa: E402

# ---------------------------------------------------------------------------
# Keyword rules
# Each entry: (ProjectType, [keywords...])
# Checked in order — first match wins.
# ---------------------------------------------------------------------------

KEYWORD_RULES: list[tuple[ProjectType, list[str]]] = [
    (
        ProjectType.HEALTHCARE,
        [
            "hospital",
            "health",
            "medical",
            "clinic",
            "surgery",
            "dental",
            "pharma",
            "biotech",
            "hca",
            "baycare",
            "adventhealth",
            "mease",
            "morton plant",
            "orlandohealth",
            " mob",  # Medical Office Building
            "mob ",
            "lecom",  # Lake Erie College of Osteopathic Medicine
            " icu ",
            " er ",  # Emergency Room — standalone word only (avoids "river", "premier", etc.)
        ],
    ),
    (
        ProjectType.EDUCATION,
        [
            "school",
            "university",
            "college",
            "academy",
            "elementary",
            "middle school",
            "high school",
            " hs ",  # "Alonso HS", "Seven Rivers HS"
            "charter",
            "montessori",
            "campus",
            "learning",
            "steam",
            "institute",
            "usf",
            " uf ",
            "ucf",
            "fsu",
            "fgcu",
            "jesuit",  # Jesuit high school
        ],
    ),
    (
        ProjectType.GOVERNMENT,
        [
            "government",
            "county",
            "city of",
            "municipal",
            "courthouse",
            "library",
            "fire station",
            "police",
            "federal",
            " dot",
            "dot ",
            "transit",
        ],
    ),
    (
        ProjectType.HOSPITALITY,
        [
            "hotel",
            "resort",
            "motel",
            " inn",
            "inn ",
            "marriott",
            "hilton",
            "hyatt",
            "westin",
            "wyndham",
            "loews",
            "ritz",
            "sheraton",
        ],
    ),
    (
        ProjectType.COMMERCIAL_OFFICE,
        [
            "office",
            "headquarters",
            " hq",
            "hq ",
            "corporate",
            "financial",
            "bank",
            "law firm",
            "insurance",
            "grant thornton",
            "engineering",
            "partners",
        ],
    ),
    (
        ProjectType.WORSHIP,
        [
            "church",
            "chapel",
            "synagogue",
            "mosque",
            "temple",
            "faith",
            "ministry",
            "worship",
            "baptist",
            "parish",
            "evangelist",
            "catholic",
        ],
    ),
    (
        ProjectType.RESIDENTIAL,
        [
            "apartment",
            "condo",
            "residential",
            "housing",
            "living",
            "multifamily",
            "multi-family",
            "village",  # retirement/senior living communities (Freedom Village, etc.)
            "flats",  # District Flats
            "regency",  # Regency at Waterset
            "vesta",  # Vesta residential brand
        ],
    ),
    # retail and sports/fitness map to OTHER (no dedicated enum value)
    (
        ProjectType.OTHER,
        [
            "retail",
            "store",
            "shop",
            "mall",
            "outlet",
            "arena",
            "stadium",
            "gym",
            "fitness",
            "recreation",
            "aquatic",
        ],
    ),
]


def _classify(name: str | None, gc_name: str | None) -> tuple[ProjectType, str]:
    """Return (ProjectType, reason_string) for a project.

    Strategy:
      1. Try to match keywords against project name.
      2. If no match, try gc_name.
      3. Fall back to ProjectType.OTHER.
    """
    name_lower = (name or "").lower()
    gc_lower = (gc_name or "").lower()

    # Try name first
    for ptype, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw in name_lower:
                return ptype, f"name match: '{kw}'"

    # Try gc_name
    for ptype, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw in gc_lower:
                return ptype, f"gc_name match: '{kw}'"

    return ProjectType.OTHER, "no keyword match"


async def classify() -> None:
    print("=== Acoustimator Project Type Classification ===\n")

    async with async_session() as session:
        result = await session.execute(select(Project))
        projects = result.scalars().all()
        print(f"Projects loaded: {len(projects)}\n")

        updates: list[dict] = []
        type_counts: dict[str, int] = {}
        already_set = 0

        for project in projects:
            ptype, reason = _classify(project.name, project.gc_name)
            type_counts[ptype.value] = type_counts.get(ptype.value, 0) + 1

            if project.project_type is not None and project.project_type == ptype:
                already_set += 1
                print(f"  [UNCHANGED {ptype.value:<20}] {project.name!r:<50}  gc={project.gc_name!r}  ({reason})")
                continue

            tag = "RECLASSIFY" if project.project_type is not None else "CLASSIFY  "
            print(f"  [{tag} {ptype.value:<20}] {project.name!r:<50}  gc={project.gc_name!r}  ({reason})")
            updates.append({"id": project.id, "project_type": ptype})

        print(f"\nApplying {len(updates)} DB updates …")
        for upd in updates:
            project_id = upd["id"]
            await session.execute(
                update(Project).where(Project.id == project_id).values(project_type=upd["project_type"])
            )
        await session.commit()
        print("Committed.\n")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)
    print(f"  Total projects:       {len(projects)}")
    print(f"  Unchanged (same type):  {already_set}")
    print(f"  Updated (new/changed):  {len(updates)}")
    print()
    print("  Distribution:")
    for ptype_val, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ptype_val:<22}  {count:>4}")

    # ------------------------------------------------------------------
    # Verification query
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("DB VERIFICATION (project_type distribution)")
    print("=" * 60)
    async with async_session() as session:
        from sqlalchemy import text

        rows = await session.execute(
            text("SELECT project_type, COUNT(*) AS cnt FROM projects GROUP BY project_type ORDER BY cnt DESC")
        )
        for row in rows:
            label = row[0] if row[0] is not None else "NULL"
            print(f"  {label:<22}  {row[1]:>4}")


if __name__ == "__main__":
    asyncio.run(classify())
