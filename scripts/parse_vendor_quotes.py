#!/usr/bin/env python3
"""Batch runner for vendor quote PDF extraction.

Walks the +ITBs Dropbox folder, finds all vendor quote PDFs using
the vendor_parser file-discovery logic, runs the two-pass extractor
(PyMuPDF text first, Claude Vision fallback), and saves each result
as a JSON file under data/extracted/vendor_quotes/.

Usage:
    # Dry-run — list files that would be processed without extracting
    uv run python scripts/parse_vendor_quotes.py --dry-run

    # Extract first 20 files (test run)
    uv run python scripts/parse_vendor_quotes.py --limit 20

    # Extract all files, skip already-extracted
    uv run python scripts/parse_vendor_quotes.py --skip-existing

    # Full run with custom concurrency
    uv run python scripts/parse_vendor_quotes.py --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path so relative imports work when run via uv run
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic

from src.config import settings
from src.extraction.vendor_parser import (
    VendorExtractionResult,
    extract_vendor_quote,
    find_vendor_quote_files,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard-coded Dropbox source — overridable via --source flag
_DEFAULT_SOURCE = Path("/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs")
_DEFAULT_OUTPUT = Path("data/extracted/vendor_quotes")

# Tier-1 Anthropic rate limit mitigation (30K input tokens/min)
# Vision fallbacks for a 3-page PDF at 2x scale can burn ~6-8K tokens each.
# Concurrency=2 + 15s between completions keeps us comfortably under limit.
CONCURRENCY = 2
REQUEST_DELAY_SECONDS = 15.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.WARNING,
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DecimalEncoder(json.JSONEncoder):
    """Serialize Decimal values as strings to preserve precision in JSON."""

    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def result_to_json(result: VendorExtractionResult) -> str:
    """Serialize a VendorExtractionResult to formatted JSON."""
    return json.dumps(result.model_dump(mode="json"), indent=2, cls=DecimalEncoder)


def derive_output_path(source_file: Path, output_dir: Path) -> Path:
    """Build the output JSON path for a given source PDF.

    Uses <project_folder>__<filename>.json so that quotes from different
    projects with the same filename don't collide.

    Example:
        source: /+ITBs/Grant Thornton/Vendor Quote - MDC.pdf
        output: data/extracted/vendor_quotes/Grant Thornton__Vendor Quote - MDC.json
    """
    folder = source_file.parent.name
    stem = source_file.stem
    safe_name = f"{folder}__{stem}.json"
    return output_dir / safe_name


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def run_dry_run(source_dir: Path, limit: int | None) -> None:
    """Print all vendor quote PDFs that would be processed."""
    all_files = find_vendor_quote_files(source_dir)
    if limit:
        all_files = all_files[:limit]

    print(f"\nDRY-RUN: {len(all_files)} vendor quote PDFs found in {source_dir}\n")
    for i, (path, vendor) in enumerate(all_files, 1):
        rel = path.relative_to(source_dir) if path.is_relative_to(source_dir) else path
        vendor_label = vendor or "unknown"
        print(f"  {i:4d}. [{vendor_label:25s}]  {rel}")

    # Vendor breakdown
    vendor_counts: Counter[str] = Counter(v or "unknown" for _, v in all_files)
    print(f"\nVendor breakdown ({len(all_files)} files):")
    for vendor, count in vendor_counts.most_common():
        print(f"  {vendor:30s}: {count:3d}")


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


def print_summary(
    results: list[tuple[Path, VendorExtractionResult]],
    elapsed_seconds: float,
    total_files: int,
) -> None:
    """Print a human-readable summary after batch extraction."""
    successful = [(p, r) for p, r in results if r.success]
    failed = [(p, r) for p, r in results if not r.success]

    total_tokens = sum(r.tokens_used for _, r in results)
    vision_calls = sum(1 for _, r in results if r.success and r.quote and r.quote.extraction_method == "vision")
    text_calls = sum(1 for _, r in results if r.success and r.quote and r.quote.extraction_method == "text")

    # Vendor breakdown for successful extractions
    vendor_counts: Counter[str] = Counter()
    for _, r in successful:
        if r.quote and r.quote.vendor_name:
            vendor_counts[r.quote.vendor_name] += 1
        else:
            vendor_counts["unknown"] += 1

    success_rate = len(successful) / len(results) * 100 if results else 0.0

    print("\n" + "=" * 65)
    print("VENDOR QUOTE EXTRACTION SUMMARY")
    print("=" * 65)
    print(f"  Files processed:         {len(results)} of {total_files}")
    print(f"  Successful:              {len(successful)}  ({success_rate:.0f}%)")
    print(f"  Failed:                  {len(failed)}")
    print("  Extraction method:")
    print(f"    Text (PyMuPDF):        {text_calls}")
    print(f"    Vision (Claude API):   {vision_calls}")
    print(f"  Total tokens used:       {total_tokens:,}")
    print(f"  Elapsed time:            {elapsed_seconds:.1f}s")
    print("=" * 65)

    if vendor_counts:
        print("\nVendor breakdown (from extracted content):")
        for vendor, count in vendor_counts.most_common():
            print(f"  {vendor:35s}: {count}")

    if failed:
        print(f"\nFailed files ({len(failed)}):")
        for path, r in failed:
            print(f"  - {path.parent.name}/{path.name}")
            print(f"      Error: {r.error}")

    print()


async def run_batch(
    source_dir: Path,
    output_dir: Path,
    concurrency: int,
    limit: int | None,
    skip_existing: bool,
) -> None:
    """Extract all vendor quote PDFs and save results as JSON."""
    all_files = find_vendor_quote_files(source_dir)

    if not all_files:
        print(f"No vendor quote PDFs found in {source_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    if skip_existing:
        existing_stems = {p.stem for p in output_dir.glob("*.json")}
        before = len(all_files)
        all_files = [(fp, v) for fp, v in all_files if derive_output_path(fp, output_dir).stem not in existing_stems]
        skipped = before - len(all_files)
        if skipped:
            print(f"Skipping {skipped} already-extracted files.")

    if limit:
        all_files = all_files[:limit]

    if not all_files:
        print("All files already extracted. Use --skip-existing=false to re-run.")
        return

    total = len(all_files)

    # Build Anthropic async client (Vision fallback uses it)
    api_key = settings.anthropic_api_key
    if not api_key:
        print(
            "WARNING: ANTHROPIC_API_KEY not set — Vision fallback disabled. "
            "Image-heavy PDFs will return low-confidence text results.",
            file=sys.stderr,
        )
        client = None
    else:
        client = anthropic.AsyncAnthropic(api_key=api_key)

    delay = REQUEST_DELAY_SECONDS
    print(f"Extracting {total} vendor quote PDFs (concurrency={concurrency}, delay={delay:.0f}s)...")
    print(f"Output directory: {output_dir}\n")

    semaphore = asyncio.Semaphore(concurrency)
    extracted: list[tuple[Path, VendorExtractionResult]] = []
    start_time = time.monotonic()

    async def _extract_and_save(
        idx: int,
        file_path: Path,
        vendor_hint: str,
    ) -> tuple[Path, VendorExtractionResult]:
        async with semaphore:
            result = await extract_vendor_quote(file_path, client)

            output_path = derive_output_path(file_path, output_dir)
            output_path.write_text(result_to_json(result), encoding="utf-8")

            status = "OK  " if result.success else "FAIL"
            method = ""
            confidence = ""
            if result.success and result.quote:
                method = f"[{result.quote.extraction_method:6s}]"
                confidence = f"conf={result.quote.extraction_confidence:.2f}"
            else:
                pass

            print(
                f"  [{idx:4d}/{total}] [{status}] {method} {confidence:10s}  {file_path.parent.name}/{file_path.name}",
                flush=True,
            )

            # Pace requests to stay within Tier-1 rate limit
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

            return file_path, result

    tasks = [_extract_and_save(i + 1, fp, v) for i, (fp, v) in enumerate(all_files)]
    extracted = list(await asyncio.gather(*tasks))
    elapsed = time.monotonic() - start_time

    print_summary(extracted, elapsed, total)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch vendor quote PDF extractor for Acoustimator",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help=f"Source directory to scan (default: {_DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(_DEFAULT_OUTPUT),
        help=f"Output directory for JSON results (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help=f"Max concurrent extractions (default: {CONCURRENCY}). Keep <=2 for Tier-1.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N files (useful for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files to process without extracting",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already have a JSON output in the output directory",
    )
    args = parser.parse_args()

    source_dir = Path(args.source) if args.source else _DEFAULT_SOURCE
    output_dir = Path(args.output)

    if not source_dir.is_dir():
        print(f"Error: Source directory does not exist: {source_dir}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        run_dry_run(source_dir, args.limit)
    else:
        await run_batch(
            source_dir=source_dir,
            output_dir=output_dir,
            concurrency=args.concurrency,
            limit=args.limit,
            skip_existing=args.skip_existing,
        )


if __name__ == "__main__":
    asyncio.run(main())
