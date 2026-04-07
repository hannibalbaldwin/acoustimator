#!/usr/bin/env python3
"""Batch estimation script — reads pre-extracted plan JSONs and produces cost estimates.

Walks data/extracted/plans/ for *.json files (PlanReadResult exports), runs
estimate_from_plan_result() on each, and saves estimate JSON to
data/estimates/{project_folder}/{filename}_estimate.json.

Usage:
    python scripts/estimate_from_plans.py                        # all projects
    python scripts/estimate_from_plans.py --project "Seven Pines"  # single project
    python scripts/estimate_from_plans.py --dry-run              # list only
    python scripts/estimate_from_plans.py --export-excel         # write .xlsx per project
    python scripts/estimate_from_plans.py --limit 5              # first N
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

# Ensure project root on sys.path when invoked directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.plan_parser.models import PlanReadResult  # noqa: E402

# ---------------------------------------------------------------------------
# Optional imports — graceful degradation when Phase 5 modules aren't ready
# ---------------------------------------------------------------------------

try:
    from src.estimation.estimator import estimate_from_plan_result

    ESTIMATOR_AVAILABLE = True
    _ESTIMATOR_ERR = ""
except ImportError as _e:
    ESTIMATOR_AVAILABLE = False
    _ESTIMATOR_ERR = str(_e)

    def estimate_from_plan_result(plan_result):  # type: ignore[misc]
        raise RuntimeError(f"estimator not available: {_ESTIMATOR_ERR}")


try:
    from src.estimation.excel_writer import write_estimate_to_excel

    EXCEL_WRITER_AVAILABLE = True
    _EXCEL_WRITER_ERR = ""
except ImportError as _e:
    EXCEL_WRITER_AVAILABLE = False
    _EXCEL_WRITER_ERR = str(_e)

    def write_estimate_to_excel(estimate, output_path):  # type: ignore[misc]
        raise RuntimeError(f"excel_writer not available: {_EXCEL_WRITER_ERR}")


try:
    from src.estimation.confidence import ConfidenceLevel, format_confidence_badge

    CONFIDENCE_AVAILABLE = True
except ImportError:
    CONFIDENCE_AVAILABLE = False

    class ConfidenceLevel:  # type: ignore[no-redef]
        HIGH = "HIGH"
        MEDIUM = "MEDIUM"
        LOW = "LOW"

    def format_confidence_badge(level) -> str:  # type: ignore[misc]
        return str(level)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLANS_DIR = Path("data/extracted/plans")
ESTIMATES_DIR = Path("data/estimates")


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def _to_json(obj: object) -> str:
    """Serialise a Pydantic model (or dict) to indented JSON."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump(mode="json")  # type: ignore[union-attr]
    else:
        data = dict(obj)  # type: ignore[call-overload]
    return json.dumps(data, indent=2, cls=_DecimalEncoder)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_plan_jsons(
    plans_dir: Path,
    project_filter: str | None = None,
) -> list[tuple[Path, str]]:
    """Walk plans_dir for *.json files and return (json_path, project_folder) pairs.

    Searches both the top-level directory and one level of sub-folders (where
    read_plans.py saves per-project files).

    Parameters
    ----------
    plans_dir:
        Root of data/extracted/plans/.
    project_filter:
        If provided, restrict to project folders whose name contains this string.

    Returns
    -------
    Sorted list of (absolute_json_path, project_folder_name) tuples.
    """
    results: list[tuple[Path, str]] = []

    if not plans_dir.exists():
        return results

    # Sub-directories are per-project folders
    for entry in sorted(plans_dir.iterdir()):
        if entry.is_dir():
            project_name = entry.name
            if project_filter and project_filter.lower() not in project_name.lower():
                continue
            for json_file in sorted(entry.glob("*.json")):
                results.append((json_file, project_name))
        elif (
            entry.is_file()
            and entry.suffix == ".json"
            and entry.name
            not in {
                "price_index.json",
                "products_catalog.json",
                "product_review_queue.json",
            }
        ):
            # Flat JSON files directly under plans_dir
            project_name = entry.stem
            if project_filter and project_filter.lower() not in project_name.lower():
                continue
            results.append((entry, project_name))

    return results


# ---------------------------------------------------------------------------
# Loading / validation
# ---------------------------------------------------------------------------


def load_plan_result(json_path: Path) -> PlanReadResult | None:
    """Load a PlanReadResult from a JSON file. Returns None on parse error."""
    try:
        with open(json_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return PlanReadResult.model_validate(raw)
    except Exception as exc:
        print(f"    [SKIP] Cannot parse {json_path.name}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_currency(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


def _confidence_label(estimate) -> str:
    """Return a short confidence label from the ProjectEstimate."""
    # Try to get overall confidence from the estimate
    confidence: float | None = None

    if hasattr(estimate, "scope_estimates") and estimate.scope_estimates:
        scores = [s.confidence for s in estimate.scope_estimates if s.confidence is not None]
        if scores:
            confidence = sum(scores) / len(scores)
    elif hasattr(estimate, "extraction_confidence"):
        confidence = estimate.extraction_confidence

    if confidence is None:
        return "UNKNOWN"

    if CONFIDENCE_AVAILABLE:
        return format_confidence_badge(confidence)
    else:
        if confidence >= 0.75:
            return "HIGH"
        elif confidence >= 0.50:
            return "MED"
        else:
            return "LOW"


def _avg_confidence(estimates: list) -> float:
    """Compute average scope-level confidence across all project estimates."""
    all_scores: list[float] = []
    for est in estimates:
        if hasattr(est, "scope_estimates"):
            for s in est.scope_estimates:
                if s.confidence is not None:
                    all_scores.append(s.confidence)
    if not all_scores:
        return 0.0
    return sum(all_scores) / len(all_scores)


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------


def run_dry_run(
    plans_dir: Path,
    limit: int | None,
    project_filter: str | None,
) -> None:
    """List plan JSON files that would be estimated, without running estimation."""
    files = find_plan_jsons(plans_dir, project_filter)
    total_found = len(files)
    if limit:
        files = files[:limit]

    print(f"Plan JSON files found: {total_found}")
    if project_filter:
        print(f"(filtered to project: '{project_filter}')")
    if limit and limit < total_found:
        print(f"(showing first {limit} of {total_found})")
    print()

    for i, (json_path, project_name) in enumerate(files, 1):
        size_kb = json_path.stat().st_size / 1024
        print(f"  {i:3d}. {project_name}/{json_path.name}  [{size_kb:.1f} KB]")

    print(f"\nTotal: {len(files)} files")


def run_batch(
    plans_dir: Path,
    output_base: Path,
    limit: int | None,
    project_filter: str | None,
    export_excel: bool = False,
    skip_existing: bool = False,
) -> None:
    """Run estimation on all discovered plan JSON files."""
    if not ESTIMATOR_AVAILABLE:
        print(
            f"ERROR: src.estimation.estimator could not be imported:\n  {_ESTIMATOR_ERR}\n"
            "Ensure all Phase 5 modules are present and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    if export_excel and not EXCEL_WRITER_AVAILABLE:
        print(
            f"WARNING: src.estimation.excel_writer not available:\n  {_EXCEL_WRITER_ERR}\n"
            "--export-excel will be skipped.",
            file=sys.stderr,
        )

    files = find_plan_jsons(plans_dir, project_filter)
    if limit:
        files = files[:limit]

    if not files:
        print("No plan JSON files found matching the current filters.", file=sys.stderr)
        sys.exit(1)

    total = len(files)
    print(f"Estimating {total} plan JSON(s)...")
    print(f"Input:  {plans_dir}")
    print(f"Output: {output_base}\n")

    ok_count = 0
    fail_count = 0
    skip_count = 0
    total_scopes = 0
    grand_total: Decimal = Decimal("0")
    all_estimates: list = []
    start = time.monotonic()

    for idx, (json_path, project_name) in enumerate(files, 1):
        output_dir = output_base / project_name
        stem = json_path.stem
        output_json = output_dir / f"{stem}_estimate.json"

        if skip_existing and output_json.exists():
            print(f"  [{idx}/{total}] [SKIP] {project_name}/{json_path.name}")
            skip_count += 1
            continue

        # Load the plan result
        plan_result = load_plan_result(json_path)
        if plan_result is None:
            fail_count += 1
            continue

        # Run estimation
        try:
            t0 = time.monotonic()
            estimate = estimate_from_plan_result(plan_result)
            elapsed = time.monotonic() - t0

            # Save JSON estimate
            output_dir.mkdir(parents=True, exist_ok=True)
            output_json.write_text(_to_json(estimate), encoding="utf-8")

            # Optionally write Excel
            if export_excel and EXCEL_WRITER_AVAILABLE:
                excel_path = output_dir / f"{stem}_estimate.xlsx"
                try:
                    write_estimate_to_excel(estimate, excel_path)
                    excel_note = f"  xlsx → {excel_path.name}"
                except Exception as exc_xl:
                    excel_note = f"  [XLSX FAIL] {exc_xl}"
            else:
                excel_note = ""

            n_scopes = len(estimate.scope_estimates) if hasattr(estimate, "scope_estimates") else 0
            total_cost = getattr(estimate, "total_estimated_cost", None)
            conf_label = _confidence_label(estimate)

            total_scopes += n_scopes
            if total_cost is not None:
                grand_total += Decimal(str(total_cost))
            all_estimates.append(estimate)
            ok_count += 1

            print(
                f"  [{idx}/{total}] [OK] {project_name} "
                f"→ {n_scopes} scopes, {_fmt_currency(total_cost)} total "
                f"(confidence: {conf_label})  ({elapsed:.1f}s)" + (f"\n{excel_note}" if excel_note else "")
            )

        except Exception as exc:
            fail_count += 1
            print(
                f"  [{idx}/{total}] [FAIL] {project_name}/{json_path.name}: {exc}",
                file=sys.stderr,
            )

    elapsed_total = time.monotonic() - start
    processed = ok_count + fail_count
    success_rate = (ok_count / processed * 100) if processed > 0 else 0.0
    avg_conf = _avg_confidence(all_estimates)

    print("\n" + "=" * 65)
    print("ESTIMATION SUMMARY")
    print("=" * 65)
    print(f"  Plan JSONs found:     {total}")
    print(f"  Estimated:            {ok_count}  ({success_rate:.0f}%)")
    print(f"  Failed:               {fail_count}")
    if skip_count:
        print(f"  Skipped (existing):  {skip_count}")
    print(f"  Total scope items:    {total_scopes}")
    print(f"  Total est. value:     {_fmt_currency(grand_total)}")
    print(f"  Avg confidence:       {avg_conf:.2%}")
    print(f"  Elapsed:              {elapsed_total:.1f}s")
    print("=" * 65)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch estimation — reads plan JSONs and produces cost estimates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project",
        metavar="NAME",
        help='Restrict to project folders whose name contains NAME (e.g. "Seven Pines").',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List plan JSON files that would be estimated, without running estimation.",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Also write a .xlsx estimate file alongside each JSON estimate.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process only the first N plan JSON files.",
    )
    parser.add_argument(
        "--input",
        metavar="DIR",
        default=str(PLANS_DIR),
        help=f"Override input directory (default: {PLANS_DIR}).",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default=str(ESTIMATES_DIR),
        help=f"Override output directory (default: {ESTIMATES_DIR}).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip plan JSONs that already have a corresponding estimate JSON.",
    )
    args = parser.parse_args()

    plans_dir = Path(args.input)
    output_base = Path(args.output)

    if not plans_dir.exists():
        print(f"Error: input plans directory not found: {plans_dir}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        run_dry_run(plans_dir, args.limit, args.project)
    else:
        run_batch(
            plans_dir=plans_dir,
            output_base=output_base,
            limit=args.limit,
            project_filter=args.project,
            export_excel=args.export_excel,
            skip_existing=args.skip_existing,
        )


if __name__ == "__main__":
    main()
