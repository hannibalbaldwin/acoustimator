"""Data Quality Dashboard — Phase 2.5

Queries the Neon PostgreSQL dev branch and local extracted JSON files to
produce a comprehensive health report of the Acoustimator dataset.

Usage:
    uv run python scripts/quality_report.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import func, select, text

from src.db.session import async_session

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"
QUOTES_DIR = EXTRACTED_DIR / "quotes"
REPORT_OUTPUT = EXTRACTED_DIR / "quality_report.txt"

console = Console(record=True)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def fetch_scalar(session, stmt):
    result = await session.execute(stmt)
    return result.scalar()


async def fetch_all(session, stmt):
    result = await session.execute(stmt)
    return result.fetchall()


# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------


def pct(n: int | float, d: int | float) -> str:
    if d == 0:
        return "N/A"
    return f"{n / d * 100:.1f}%"


def fmt_num(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.4f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)


def fmt_money(v) -> str:
    if v is None:
        return "—"
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_extracted_buildups() -> list[dict]:
    """Load all buildup extraction JSON files (not quotes).

    Skips any JSON files that are lists or don't look like extraction results.
    """
    results = []
    for f in EXTRACTED_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            # Only include dicts that look like extraction results
            if isinstance(data, dict) and "success" in data:
                results.append(data)
        except Exception:
            pass
    return results


def load_extracted_quotes() -> list[dict]:
    """Load all quote PDF extraction JSON files."""
    results = []
    for f in QUOTES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            results.append(data)
        except Exception:
            pass
    return results


# ---------------------------------------------------------------------------
# Main report
# ---------------------------------------------------------------------------


async def build_report() -> None:
    console.print(
        Panel(
            f"[bold white]Acoustimator Data Quality Dashboard[/bold white]\n"
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC",
            border_style="bright_blue",
            expand=True,
        )
    )

    async with async_session() as session:
        # ===================================================================
        # SECTION 1: Dataset Overview
        # ===================================================================
        console.print("\n[bold bright_cyan]━━━ SECTION 1: Dataset Overview ━━━[/bold bright_cyan]")

        # Counts
        total_projects = await fetch_scalar(
            session, select(func.count()).select_from(text("projects"))
        )
        total_scopes = await fetch_scalar(session, select(func.count()).select_from(text("scopes")))
        total_addl_costs = await fetch_scalar(
            session, select(func.count()).select_from(text("additional_costs"))
        )

        try:
            total_vendor_quotes = await fetch_scalar(
                session, select(func.count()).select_from(text("vendor_quotes"))
            )
        except Exception:
            total_vendor_quotes = 0

        try:
            total_products = await fetch_scalar(
                session, select(func.count()).select_from(text("products"))
            )
        except Exception:
            total_products = 0

        try:
            scopes_with_product = await fetch_scalar(
                session, text("SELECT COUNT(*) FROM scopes WHERE product_id IS NOT NULL")
            )
        except Exception:
            scopes_with_product = 0

        overview_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
        overview_table.add_column("Metric", style="bold")
        overview_table.add_column("Value", justify="right", style="bright_white")
        overview_table.add_row("Projects in DB", str(total_projects or 0))
        overview_table.add_row("Scopes in DB", str(total_scopes or 0))
        overview_table.add_row("Additional Costs in DB", str(total_addl_costs or 0))
        overview_table.add_row("Vendor Quotes in DB", str(total_vendor_quotes or 0))
        overview_table.add_row("Products in Catalog", str(total_products or 0))
        overview_table.add_row(
            "Scopes Linked to Product",
            f"{scopes_with_product or 0} ({pct(scopes_with_product or 0, total_scopes or 1)})",
        )
        console.print(overview_table)

        # Projects by status
        try:
            status_rows = await fetch_all(
                session,
                text(
                    "SELECT status, COUNT(*) as cnt FROM projects GROUP BY status ORDER BY cnt DESC"
                ),
            )
        except Exception:
            status_rows = []

        if status_rows:
            status_table = Table(title="Projects by Status", box=box.SIMPLE_HEAD)
            status_table.add_column("Status", style="bold")
            status_table.add_column("Count", justify="right")
            status_table.add_column("Pct", justify="right")
            for row in status_rows:
                status_table.add_row(
                    str(row[0] or "NULL"), str(row[1]), pct(row[1], total_projects or 1)
                )
            console.print(status_table)

        # Date range
        try:
            date_row = await fetch_all(
                session,
                text(
                    "SELECT MIN(quote_date), MAX(quote_date) FROM projects WHERE quote_date IS NOT NULL"
                ),
            )
            if date_row and date_row[0][0]:
                console.print(
                    f"  [dim]Quote date range:[/dim] [green]{date_row[0][0]}[/green] → [green]{date_row[0][1]}[/green]"
                )
        except Exception:
            pass

        # ===================================================================
        # SECTION 2: Scope Type Distribution
        # ===================================================================
        console.print(
            "\n[bold bright_cyan]━━━ SECTION 2: Scope Type Distribution ━━━[/bold bright_cyan]"
        )

        try:
            scope_dist_rows = await fetch_all(
                session,
                text("""
                    SELECT
                        scope_type,
                        COUNT(*) as cnt,
                        AVG(cost_per_unit) as avg_cpu,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cost_per_unit) as med_cpu,
                        MIN(cost_per_unit) as min_cpu,
                        MAX(cost_per_unit) as max_cpu,
                        AVG(markup_pct) as avg_mkp,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY markup_pct) as med_mkp
                    FROM scopes
                    GROUP BY scope_type
                    ORDER BY cnt DESC
                """),
            )
        except Exception:
            scope_dist_rows = []

        if scope_dist_rows:
            dist_table = Table(title="Scope Type Distribution", box=box.SIMPLE_HEAD)
            dist_table.add_column("Scope Type", style="bold")
            dist_table.add_column("Count", justify="right")
            dist_table.add_column("Pct", justify="right")
            dist_table.add_column("Avg $/SF", justify="right")
            dist_table.add_column("Median $/SF", justify="right")
            dist_table.add_column("Min $/SF", justify="right")
            dist_table.add_column("Max $/SF", justify="right")
            dist_table.add_column("Avg Markup", justify="right")
            dist_table.add_column("Med Markup", justify="right")

            for row in scope_dist_rows:
                stype, cnt, avg_cpu, med_cpu, min_cpu, max_cpu, avg_mkp, med_mkp = row
                dist_table.add_row(
                    str(stype or "NULL"),
                    str(cnt),
                    pct(cnt, total_scopes or 1),
                    fmt_money(avg_cpu),
                    fmt_money(med_cpu),
                    fmt_money(min_cpu),
                    fmt_money(max_cpu),
                    f"{float(avg_mkp) * 100:.1f}%" if avg_mkp is not None else "—",
                    f"{float(med_mkp) * 100:.1f}%" if med_mkp is not None else "—",
                )
            console.print(dist_table)

        # ===================================================================
        # SECTION 3: Extraction Quality
        # ===================================================================
        console.print(
            "\n[bold bright_cyan]━━━ SECTION 3: Extraction Quality ━━━[/bold bright_cyan]"
        )

        try:
            quality_rows = await fetch_all(
                session,
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(cost_per_unit) FILTER (WHERE cost_per_unit IS NOT NULL) as has_cpu,
                        COUNT(square_footage) FILTER (WHERE square_footage IS NOT NULL AND square_footage > 0) as has_sf,
                        COUNT(product_name) FILTER (WHERE product_name IS NOT NULL AND product_name != '') as has_product_name,
                        COUNT(man_days) FILTER (WHERE man_days IS NOT NULL AND man_days > 0) as has_man_days,
                        COUNT(markup_pct) FILTER (WHERE markup_pct IS NOT NULL) as has_markup,
                        COUNT(product_id) FILTER (WHERE product_id IS NOT NULL) as has_product_id
                    FROM scopes
                """),
            )
        except Exception:
            quality_rows = []

        if quality_rows and quality_rows[0][0]:
            total, has_cpu, has_sf, has_pn, has_md, has_mkp, has_pid = quality_rows[0]
            total = total or 1

            q_table = Table(title="Scope Field Population", box=box.SIMPLE_HEAD)
            q_table.add_column("Field", style="bold")
            q_table.add_column("Populated", justify="right")
            q_table.add_column("Pct", justify="right")
            q_table.add_column("Missing", justify="right")

            fields = [
                ("cost_per_unit ($/SF)", has_cpu),
                ("square_footage", has_sf),
                ("product_name", has_pn),
                ("man_days", has_md),
                ("markup_pct", has_mkp),
                ("product_id (normalized)", has_pid),
            ]
            for fname, n in fields:
                color = "green" if (n / total) >= 0.8 else "yellow" if (n / total) >= 0.5 else "red"
                q_table.add_row(
                    fname, str(n), f"[{color}]{pct(n, total)}[/{color}]", str(total - n)
                )
            console.print(q_table)

        # ===================================================================
        # SECTION 4: Validation Issues
        # ===================================================================
        console.print("\n[bold bright_cyan]━━━ SECTION 4: Validation Issues ━━━[/bold bright_cyan]")

        buildups = load_extracted_buildups()
        total_extracted = len(buildups)
        success_count = sum(1 for b in buildups if b.get("success"))
        failed_count = total_extracted - success_count

        console.print(
            f"  Buildup JSON files on disk: [bold]{total_extracted}[/bold] "
            f"([green]{success_count} success[/green], [red]{failed_count} failed[/red])"
        )

        # Analyze issues from JSON files
        no_issues_count = 0
        warn_only_count = 0
        error_count_proj = 0
        issue_type_counter: Counter = Counter()
        high_markup_projects: list[str] = []

        for b in buildups:
            if not b.get("success") or not b.get("project"):
                continue
            proj = b["project"]
            scopes = proj.get("scopes", [])
            proj_name = proj.get("project_name", "Unknown")

            has_error = False
            has_warn = False

            for scope in scopes:
                markup = scope.get("markup_pct")
                if markup is not None:
                    try:
                        mp = float(markup)
                        if mp > 1.0:
                            high_markup_projects.append(
                                f"{proj_name} / {scope.get('tag', '?')} ({mp * 100:.0f}%)"
                            )
                        if mp < 0.10 or mp > 1.00:
                            has_error = True
                            issue_type_counter["markup_pct:out_of_range:error"] += 1
                        elif mp < 0.15 or mp > 0.75:
                            has_warn = True
                            issue_type_counter["markup_pct:out_of_range:warning"] += 1
                    except Exception:
                        pass

                sf = scope.get("square_footage")
                stype = scope.get("scope_type", "")
                if stype in ("ACT", "AWP", "AP", "FW", "WW", "RPG"):
                    if not sf or float(sf) <= 0:
                        has_error = True
                        issue_type_counter["square_footage:missing_required:error"] += 1

                if scope.get("total") is not None and float(scope.get("total", 0)) <= 0:
                    has_error = True
                    issue_type_counter["total:out_of_range:error"] += 1

                if (
                    scope.get("labor_price")
                    and float(scope["labor_price"]) > 0
                    and not scope.get("man_days")
                ):
                    has_warn = True
                    issue_type_counter["man_days:missing_required:warning"] += 1

            if has_error:
                error_count_proj += 1
            elif has_warn:
                warn_only_count += 1
            else:
                no_issues_count += 1

        val_table = Table(title="Project Validation Summary (from JSON)", box=box.SIMPLE_HEAD)
        val_table.add_column("Category", style="bold")
        val_table.add_column("Count", justify="right")
        val_table.add_column("Pct", justify="right")
        val_table.add_row(
            "[green]No Issues[/green]",
            str(no_issues_count),
            pct(no_issues_count, success_count or 1),
        )
        val_table.add_row(
            "[yellow]Warnings Only[/yellow]",
            str(warn_only_count),
            pct(warn_only_count, success_count or 1),
        )
        val_table.add_row(
            "[red]Has Errors[/red]",
            str(error_count_proj),
            pct(error_count_proj, success_count or 1),
        )
        console.print(val_table)

        if issue_type_counter:
            top_issues_table = Table(title="Top 5 Most Common Issue Types", box=box.SIMPLE_HEAD)
            top_issues_table.add_column("Issue Key (field:type:severity)", style="dim")
            top_issues_table.add_column("Count", justify="right")
            for issue_key, cnt in issue_type_counter.most_common(5):
                parts = issue_key.split(":")
                sev = parts[2] if len(parts) >= 3 else ""
                color = "red" if sev == "error" else "yellow"
                top_issues_table.add_row(f"[{color}]{issue_key}[/{color}]", str(cnt))
            console.print(top_issues_table)

        if high_markup_projects:
            console.print(
                f"\n  [bold yellow]High Markup (>100%) — {len(high_markup_projects)} scope(s) flagged:[/bold yellow]"
            )
            for item in high_markup_projects[:10]:
                console.print(f"    [yellow]• {item}[/yellow]")
            if len(high_markup_projects) > 10:
                console.print(f"    [dim]... and {len(high_markup_projects) - 10} more[/dim]")

        # ===================================================================
        # SECTION 5: Quote PDF Coverage
        # ===================================================================
        console.print(
            "\n[bold bright_cyan]━━━ SECTION 5: Quote PDF Coverage ━━━[/bold bright_cyan]"
        )

        quotes = load_extracted_quotes()
        total_quote_files = len(quotes)
        quote_success = sum(1 for q in quotes if q.get("success"))
        quote_with_number = sum(
            1
            for q in quotes
            if q.get("success") and q.get("quote") and q["quote"].get("quote_number")
        )
        quote_with_total = sum(
            1
            for q in quotes
            if q.get("success") and q.get("quote") and q["quote"].get("grand_total")
        )

        # Build a set of project names from buildup extractions
        buildup_project_names: set[str] = set()
        for b in buildups:
            if b.get("success") and b.get("project"):
                pname = b["project"].get("project_name", "").strip().lower()
                if pname:
                    buildup_project_names.add(pname)

        # Check cross-reference: which quote client names match buildup project names
        matched_quotes = 0
        for q in quotes:
            if not q.get("success") or not q.get("quote"):
                continue
            client = (q["quote"].get("client_name") or "").strip().lower()
            if any(client in pname or pname in client for pname in buildup_project_names):
                matched_quotes += 1

        quote_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
        quote_table.add_column("Metric", style="bold")
        quote_table.add_column("Value", justify="right", style="bright_white")
        quote_table.add_row("Quote PDFs extracted", str(total_quote_files))
        quote_table.add_row(
            "Successfully parsed", f"{quote_success} ({pct(quote_success, total_quote_files or 1)})"
        )
        quote_table.add_row(
            "Quote numbers found",
            f"{quote_with_number} ({pct(quote_with_number, quote_success or 1)})",
        )
        quote_table.add_row(
            "Grand totals found",
            f"{quote_with_total} ({pct(quote_with_total, quote_success or 1)})",
        )
        quote_table.add_row("Cross-ref: quotes matched to buildup project", f"~{matched_quotes}")
        console.print(quote_table)

        # Template type breakdown
        template_counter: Counter = Counter()
        for q in quotes:
            if q.get("success") and q.get("quote"):
                t = q["quote"].get("template_type") or "Unknown"
                template_counter[t] += 1

        if template_counter:
            tmpl_table = Table(title="Quote Template Types", box=box.SIMPLE_HEAD)
            tmpl_table.add_column("Template", style="bold")
            tmpl_table.add_column("Count", justify="right")
            for t, cnt in template_counter.most_common():
                tmpl_table.add_row(str(t), str(cnt))
            console.print(tmpl_table)

        # ===================================================================
        # SECTION 6: Vendor Data
        # ===================================================================
        console.print("\n[bold bright_cyan]━━━ SECTION 6: Vendor Data ━━━[/bold bright_cyan]")

        try:
            vq_rows = await fetch_all(
                session,
                text("""
                    SELECT v.name, COUNT(vq.id) as quote_count, SUM(vq.total) as total_value
                    FROM vendor_quotes vq
                    LEFT JOIN vendors v ON vq.vendor_id = v.id
                    GROUP BY v.name
                    ORDER BY quote_count DESC
                """),
            )
        except Exception:
            vq_rows = []

        try:
            products_with_pricing = await fetch_scalar(
                session,
                text("""
                    SELECT COUNT(*) FROM products
                    WHERE typical_cost_per_sf IS NOT NULL OR typical_cost_per_lf IS NOT NULL
                """),
            )
        except Exception:
            products_with_pricing = 0

        vendor_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
        vendor_table.add_column("Metric", style="bold")
        vendor_table.add_column("Value", justify="right", style="bright_white")
        vendor_table.add_row("Total vendor quotes loaded", str(total_vendor_quotes or 0))
        vendor_table.add_row("Products in catalog", str(total_products or 0))
        vendor_table.add_row("Products with pricing data", str(products_with_pricing or 0))
        console.print(vendor_table)

        if vq_rows:
            vq_table = Table(title="Vendor Quote Breakdown", box=box.SIMPLE_HEAD)
            vq_table.add_column("Vendor", style="bold")
            vq_table.add_column("Quotes", justify="right")
            vq_table.add_column("Total Value", justify="right")
            for row in vq_rows:
                vq_table.add_row(str(row[0] or "Unknown"), str(row[1]), fmt_money(row[2]))
            console.print(vq_table)
        else:
            console.print("  [dim]No vendor quotes loaded yet.[/dim]")

        # ===================================================================
        # SECTION 7: ML Readiness
        # ===================================================================
        console.print(
            "\n[bold bright_cyan]━━━ SECTION 7: ML Readiness (Phase 3) ━━━[/bold bright_cyan]"
        )

        try:
            ml_rows = await fetch_all(
                session,
                text("""
                    SELECT
                        scope_type,
                        COUNT(*) as total,
                        COUNT(*) FILTER (
                            WHERE scope_type IS NOT NULL
                              AND cost_per_unit IS NOT NULL
                              AND square_footage IS NOT NULL AND square_footage > 0
                              AND markup_pct IS NOT NULL
                        ) as ml_ready
                    FROM scopes
                    GROUP BY scope_type
                    ORDER BY ml_ready DESC
                """),
            )
        except Exception:
            ml_rows = []

        total_ml_ready = 0
        total_ml_total = total_scopes or 0

        if ml_rows:
            ml_table = Table(
                title="ML Readiness per Scope Type (need: scope_type + cost_per_unit + SF + markup)",
                box=box.SIMPLE_HEAD,
            )
            ml_table.add_column("Scope Type", style="bold")
            ml_table.add_column("Total Rows", justify="right")
            ml_table.add_column("ML-Ready", justify="right")
            ml_table.add_column("Pct Ready", justify="right")
            ml_table.add_column("Can Train (>20)?", justify="center")

            for row in ml_rows:
                stype, total_r, ml_ready_r = row
                total_ml_ready += ml_ready_r or 0
                can_train = "[green]YES[/green]" if (ml_ready_r or 0) > 20 else "[red]NO[/red]"
                readiness_pct = pct(ml_ready_r or 0, total_r or 1)
                color = (
                    "green"
                    if (ml_ready_r or 0) > 20
                    else "yellow"
                    if (ml_ready_r or 0) >= 5
                    else "red"
                )
                ml_table.add_row(
                    str(stype or "NULL"),
                    str(total_r),
                    f"[{color}]{ml_ready_r or 0}[/{color}]",
                    readiness_pct,
                    can_train,
                )
            console.print(ml_table)

        console.print(
            f"\n  Overall ML-ready scopes: [bold]{total_ml_ready}[/bold] / {total_ml_total} "
            f"([bright_white]{pct(total_ml_ready, total_ml_total or 1)}[/bright_white])"
        )

        # Recommendation panel
        try:
            trainable = (
                [str(row[0]) for row in ml_rows if row[0] and (row[2] or 0) > 20] if ml_rows else []
            )
        except Exception:
            trainable = []

        if trainable:
            rec_text = (
                f"[green]Scope types ready for ML model training:[/green] {', '.join(trainable)}\n"
                f"[dim]Minimum 20 complete rows (scope_type + cost_per_unit + SF + markup_pct) required.[/dim]"
            )
        else:
            rec_text = (
                "[yellow]No scope types have >20 complete ML feature rows yet.[/yellow]\n"
                "[dim]Continue loading extracted data to reach training threshold.[/dim]"
            )

        console.print(
            Panel(
                rec_text,
                title="[bold]Phase 3 Recommendation[/bold]",
                border_style="green" if trainable else "yellow",
            )
        )

    # ===================================================================
    # Footer
    # ===================================================================
    console.print(
        Panel(
            "[dim]Report complete. Data sourced from Neon PostgreSQL dev branch + local JSON extractions.[/dim]",
            border_style="dim",
        )
    )


async def main() -> None:
    await build_report()

    # Save report to file (strip ANSI codes)
    plain_text = console.export_text(clear=False)
    REPORT_OUTPUT.write_text(plain_text, encoding="utf-8")
    console.print(f"\n[dim]Report saved to:[/dim] [bold]{REPORT_OUTPUT}[/bold]")


if __name__ == "__main__":
    asyncio.run(main())
