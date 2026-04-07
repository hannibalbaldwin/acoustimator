#!/usr/bin/env python3
"""CLI runner that loads extracted JSON results into PostgreSQL.

Reads ExtractionResult JSON files produced by extract_all.py from
data/extracted/ (or a custom directory), deserialises them, and persists
them to the configured database via the loader module.

Usage:
    python scripts/load_to_db.py                     # Load all JSON from data/extracted/
    python scripts/load_to_db.py --input path/to/    # Custom input directory
    python scripts/load_to_db.py --dry-run           # Count files without loading
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so that `src` imports work when the
# script is run directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from src.extraction.excel_parser import ExtractionResult

console = Console()

DEFAULT_INPUT_DIR = Path("data/extracted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json_files(input_dir: Path) -> list[Path]:
    """Return all .json files found directly inside *input_dir*.

    Raises FileNotFoundError if the directory does not exist.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    return sorted(input_dir.glob("*.json"))


def deserialize_result(path: Path) -> ExtractionResult | None:
    """Deserialise a JSON file into an ExtractionResult.

    Returns None and logs a warning if the file cannot be parsed.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ExtractionResult.model_validate(raw)
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] Could not parse {path.name}: {exc}")
        return None


def print_summary(counts: dict[str, int], total_files: int, skipped_parse: int) -> None:
    """Print a Rich table summarising the load operation."""
    table = Table(title="Load Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total JSON files found", str(total_files))
    table.add_row("Parse errors (skipped)", str(skipped_parse))
    table.add_row("Successfully loaded", f"[green]{counts['success']}[/green]")
    table.add_row("Failed to load", f"[red]{counts['failed']}[/red]")
    table.add_row("Skipped (no project data)", str(counts.get("skipped", 0)))

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Async main
# ---------------------------------------------------------------------------


async def run(input_dir: Path, dry_run: bool) -> int:
    """Core async logic; returns an exit code (0 = success, 1 = errors)."""
    try:
        json_files = load_json_files(input_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        console.print("Create the directory or point --input at the correct location.")
        return 1

    if not json_files:
        console.print(f"[yellow]No JSON files found in {input_dir}[/yellow]")
        return 0

    console.print(f"Found [bold]{len(json_files)}[/bold] JSON file(s) in [cyan]{input_dir}[/cyan]")

    if dry_run:
        console.print("\n[bold]Dry-run mode — no data will be written.[/bold]\n")
        for path in json_files:
            console.print(f"  {path.name}")
        console.print(f"\nWould attempt to load {len(json_files)} file(s).")
        return 0

    # ------------------------------------------------------------------
    # Deserialise
    # ------------------------------------------------------------------
    results: list[ExtractionResult] = []
    skipped_parse = 0
    for path in json_files:
        result = deserialize_result(path)
        if result is not None:
            results.append(result)
        else:
            skipped_parse += 1

    console.print(
        f"Parsed [bold]{len(results)}[/bold] result(s) "
        f"([yellow]{skipped_parse}[/yellow] parse error(s))."
    )

    if not results:
        console.print("[yellow]Nothing to load.[/yellow]")
        return 0

    # ------------------------------------------------------------------
    # Load — import here so DB-connection errors surface with a good message
    # ------------------------------------------------------------------
    try:
        from sqlalchemy.exc import OperationalError

        from src.db.loader import get_project_count, get_scope_count, load_all_results
        from src.db.session import async_session
    except ImportError as exc:
        console.print(f"[red]Import error:[/red] {exc}")
        return 1

    try:
        counts = await load_all_results(results, show_progress=True)
    except OperationalError as exc:
        console.print("\n[red]Database connection error.[/red]")
        console.print(
            "Make sure DATABASE_URL is set in your .env file and the database is reachable."
        )
        console.print(f"\nDetail: {exc.orig}")
        return 1

    # ------------------------------------------------------------------
    # Post-load counts
    # ------------------------------------------------------------------
    try:
        async with async_session() as session:
            total_projects = await get_project_count(session)
            total_scopes = await get_scope_count(session)
        console.print(
            f"\nDatabase now contains [bold]{total_projects}[/bold] project(s) "
            f"and [bold]{total_scopes}[/bold] scope(s)."
        )
    except OperationalError:
        # Non-fatal — summary already printed
        pass

    print_summary(counts, len(json_files), skipped_parse)

    return 1 if counts["failed"] > 0 else 0


def main() -> None:
    """Parse CLI arguments and drive the async load pipeline."""
    parser = argparse.ArgumentParser(
        description="Load extracted JSON results into the Acoustimator PostgreSQL database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_INPUT_DIR),
        metavar="DIR",
        help=f"Directory containing extracted JSON files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be loaded without writing to the database",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run(Path(args.input), dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
