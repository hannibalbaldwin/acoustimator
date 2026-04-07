"""Batch runner for the quote PDF parser.

Walks a source directory tree, extracts all Commercial Acoustics quote PDFs
(files named "Quote *.pdf"), saves each result as a JSON file under
data/extracted/quotes/, and prints a summary report.

Usage:
    uv run python scripts/parse_quotes.py --source "/path/to/+ITBs"
    uv run python scripts/parse_quotes.py --source "/path/to/+ITBs" --verbose
    uv run python scripts/parse_quotes.py --source "/path/to/+ITBs" --limit 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow imports from repo root (handles running via `uv run python scripts/...`)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.extraction.pdf_parser import extract_quote, find_quote_files  # noqa: E402

# ---------------------------------------------------------------------------
# Output directory (relative to repo root)
# ---------------------------------------------------------------------------
OUTPUT_DIR = REPO_ROOT / "data" / "extracted" / "quotes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_serialiser(obj: object) -> str:
    """JSON serialiser for Decimal values (json.dumps default hook)."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


def _safe_stem(path: Path) -> str:
    """Return a filesystem-safe version of a file stem (replace problematic chars)."""
    return path.stem.replace("/", "_").replace("\\", "_").replace(":", "_")


def _save_result(result_dict: dict, source_path: Path, output_dir: Path) -> Path:
    """Save extraction result as JSON; return the output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_name = _safe_stem(source_path) + ".json"
    out_path = output_dir / out_name
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result_dict, fh, indent=2, default=_decimal_serialiser)
    return out_path


def _result_to_dict(result) -> dict:  # QuoteExtractionResult
    """Convert a QuoteExtractionResult to a plain dict (JSON-serialisable)."""
    if result.quote is not None:
        quote_dict = result.quote.model_dump()
        # Convert Decimal line-item fields
        items_out = []
        for item in quote_dict.get("line_items", []):
            items_out.append(item)
        quote_dict["line_items"] = items_out
        return {"success": result.success, "quote": quote_dict, "error": result.error}
    return {"success": result.success, "quote": None, "error": result.error}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(source_dir: Path, output_dir: Path, limit: int | None, verbose: bool) -> None:
    """Core batch extraction logic."""

    # -------------------------------------------------------------- discover
    print(f"\nScanning for quote PDFs in:\n  {source_dir}\n")
    pairs = find_quote_files(source_dir)

    if not pairs:
        print("No quote PDFs found.  Check that --source points to the +ITBs folder.")
        sys.exit(1)

    total_found = len(pairs)
    print(f"Found {total_found} quote PDFs.")

    if limit:
        pairs = pairs[:limit]
        print(f"Limiting run to {limit} files (--limit flag).\n")

    # ------------------------------------------------------------- extraction
    successes: list[tuple[Path, dict]] = []
    failures: list[tuple[Path, str]] = []
    has_quote_number: int = 0
    has_grand_total: int = 0
    total_processed = len(pairs)

    t0 = time.perf_counter()

    for i, (pdf_path, folder_name) in enumerate(pairs, 1):
        prefix = f"[{i:3d}/{total_processed}]"
        if verbose:
            print(f"{prefix} {pdf_path.name} ({folder_name})")

        result = extract_quote(pdf_path)
        result_dict = _result_to_dict(result)

        _save_result(result_dict, pdf_path, output_dir)

        if result.success and result.quote is not None:
            q = result.quote
            if q.quote_number:
                has_quote_number += 1
            if q.grand_total is not None:
                has_grand_total += 1

            successes.append((pdf_path, result_dict))

            if verbose:
                print(
                    f"        OK  quote={q.quote_number or 'NONE':>10}  "
                    f"template={q.template_type or 'NONE':>6}  "
                    f"total={str(q.grand_total) if q.grand_total else 'NONE':>12}  "
                    f"conf={q.extraction_confidence:.2f}"
                )
        else:
            err = result.error or "unknown error"
            failures.append((pdf_path, err))
            if verbose:
                print(f"        FAIL  {err}")

    elapsed = time.perf_counter() - t0

    # ---------------------------------------------------------------- summary
    n_ok = len(successes)
    n_fail = len(failures)
    success_rate = n_ok / total_processed * 100 if total_processed else 0.0
    qnum_rate = has_quote_number / total_processed * 100 if total_processed else 0.0
    total_rate = has_grand_total / total_processed * 100 if total_processed else 0.0

    print("\n" + "=" * 70)
    print("QUOTE EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"  Source directory : {source_dir}")
    print(f"  Output directory : {output_dir}")
    print(f"  PDFs found       : {total_found:>5}")
    print(f"  PDFs processed   : {total_processed:>5}")
    print(f"  Successful       : {n_ok:>5}  ({success_rate:.1f}%)")
    print(f"  Failed           : {n_fail:>5}  ({100 - success_rate:.1f}%)")
    print(f"  Quote number     : {has_quote_number:>5}  ({qnum_rate:.1f}% of processed)")
    print(f"  Grand total      : {has_grand_total:>5}  ({total_rate:.1f}% of processed)")
    print(f"  Elapsed          : {elapsed:.1f}s  ({elapsed / total_processed:.2f}s/file)")

    # Acceptance-criteria callout
    target = 95.0
    qnum_pass = "PASS" if qnum_rate >= target else "FAIL"
    total_pass = "PASS" if total_rate >= target else "FAIL"
    print(f"\n  Acceptance criteria (>= {target:.0f}% extraction rate):")
    print(f"    Quote number : {qnum_rate:5.1f}%  [{qnum_pass}]")
    print(f"    Grand total  : {total_rate:5.1f}%  [{total_pass}]")

    # ----------------------------------------------------------- sample output
    print("\n" + "-" * 70)
    print("SAMPLE EXTRACTIONS (first 5 successful)")
    print("-" * 70)
    for pdf_path, rd in successes[:5]:
        q = rd.get("quote") or {}
        print(
            f"  {pdf_path.name}\n"
            f"    quote_number : {q.get('quote_number')}\n"
            f"    template     : {q.get('template_type')}\n"
            f"    client       : {q.get('client_name')}\n"
            f"    grand_total  : {q.get('grand_total')}\n"
            f"    date         : {q.get('quote_date')}\n"
            f"    payment_terms: {q.get('payment_terms')}\n"
            f"    line_items   : {len(q.get('line_items', []))}\n"
            f"    confidence   : {q.get('extraction_confidence')}\n"
        )

    # ----------------------------------------------------------- failure list
    if failures:
        print("-" * 70)
        print(f"FAILURES ({len(failures)})")
        print("-" * 70)
        for pdf_path, err in failures[:20]:
            print(f"  {pdf_path.name}: {err}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more (see JSON files for details)")

    print("=" * 70 + "\n")

    # Exit with non-zero if acceptance criteria not met (both must pass)
    if qnum_pass == "FAIL" or total_pass == "FAIL":
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-extract Commercial Acoustics quote PDFs and save as JSON."
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Root directory to search for quote PDFs (the +ITBs folder).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory for JSON output files (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N quote PDFs (useful for smoke-tests).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file extraction details.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level (default: WARNING).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    source_dir = args.source.expanduser().resolve()
    if not source_dir.is_dir():
        print(f"ERROR: source directory does not exist: {source_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output.expanduser().resolve()

    run(
        source_dir=source_dir,
        output_dir=output_dir,
        limit=args.limit,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
