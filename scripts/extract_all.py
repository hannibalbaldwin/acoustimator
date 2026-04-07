#!/usr/bin/env python3
"""Batch extraction runner for all Commercial Acoustics buildups.

Usage:
    # Extract all buildups from configured source directory
    python scripts/extract_all.py

    # Extract a single file
    python scripts/extract_all.py --single path/to/buildup.xlsx

    # Dry run — list files without extracting
    python scripts/extract_all.py --dry-run

    # Limit to first N files with custom concurrency
    python scripts/extract_all.py --limit 10 --concurrency 3
"""

import argparse
import asyncio
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.extraction.excel_parser import (
    ExtractionResult,
    extract_buildup,
    find_buildup_files,
)

# Claude Sonnet pricing as of 2025: $3/MTok input, $15/MTok output
COST_PER_INPUT_TOKEN = Decimal("3.00") / Decimal("1_000_000")
COST_PER_OUTPUT_TOKEN = Decimal("15.00") / Decimal("1_000_000")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that serializes Decimal values as strings to preserve precision."""

    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def result_to_json(result: ExtractionResult) -> str:
    """Serialize an ExtractionResult to formatted JSON."""
    return json.dumps(result.model_dump(mode="json"), indent=2, cls=DecimalEncoder)


def derive_output_name(source_path: Path) -> str:
    """Derive a JSON output filename from the source file's parent folder name.

    For example:
        /data/raw/Grant Thornton/buildup.xlsx -> Grant Thornton.json
        /data/raw/++Archive/Old Project/buildup.xlsx -> Old Project.json
    """
    folder_name = source_path.parent.name
    # Fallback to the file stem if the folder is the root source dir
    if not folder_name or folder_name in ("raw", "data"):
        folder_name = source_path.stem
    return f"{folder_name}.json"


def estimate_cost(results: list[ExtractionResult]) -> tuple[int, Decimal]:
    """Calculate total tokens used and estimated API cost.

    Returns:
        Tuple of (total_tokens, estimated_cost_usd).
    """
    total_tokens = sum(r.tokens_used for r in results)
    # Approximate 80/20 input/output split for cost estimate
    estimated_input = int(total_tokens * 0.8)
    estimated_output = total_tokens - estimated_input
    cost = (
        Decimal(estimated_input) * COST_PER_INPUT_TOKEN
        + Decimal(estimated_output) * COST_PER_OUTPUT_TOKEN
    )
    return total_tokens, cost


def print_summary(
    results: list[ExtractionResult],
    elapsed_seconds: float,
) -> None:
    """Print a human-readable summary of the extraction batch."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    total_tokens, cost = estimate_cost(results)

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"  Total files processed:   {len(results)}")
    print(f"  Successful extractions:  {len(successful)}")
    print(f"  Failed extractions:      {len(failed)}")
    print(f"  Total tokens used:       {total_tokens:,}")
    print(f"  Estimated API cost:      ${cost:.4f}")
    print(f"  Elapsed time:            {elapsed_seconds:.1f}s")
    print("=" * 60)

    if failed:
        print("\nFailed files:")
        for result in failed:
            src = result.project.source_file if result.project else "unknown"
            print(f"  - {src}: {result.error}")


async def run_single(file_path: Path) -> None:
    """Extract a single buildup file and print the result."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    if not file_path.suffix.lower() == ".xlsx":
        print(f"Error: Expected .xlsx file, got: {file_path.suffix}", file=sys.stderr)
        sys.exit(1)

    folder_name = file_path.parent.name
    print(f"Extracting: {file_path}")
    result = await extract_buildup(file_path, folder_name)

    if result.success:
        print(result_to_json(result))
    else:
        print(f"Extraction failed: {result.error}", file=sys.stderr)
        sys.exit(1)


async def run_dry_run(source_dir: Path, limit: int | None) -> None:
    """List all .xlsx files that would be processed without extracting."""
    files = find_buildup_files(source_dir)
    if limit:
        files = files[:limit]

    print(f"Found {len(files)} buildup files in {source_dir}:\n")
    for i, (file_path, folder_name) in enumerate(files, 1):
        rel = (
            file_path.relative_to(source_dir) if file_path.is_relative_to(source_dir) else file_path
        )
        print(f"  {i:3d}. [{folder_name}] {rel.name}")

    print(f"\nTotal: {len(files)} files")


async def run_batch(
    source_dir: Path,
    output_dir: Path,
    concurrency: int,
    limit: int | None,
    skip_existing: bool = False,
) -> None:
    """Extract all buildups and save results as JSON files."""
    files = find_buildup_files(source_dir)
    if limit:
        files = files[:limit]

    if not files:
        print(f"No buildup files found in {source_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    if skip_existing:
        existing = {p.stem for p in output_dir.glob("*.json")}
        before = len(files)
        files = [(fp, fn) for fp, fn in files if fn not in existing]
        print(f"Skipping {before - len(files)} already-extracted files.")

    if not files:
        print("All files already extracted.")
        return

    total = len(files)
    print(f"Extracting {total} buildups (concurrency={concurrency}, delay=15s)...")
    print(f"Output directory: {output_dir}\n")

    semaphore = asyncio.Semaphore(concurrency)
    results: list[ExtractionResult] = []
    start_time = time.monotonic()

    async def _extract_and_save(idx: int, file_path: Path, folder_name: str) -> ExtractionResult:
        async with semaphore:
            result = await extract_buildup(file_path, folder_name)
            src = result.project.source_file if result.project else None
            output_name = derive_output_name(Path(src)) if src else f"{folder_name}.json"
            output_path = output_dir / output_name
            output_path.write_text(result_to_json(result), encoding="utf-8")
            status = "OK" if result.success else "FAIL"
            print(f"  [{idx}/{total}] [{status}] {output_name}", flush=True)
            # Pace requests: 15s delay keeps us under Tier 1 token rate limit
            await asyncio.sleep(15.0)
            return result

    tasks = [_extract_and_save(i + 1, fp, fn) for i, (fp, fn) in enumerate(files)]
    results = list(await asyncio.gather(*tasks))
    elapsed = time.monotonic() - start_time

    print_summary(results, elapsed)


async def main() -> None:
    """CLI entry point for the extraction pipeline."""
    parser = argparse.ArgumentParser(
        description="Extract data from Commercial Acoustics buildups",
    )
    parser.add_argument(
        "--single",
        type=str,
        help="Extract a single file (path to .xlsx)",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Source directory (default: DATA_SOURCE_PATH from .env)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/extracted",
        help="Output directory for JSON results (default: data/extracted)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent API calls (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files to process without extracting",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of files to process",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already have a JSON output in the output directory",
    )
    args = parser.parse_args()

    source_dir = Path(args.source) if args.source else settings.data_source_path
    output_dir = Path(args.output)

    if args.single:
        await run_single(Path(args.single))
    elif args.dry_run:
        await run_dry_run(source_dir, args.limit)
    else:
        await run_batch(
            source_dir, output_dir, args.concurrency, args.limit, skip_existing=args.skip_existing
        )


if __name__ == "__main__":
    asyncio.run(main())
