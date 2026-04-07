#!/usr/bin/env python3
"""Batch plan reader for all Commercial Acoustics projects.

Walks the +ITBs directory, finds drawing PDFs, and runs the plan reader on each.
Results are saved to data/extracted/plans/{project_folder}/{filename}.json.

Usage:
    python scripts/read_plans.py                          # Process all drawing PDFs
    python scripts/read_plans.py --single path/to/file   # Single file
    python scripts/read_plans.py --dry-run               # List files only
    python scripts/read_plans.py --limit 10              # First N files
    python scripts/read_plans.py --project "BMG 231"     # Single project folder
"""

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

# Ensure project root is on sys.path when invoked directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

# ---------------------------------------------------------------------------
# Optional plan_reader import — graceful degradation if not yet wired
# ---------------------------------------------------------------------------
try:
    from src.extraction.plan_reader import read_plan

    PLAN_READER_AVAILABLE = True
except ImportError as _import_err:
    PLAN_READER_AVAILABLE = False
    _PLAN_READER_ERR = str(_import_err)

    def read_plan(pdf_path, use_vision=True):  # type: ignore[misc]
        raise RuntimeError(f"plan_reader not available: {_PLAN_READER_ERR}")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

# Filename substrings that indicate a drawing PDF (case-insensitive)
_INCLUDE_PATTERNS: list[str] = [
    "rcp",
    "reflected ceiling",
    "floor plan",
    "takeoff dwg",
    "act dwg",
    "panels",  # covers "Panels & ACT Dwgs", "Panels Dwg", "Dwg Panels"
    "dwg",  # covers standalone "Dwg" variants
    "architectural",
    "drawing",
    "acoustic takeoff",  # very common in this dataset
]

# Filename substrings that disqualify a PDF (case-insensitive)
_EXCLUDE_PATTERNS: list[str] = [
    "quote",
    "t-004",
    "vendor",
    "signed",
    "invoice",
    "purchase order",
]


def _is_drawing_pdf(path: Path) -> bool:
    """Return True if the file looks like an architectural drawing PDF."""
    name_lower = path.name.lower()
    excluded = any(ex in name_lower for ex in _EXCLUDE_PATTERNS)
    if excluded:
        return False
    included = any(inc in name_lower for inc in _INCLUDE_PATTERNS)
    return included


def find_drawing_pdfs(
    source_dir: Path,
    project_filter: str | None = None,
) -> list[tuple[Path, str]]:
    """Walk source_dir (max depth 2) and return (pdf_path, project_folder) pairs.

    Parameters
    ----------
    source_dir:
        Root of the +ITBs directory.
    project_filter:
        If provided, only return files whose project folder name contains this string.

    Returns
    -------
    Sorted list of (absolute_pdf_path, project_folder_name) tuples.
    """
    results: list[tuple[Path, str]] = []

    # Each sub-directory of source_dir is one project
    for project_dir in sorted(source_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        project_name = project_dir.name
        if project_filter and project_filter.lower() not in project_name.lower():
            continue

        # Search both at top level and one level deeper (some projects have sub-folders)
        candidates: list[Path] = list(project_dir.glob("*.pdf"))
        for sub in project_dir.iterdir():
            if sub.is_dir():
                candidates.extend(sub.glob("*.pdf"))

        for pdf in sorted(candidates):
            if _is_drawing_pdf(pdf):
                results.append((pdf, project_name))

    return results


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def _result_to_json(result: object) -> str:
    """Serialise a PlanReadResult (Pydantic model) to indented JSON."""
    if hasattr(result, "model_dump"):
        data = result.model_dump(mode="json")
    else:
        data = dict(result)  # type: ignore[call-overload]
    return json.dumps(data, indent=2, cls=_DecimalEncoder)


# ---------------------------------------------------------------------------
# Progress / summary helpers
# ---------------------------------------------------------------------------


def _summarise_result(result: object) -> tuple[int, Decimal | None]:
    """Return (n_scope_suggestions, total_area_sf) from a PlanReadResult."""
    if hasattr(result, "scope_suggestions"):
        n_scopes = len(result.scope_suggestions)  # type: ignore[union-attr]
    else:
        n_scopes = 0
    sf: Decimal | None = getattr(result, "total_area_sf", None)
    return n_scopes, sf


def _fmt_sf(sf: Decimal | None) -> str:
    if sf is None:
        return "—"
    return f"{sf:,.0f} SF"


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------


def run_dry_run(source_dir: Path, limit: int | None, project_filter: str | None) -> None:
    """List drawing PDFs that would be processed, without running extraction."""
    files = find_drawing_pdfs(source_dir, project_filter)
    total_found = len(files)
    if limit:
        files = files[:limit]

    print(f"Drawing PDFs found: {total_found}")
    if project_filter:
        print(f"(filtered to project: '{project_filter}')")
    if limit and limit < total_found:
        print(f"(showing first {limit} of {total_found})")
    print()

    for i, (pdf_path, project_name) in enumerate(files, 1):
        size_mb = pdf_path.stat().st_size / 1_048_576
        rel = f"{project_name}/{pdf_path.name}"
        print(f"  {i:3d}. {rel}  [{size_mb:.1f} MB]")

    print(f"\nTotal: {len(files)} files")
    # Rough estimate: ~30s per file (PDF parse + optional vision API)
    est_minutes = (len(files) * 30) / 60
    print(f"Estimated run time: ~{est_minutes:.0f} min (30 s/file, no vision)")


def run_single(pdf_path: Path, output_base: Path) -> None:
    """Run the plan reader on a single file and save the result."""
    if not PLAN_READER_AVAILABLE:
        print(f"WARNING: plan_reader not available — {_PLAN_READER_ERR}", file=sys.stderr)
        sys.exit(1)

    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    project_name = pdf_path.parent.name
    output_dir = output_base / project_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (pdf_path.stem + ".json")

    print(f"Reading: {project_name}/{pdf_path.name}")
    t0 = time.monotonic()
    result = read_plan(pdf_path, use_vision=False)
    elapsed = time.monotonic() - t0

    n_scopes, sf = _summarise_result(result)
    status = "OK" if getattr(result, "success", True) else "FAIL"
    print(f"  [{status}] {n_scopes} scopes, {_fmt_sf(sf)}  ({elapsed:.1f}s)")

    output_path.write_text(_result_to_json(result), encoding="utf-8")
    print(f"  Saved → {output_path}")


def run_batch(
    source_dir: Path,
    output_base: Path,
    limit: int | None,
    project_filter: str | None,
    skip_existing: bool = False,
) -> None:
    """Run the plan reader on all discovered drawing PDFs."""
    if not PLAN_READER_AVAILABLE:
        print(
            f"WARNING: src.extraction.plan_reader could not be imported:\n  {_PLAN_READER_ERR}\n"
            "Skipping extraction. Fix the import error and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    files = find_drawing_pdfs(source_dir, project_filter)
    if limit:
        files = files[:limit]

    if not files:
        print("No drawing PDFs found matching the current filters.", file=sys.stderr)
        sys.exit(1)

    total = len(files)
    print(f"Processing {total} drawing PDF(s)...")
    print(f"Output: {output_base}\n")

    ok_count = 0
    fail_count = 0
    grand_sf: Decimal = Decimal("0")
    total_scopes = 0
    start = time.monotonic()

    for idx, (pdf_path, project_name) in enumerate(files, 1):
        output_dir = output_base / project_name
        output_path = output_dir / (pdf_path.stem + ".json")

        if skip_existing and output_path.exists():
            print(f"  [{idx}/{total}] [SKIP] {project_name}/{pdf_path.name}")
            continue

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            t0 = time.monotonic()
            result = read_plan(pdf_path, use_vision=False)
            elapsed = time.monotonic() - t0
            n_scopes, sf = _summarise_result(result)
            success = getattr(result, "success", True)
            status = "OK" if success else "FAIL"

            output_path.write_text(_result_to_json(result), encoding="utf-8")

            sf_str = _fmt_sf(sf)
            print(
                f"  [{idx}/{total}] [{status}] {project_name}/{pdf_path.name}"
                f" → {n_scopes} scopes suggested, {sf_str}  ({elapsed:.1f}s)"
            )

            if success:
                ok_count += 1
                total_scopes += n_scopes
                if sf:
                    grand_sf += sf
            else:
                fail_count += 1
                err = getattr(result, "error", None)
                if err:
                    print(f"           ERROR: {err}", file=sys.stderr)

        except Exception as exc:
            fail_count += 1
            print(
                f"  [{idx}/{total}] [FAIL] {project_name}/{pdf_path.name}: {exc}",
                file=sys.stderr,
            )

    elapsed_total = time.monotonic() - start
    processed = ok_count + fail_count
    success_rate = (ok_count / processed * 100) if processed > 0 else 0.0

    print("\n" + "=" * 60)
    print("PLAN READER SUMMARY")
    print("=" * 60)
    print(f"  Files found:          {total}")
    print(f"  Processed:            {processed}")
    print(f"  Successful:           {ok_count}  ({success_rate:.0f}%)")
    print(f"  Failed:               {fail_count}")
    print(f"  Total scope items:    {total_scopes}")
    print(f"  Total area found:     {_fmt_sf(grand_sf if grand_sf else None)}")
    print(f"  Elapsed:              {elapsed_total:.1f}s")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch plan reader — finds drawing PDFs and extracts scope data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--single",
        metavar="PATH",
        help="Read a single PDF file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List drawing PDFs that would be processed, without extracting.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process only the first N files.",
    )
    parser.add_argument(
        "--project",
        metavar="NAME",
        help='Restrict to folders whose name contains NAME (e.g. "BMG 231").',
    )
    parser.add_argument(
        "--source",
        metavar="DIR",
        help="Override the source directory (default: DATA_SOURCE_PATH from .env).",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default="data/extracted/plans",
        help="Base output directory (default: data/extracted/plans).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already have a JSON output.",
    )
    args = parser.parse_args()

    source_dir = Path(args.source) if args.source else settings.data_source_path
    output_base = Path(args.output)

    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    if args.single:
        run_single(Path(args.single), output_base)
    elif args.dry_run:
        run_dry_run(source_dir, args.limit, args.project)
    else:
        run_batch(source_dir, output_base, args.limit, args.project, args.skip_existing)


if __name__ == "__main__":
    main()
