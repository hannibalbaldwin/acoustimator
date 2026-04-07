"""Extraction validator for Acoustimator.

Validates extracted scope and project data from Excel buildups for internal
consistency, math accuracy, and outlier detection. Generates quality reports
for individual projects and full extraction batches.

Usage:
    from src.extraction.validator import validate_batch, print_validation_report

    report = validate_batch(results)
    print_validation_report(report)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from src.extraction.excel_parser import ExtractedProject, ExtractedScope, ExtractionResult

# ---------------------------------------------------------------------------
# Expected ranges per scope type
# ---------------------------------------------------------------------------

# (min_cost_per_sf, max_cost_per_sf) — None means "varies, no hard check"
# AP is excluded: it is not a canonical scope type and should not appear in new extractions.
COST_PER_SF_RANGES: dict[str, tuple[float, float] | None] = {
    "ACT": (1.57, 9.44),
    "AWP": (21.0, 34.0),
    "WW": (20.0, 45.0),
    "FW": (3.0, 5.0),
    "Baffles": None,
    "SM": None,
    "RPG": None,
    "Other": None,
}

# (min_markup, max_markup) as decimals — warning band
MARKUP_WARNING_RANGE = (0.15, 0.75)
# Hard error bounds
MARKUP_ERROR_RANGE = (0.10, 1.00)

# Tolerance for math consistency checks (2%)
MATH_TOLERANCE = 0.02


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    """A single validation finding for a scope or project."""

    field: str
    issue_type: str  # "out_of_range", "math_mismatch", "missing_required", "suspicious"
    severity: str  # "error", "warning", "info"
    expected: str | None
    actual: str | None
    message: str


class ScopeValidation(BaseModel):
    """Validation result for a single extracted scope."""

    scope_index: int
    tag: str | None
    scope_type: str
    issues: list[ValidationIssue]
    is_valid: bool  # True if no "error" severity issues


class ProjectValidation(BaseModel):
    """Validation result for a full extracted project."""

    project_name: str
    source_file: str
    scope_validations: list[ScopeValidation]
    project_issues: list[ValidationIssue]
    overall_valid: bool
    confidence_score: float  # 0.0–1.0
    summary: str


class BatchValidationReport(BaseModel):
    """Aggregate validation report for an entire extraction batch."""

    total_projects: int
    valid_projects: int
    projects_with_warnings: int
    projects_with_errors: int
    total_scopes: int
    valid_scopes: int
    common_issues: list[dict[str, Any]]
    project_validations: list[ProjectValidation]
    generated_at: str  # ISO datetime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ratio_diff(a: Decimal | float | None, b: Decimal | float | None) -> float | None:
    """Return |a - b| / max(|a|, |b|, 1) as a float, or None if either is missing."""
    if a is None or b is None:
        return None
    fa, fb = float(a), float(b)
    denom = max(abs(fa), abs(fb), 1.0)
    return abs(fa - fb) / denom


def _fmt_money(v: Decimal | None) -> str:
    """Format a Decimal as a dollar string for display."""
    if v is None:
        return "None"
    return f"${float(v):,.2f}"


def _fmt_pct(v: Decimal | None) -> str:
    """Format a Decimal fraction as a percentage string."""
    if v is None:
        return "None"
    return f"{float(v) * 100:.1f}%"


# ---------------------------------------------------------------------------
# Scope-level validation
# ---------------------------------------------------------------------------


def validate_scope(scope: ExtractedScope, scope_index: int) -> ScopeValidation:
    """Validate a single extracted scope for consistency and outliers.

    Performs the following checks:
    - SF > 0 for area-based scope types
    - markup_pct within acceptable range
    - cost_per_sf within expected range for the scope type
    - total > 0
    - sales_tax >= 0
    - Total math: total ≈ material_price + labor_price + sales_tax
    - Material price math: material_price ≈ material_cost × (1 + markup_pct)
    - Material cost math: material_cost ≈ sf × cost_per_sf
    - man_days present when labor_price is set

    Args:
        scope: The extracted scope to validate.
        scope_index: Zero-based index of this scope in the project's scope list.

    Returns:
        ScopeValidation with all issues found and an is_valid flag.
    """
    issues: list[ValidationIssue] = []
    stype = scope.scope_type

    # ------------------------------------------------------------------
    # 1. SF > 0 for area-based scope types
    #
    # Only require SF when the scope is priced per SF (cost_per_sf is set).
    # Unit-priced scopes (cost_per_sf is None) use quantity × unit_price
    # instead of SF, so SF is not required for them.
    # AP is no longer a canonical scope type — excluded from this check.
    # ------------------------------------------------------------------
    area_types = {"ACT", "AWP", "FW", "WW", "RPG"}
    is_unit_priced = scope.cost_per_sf is None
    if stype in area_types and not is_unit_priced:
        if scope.square_footage is None or scope.square_footage <= 0:
            issues.append(
                ValidationIssue(
                    field="square_footage",
                    issue_type="missing_required",
                    severity="error",
                    expected="SF > 0",
                    actual=str(scope.square_footage),
                    message=f"{stype} scope requires square_footage > 0 when priced per SF.",
                )
            )

    # ------------------------------------------------------------------
    # 2. markup_pct range checks
    # ------------------------------------------------------------------
    if scope.markup_pct is not None:
        mp = float(scope.markup_pct)
        lo_err, hi_err = MARKUP_ERROR_RANGE
        lo_warn, hi_warn = MARKUP_WARNING_RANGE
        if mp < lo_err or mp > hi_err:
            issues.append(
                ValidationIssue(
                    field="markup_pct",
                    issue_type="out_of_range",
                    severity="error",
                    expected=f"{lo_err * 100:.0f}%–{hi_err * 100:.0f}%",
                    actual=_fmt_pct(scope.markup_pct),
                    message=f"markup_pct {_fmt_pct(scope.markup_pct)} is outside hard limits "
                    f"({lo_err * 100:.0f}%–{hi_err * 100:.0f}%).",
                )
            )
        elif mp < lo_warn or mp > hi_warn:
            issues.append(
                ValidationIssue(
                    field="markup_pct",
                    issue_type="out_of_range",
                    severity="warning",
                    expected=f"{lo_warn * 100:.0f}%–{hi_warn * 100:.0f}%",
                    actual=_fmt_pct(scope.markup_pct),
                    message=f"markup_pct {_fmt_pct(scope.markup_pct)} is outside the typical "
                    f"range ({lo_warn * 100:.0f}%–{hi_warn * 100:.0f}%).",
                )
            )

    # ------------------------------------------------------------------
    # 3. cost_per_sf expected range for scope type
    # ------------------------------------------------------------------
    if scope.cost_per_sf is not None and scope.cost_per_sf > 0:
        rng = COST_PER_SF_RANGES.get(stype)
        if rng is not None:
            lo, hi = rng
            cpf = float(scope.cost_per_sf)
            if cpf < lo or cpf > hi:
                issues.append(
                    ValidationIssue(
                        field="cost_per_sf",
                        issue_type="suspicious",
                        severity="warning",
                        expected=f"${lo:.2f}–${hi:.2f}/SF",
                        actual=f"${cpf:.2f}/SF",
                        message=f"cost_per_sf ${cpf:.2f} is outside expected range for "
                        f"{stype} (${lo:.2f}–${hi:.2f}/SF).",
                    )
                )

    # ------------------------------------------------------------------
    # 4. total > 0
    # ------------------------------------------------------------------
    if scope.total is not None and scope.total <= 0:
        issues.append(
            ValidationIssue(
                field="total",
                issue_type="out_of_range",
                severity="error",
                expected="> 0",
                actual=_fmt_money(scope.total),
                message="Scope total must be greater than zero.",
            )
        )

    # ------------------------------------------------------------------
    # 5. sales_tax >= 0
    # ------------------------------------------------------------------
    if scope.sales_tax is not None and scope.sales_tax < 0:
        issues.append(
            ValidationIssue(
                field="sales_tax",
                issue_type="out_of_range",
                severity="error",
                expected=">= $0.00",
                actual=_fmt_money(scope.sales_tax),
                message="sales_tax cannot be negative.",
            )
        )

    # ------------------------------------------------------------------
    # 6. Total math: total ≈ material_price + labor_price + sales_tax
    # ------------------------------------------------------------------
    if scope.total is not None and float(scope.total) != 0:
        components_available = any(v is not None for v in [scope.material_price, scope.labor_price, scope.sales_tax])
        if components_available:
            mat = float(scope.material_price or 0)
            lab = float(scope.labor_price or 0)
            tax = float(scope.sales_tax or 0)
            computed_total = mat + lab + tax
            diff = _ratio_diff(Decimal(str(computed_total)), scope.total)
            if diff is not None and diff > MATH_TOLERANCE:
                issues.append(
                    ValidationIssue(
                        field="total",
                        issue_type="math_mismatch",
                        severity="warning",
                        expected=f"≈ {_fmt_money(Decimal(str(computed_total)))} "
                        f"(material_price + labor_price + sales_tax)",
                        actual=_fmt_money(scope.total),
                        message=f"Total mismatch: extracted {_fmt_money(scope.total)} but "
                        f"material_price + labor_price + sales_tax = "
                        f"{_fmt_money(Decimal(str(computed_total)))} "
                        f"({diff * 100:.1f}% difference).",
                    )
                )

    # ------------------------------------------------------------------
    # 7. Material price math: material_price ≈ material_cost × (1 + markup_pct)
    # ------------------------------------------------------------------
    if (
        scope.material_price is not None
        and scope.material_cost is not None
        and scope.markup_pct is not None
        and float(scope.material_price) != 0
    ):
        expected_mp = scope.material_cost * (1 + scope.markup_pct)
        diff = _ratio_diff(expected_mp, scope.material_price)
        if diff is not None and diff > MATH_TOLERANCE / 2:  # tighter: 1%
            issues.append(
                ValidationIssue(
                    field="material_price",
                    issue_type="math_mismatch",
                    severity="warning",
                    expected=f"{_fmt_money(expected_mp)} (material_cost × (1 + {_fmt_pct(scope.markup_pct)}))",
                    actual=_fmt_money(scope.material_price),
                    message=f"material_price {_fmt_money(scope.material_price)} does not match "
                    f"material_cost × (1 + markup) = {_fmt_money(expected_mp)} "
                    f"({diff * 100:.1f}% difference).",
                )
            )

    # ------------------------------------------------------------------
    # 8. Material cost math: material_cost ≈ sf × cost_per_sf
    # ------------------------------------------------------------------
    if (
        scope.material_cost is not None
        and scope.square_footage is not None
        and scope.cost_per_sf is not None
        and float(scope.material_cost) != 0
    ):
        expected_mc = scope.square_footage * scope.cost_per_sf
        diff = _ratio_diff(expected_mc, scope.material_cost)
        if diff is not None and diff > MATH_TOLERANCE / 2:  # 1%
            issues.append(
                ValidationIssue(
                    field="material_cost",
                    issue_type="math_mismatch",
                    severity="warning",
                    expected=f"{_fmt_money(expected_mc)} (SF × cost_per_sf)",
                    actual=_fmt_money(scope.material_cost),
                    message=f"material_cost {_fmt_money(scope.material_cost)} does not match "
                    f"SF × cost_per_sf = {_fmt_money(expected_mc)} "
                    f"({diff * 100:.1f}% difference).",
                )
            )

    # ------------------------------------------------------------------
    # 9. man_days present when labor_price > 0
    # ------------------------------------------------------------------
    if scope.labor_price is not None and float(scope.labor_price) > 0 and scope.man_days is None:
        issues.append(
            ValidationIssue(
                field="man_days",
                issue_type="missing_required",
                severity="warning",
                expected="man_days > 0",
                actual="None",
                message=f"labor_price is {_fmt_money(scope.labor_price)} but man_days is not set.",
            )
        )

    is_valid = not any(i.severity == "error" for i in issues)
    return ScopeValidation(
        scope_index=scope_index,
        tag=scope.tag,
        scope_type=scope.scope_type,
        issues=issues,
        is_valid=is_valid,
    )


# ---------------------------------------------------------------------------
# Project-level validation
# ---------------------------------------------------------------------------


def validate_project(project: ExtractedProject) -> ProjectValidation:
    """Validate an extracted project — all scopes plus project-level checks.

    Project-level checks include:
    - At least one scope was extracted
    - All scopes have scope_type set
    - Grand total consistency (extracted grand_total ≈ sum of scope totals)

    Confidence score starts at 1.0 and is reduced by 0.2 per error and
    0.05 per warning, clamped to [0.0, 1.0].

    Args:
        project: The extracted project to validate.

    Returns:
        ProjectValidation with scope-level and project-level issues and a
        confidence score.
    """
    project_issues: list[ValidationIssue] = []

    # ------------------------------------------------------------------
    # Project check 1: at least 1 scope extracted
    # ------------------------------------------------------------------
    if not project.scopes:
        project_issues.append(
            ValidationIssue(
                field="scopes",
                issue_type="missing_required",
                severity="error",
                expected=">= 1 scope",
                actual="0 scopes",
                message="No scopes were extracted from this project.",
            )
        )

    # ------------------------------------------------------------------
    # Project check 2: all scopes have scope_type set
    # ------------------------------------------------------------------
    for i, scope in enumerate(project.scopes):
        if not scope.scope_type or scope.scope_type.strip() == "":
            project_issues.append(
                ValidationIssue(
                    field=f"scopes[{i}].scope_type",
                    issue_type="missing_required",
                    severity="warning",
                    expected="non-empty scope_type",
                    actual=repr(scope.scope_type),
                    message=f"Scope at index {i} (tag={scope.tag!r}) is missing scope_type.",
                )
            )

    # ------------------------------------------------------------------
    # Project check 3: grand total consistency
    # ------------------------------------------------------------------
    if project.grand_total is not None and float(project.grand_total) != 0 and project.scopes:
        scopes_with_totals = [s for s in project.scopes if s.total is not None]
        if scopes_with_totals:
            computed_grand = sum(float(s.total) for s in scopes_with_totals)  # type: ignore[arg-type]
            diff = _ratio_diff(Decimal(str(computed_grand)), project.grand_total)
            if diff is not None and diff > MATH_TOLERANCE:
                project_issues.append(
                    ValidationIssue(
                        field="grand_total",
                        issue_type="math_mismatch",
                        severity="warning",
                        expected=f"≈ ${computed_grand:,.2f} (sum of scope totals)",
                        actual=_fmt_money(project.grand_total),
                        message=f"Grand total {_fmt_money(project.grand_total)} differs from "
                        f"sum of scope totals ${computed_grand:,.2f} "
                        f"({diff * 100:.1f}% difference).",
                    )
                )

    # ------------------------------------------------------------------
    # Validate each scope
    # ------------------------------------------------------------------
    scope_validations = [validate_scope(scope, idx) for idx, scope in enumerate(project.scopes)]

    # ------------------------------------------------------------------
    # Confidence score
    # ------------------------------------------------------------------
    all_issues = list(project_issues)
    for sv in scope_validations:
        all_issues.extend(sv.issues)

    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")

    confidence = 1.0 - (error_count * 0.2) - (warning_count * 0.05)
    confidence = max(0.0, min(1.0, confidence))

    overall_valid = not any(i.severity == "error" for i in project_issues) and all(
        sv.is_valid for sv in scope_validations
    )

    # ------------------------------------------------------------------
    # Human-readable summary
    # ------------------------------------------------------------------
    scope_count = len(project.scopes)
    valid_scope_count = sum(1 for sv in scope_validations if sv.is_valid)
    if overall_valid:
        summary = (
            f"Project is valid. {scope_count} scope(s) extracted, all passed validation. Confidence: {confidence:.0%}."
        )
    else:
        summary = (
            f"{valid_scope_count}/{scope_count} scope(s) valid. "
            f"{error_count} error(s), {warning_count} warning(s). "
            f"Confidence: {confidence:.0%}."
        )

    return ProjectValidation(
        project_name=project.project_name,
        source_file=project.source_file,
        scope_validations=scope_validations,
        project_issues=project_issues,
        overall_valid=overall_valid,
        confidence_score=confidence,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------


def validate_batch(results: list[ExtractionResult]) -> BatchValidationReport:
    """Validate a batch of extraction results and generate a quality report.

    Processes only successful ExtractionResult objects (where result.success
    is True and result.project is set). Failed extractions are excluded from
    project-level counts but contribute to total_projects.

    Args:
        results: List of ExtractionResult objects from extract_all_buildups.

    Returns:
        BatchValidationReport with per-project validations, aggregate counts,
        and the most common issue types across the batch.
    """
    project_validations: list[ProjectValidation] = []
    total_scopes = 0
    valid_scopes = 0

    for result in results:
        if not result.success or result.project is None:
            continue
        pv = validate_project(result.project)
        project_validations.append(pv)
        total_scopes += len(pv.scope_validations)
        valid_scopes += sum(1 for sv in pv.scope_validations if sv.is_valid)

    valid_projects = sum(1 for pv in project_validations if pv.overall_valid)
    projects_with_errors = sum(
        1
        for pv in project_validations
        if any(i.severity == "error" for i in pv.project_issues) or any(not sv.is_valid for sv in pv.scope_validations)
    )
    projects_with_warnings = sum(
        1
        for pv in project_validations
        if not pv.overall_valid
        and not (
            any(i.severity == "error" for i in pv.project_issues) or any(not sv.is_valid for sv in pv.scope_validations)
        )
    )

    # Count common issue types across all projects
    issue_counts: dict[tuple[str, str, str], int] = {}
    for pv in project_validations:
        all_issues = list(pv.project_issues)
        for sv in pv.scope_validations:
            all_issues.extend(sv.issues)
        for issue in all_issues:
            key = (issue.field, issue.issue_type, issue.severity)
            issue_counts[key] = issue_counts.get(key, 0) + 1

    common_issues = [
        {"field": k[0], "issue_type": k[1], "severity": k[2], "count": v}
        for k, v in sorted(issue_counts.items(), key=lambda x: -x[1])
    ][:10]

    return BatchValidationReport(
        total_projects=len(results),
        valid_projects=valid_projects,
        projects_with_warnings=projects_with_warnings,
        projects_with_errors=projects_with_errors,
        total_scopes=total_scopes,
        valid_scopes=valid_scopes,
        common_issues=common_issues,
        project_validations=project_validations,
        generated_at=datetime.now(tz=UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Rich report printer
# ---------------------------------------------------------------------------


def print_validation_report(report: BatchValidationReport) -> None:
    """Print a human-readable validation report to stdout using rich.

    Displays a summary table with per-project confidence scores, scope counts,
    and issue breakdowns. Lists the most common issues across the batch and
    expands error details for invalid projects.

    Args:
        report: The BatchValidationReport to display.
    """
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # ------------------------------------------------------------------
    # Header panel
    # ------------------------------------------------------------------
    generated = report.generated_at[:19].replace("T", " ")
    header_lines = [
        f"Generated: {generated} UTC",
        f"Total projects: {report.total_projects}  |  "
        f"Valid: {report.valid_projects}  |  "
        f"Warnings: {report.projects_with_warnings}  |  "
        f"Errors: {report.projects_with_errors}",
        f"Total scopes: {report.total_scopes}  |  Valid: {report.valid_scopes}",
    ]
    console.print(
        Panel(
            "\n".join(header_lines),
            title="[bold cyan]Acoustimator Extraction Validation Report[/bold cyan]",
            border_style="cyan",
        )
    )

    # ------------------------------------------------------------------
    # Per-project summary table
    # ------------------------------------------------------------------
    proj_table = Table(
        title="Project Summary",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        highlight=True,
    )
    proj_table.add_column("Project", style="bold", no_wrap=True, max_width=40)
    proj_table.add_column("Scopes", justify="right")
    proj_table.add_column("Valid Scopes", justify="right")
    proj_table.add_column("Confidence", justify="right")
    proj_table.add_column("Status", justify="center")

    for pv in report.project_validations:
        scope_count = len(pv.scope_validations)
        valid_count = sum(1 for sv in pv.scope_validations if sv.is_valid)
        confidence_str = f"{pv.confidence_score:.0%}"
        if pv.overall_valid:
            status = "[green]OK[/green]"
        else:
            error_count = sum(1 for sv in pv.scope_validations for i in sv.issues if i.severity == "error") + sum(
                1 for i in pv.project_issues if i.severity == "error"
            )
            warn_count = sum(1 for sv in pv.scope_validations for i in sv.issues if i.severity == "warning") + sum(
                1 for i in pv.project_issues if i.severity == "warning"
            )
            parts = []
            if error_count:
                parts.append(f"[red]{error_count}E[/red]")
            if warn_count:
                parts.append(f"[yellow]{warn_count}W[/yellow]")
            status = " ".join(parts) if parts else "[yellow]WARN[/yellow]"
        proj_table.add_row(
            pv.project_name,
            str(scope_count),
            str(valid_count),
            confidence_str,
            status,
        )

    console.print(proj_table)

    # ------------------------------------------------------------------
    # Common issues table
    # ------------------------------------------------------------------
    if report.common_issues:
        issue_table = Table(
            title="Most Common Issues",
            box=box.SIMPLE_HEAD,
            show_lines=False,
        )
        issue_table.add_column("Field", style="dim")
        issue_table.add_column("Issue Type")
        issue_table.add_column("Severity")
        issue_table.add_column("Count", justify="right")

        for ci in report.common_issues:
            sev = ci["severity"]
            sev_str = f"[red]{sev}[/red]" if sev == "error" else f"[yellow]{sev}[/yellow]" if sev == "warning" else sev
            issue_table.add_row(ci["field"], ci["issue_type"], sev_str, str(ci["count"]))

        console.print(issue_table)

    # ------------------------------------------------------------------
    # Detail for invalid projects
    # ------------------------------------------------------------------
    invalid = [pv for pv in report.project_validations if not pv.overall_valid]
    if invalid:
        console.print(f"\n[bold red]Invalid Projects ({len(invalid)})[/bold red]")
        for pv in invalid:
            console.print(f"\n  [bold]{pv.project_name}[/bold] — {pv.summary}")

            # Project-level issues
            for issue in pv.project_issues:
                color = "red" if issue.severity == "error" else "yellow"
                console.print(f"    [{color}][{issue.severity.upper()}][/{color}] {issue.field}: {issue.message}")

            # Scope-level issues
            for sv in pv.scope_validations:
                if not sv.issues:
                    continue
                tag_str = sv.tag or f"scope[{sv.scope_index}]"
                for issue in sv.issues:
                    color = "red" if issue.severity == "error" else "yellow"
                    console.print(
                        f"    [{color}][{issue.severity.upper()}][/{color}] {tag_str} / {issue.field}: {issue.message}"
                    )
    else:
        console.print("\n[bold green]All projects passed validation.[/bold green]")
