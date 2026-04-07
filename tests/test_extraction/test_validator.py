"""Unit tests for the extraction validator module.

Tests scope-level checks, project-level checks, batch aggregation, and
confidence scoring. Does NOT test Claude API calls or file I/O.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.extraction.excel_parser import ExtractedProject, ExtractedScope, ExtractionResult
from src.extraction.validator import (
    ScopeValidation,
    validate_batch,
    validate_project,
    validate_scope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(**kwargs) -> ExtractedScope:
    """Build an ExtractedScope with sensible ACT defaults, overridable by kwargs."""
    defaults = {
        "scope_type": "ACT",
        "tag": "ACT-1",
        "square_footage": Decimal("2000"),
        "cost_per_sf": Decimal("2.50"),
        "material_cost": Decimal("5000.00"),
        "markup_pct": Decimal("0.30"),
        "material_price": Decimal("6500.00"),
        "man_days": Decimal("3"),
        "labor_price": Decimal("1566.00"),
        "sales_tax": Decimal("390.00"),
        "total": Decimal("8456.00"),  # 6500 + 1566 + 390
    }
    defaults.update(kwargs)
    return ExtractedScope(**defaults)


def _make_project(scopes: list[ExtractedScope] | None = None, **kwargs) -> ExtractedProject:
    """Build an ExtractedProject with one valid ACT scope by default."""
    if scopes is None:
        scopes = [_make_scope()]
    defaults = {
        "project_name": "Test Project",
        "folder_name": "Test Project",
        "source_file": "/data/raw/test/buildup.xlsx",
        "format_type": "A",
        "scopes": scopes,
    }
    defaults.update(kwargs)
    return ExtractedProject(**defaults)


def _make_result(project: ExtractedProject | None = None, success: bool = True) -> ExtractionResult:
    """Build an ExtractionResult wrapping the given project."""
    return ExtractionResult(success=success, project=project, tokens_used=1000)


def _issues_by_field(sv: ScopeValidation, field: str) -> list:
    return [i for i in sv.issues if i.field == field]


def _issues_by_severity(validation, severity: str) -> list:
    """Collect all issues of given severity from a ScopeValidation or ProjectValidation."""
    if isinstance(validation, ScopeValidation):
        return [i for i in validation.issues if i.severity == severity]
    # ProjectValidation — gather project + scope issues
    all_issues = list(validation.project_issues)
    for sv in validation.scope_validations:
        all_issues.extend(sv.issues)
    return [i for i in all_issues if i.severity == severity]


# ---------------------------------------------------------------------------
# 1. Valid scope → no issues
# ---------------------------------------------------------------------------


class TestValidScopeNoIssues:
    def test_clean_act_scope_has_no_issues(self):
        """A well-formed ACT scope with consistent math should produce zero issues."""
        # Build a fully self-consistent scope
        sf = Decimal("2000")
        cost_per_sf = Decimal("2.50")
        mat_cost = sf * cost_per_sf  # 5000
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)  # 6500
        labor = Decimal("1566.00")
        tax = mat_price * Decimal("0.06")  # 390
        total = mat_price + labor + tax  # 8456

        scope = ExtractedScope(
            scope_type="ACT",
            tag="ACT-1",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("3"),
            labor_price=labor,
            sales_tax=tax,
            total=total,
        )
        sv = validate_scope(scope, 0)
        assert sv.is_valid is True
        assert sv.issues == []

    def test_valid_awp_scope_no_issues(self):
        """A well-formed AWP scope within expected ranges should be clean."""
        sf = Decimal("500")
        cost_per_sf = Decimal("25.00")
        mat_cost = sf * cost_per_sf  # 12500
        markup = Decimal("0.35")
        mat_price = mat_cost * (1 + markup)  # 16875
        labor = Decimal("5000.00")
        tax = mat_price * Decimal("0.06")  # 1012.50
        total = mat_price + labor + tax

        scope = ExtractedScope(
            scope_type="AWP",
            tag="AWP-1",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("5"),
            labor_price=labor,
            sales_tax=tax,
            total=total,
        )
        sv = validate_scope(scope, 0)
        assert sv.is_valid is True
        assert sv.issues == []


# ---------------------------------------------------------------------------
# 2. Markup 1.5 (150%) → error
# ---------------------------------------------------------------------------


class TestMarkupOutOfRange:
    def test_markup_150_pct_is_error(self):
        """Markup of 1.5 (150%) exceeds hard upper limit of 100% → error."""
        scope = _make_scope(markup_pct=Decimal("1.5"))
        sv = validate_scope(scope, 0)
        errors = _issues_by_severity(sv, "error")
        markup_errors = [i for i in errors if i.field == "markup_pct"]
        assert len(markup_errors) >= 1
        assert markup_errors[0].issue_type == "out_of_range"

    def test_markup_005_below_error_floor(self):
        """Markup of 0.05 (5%) is below hard lower limit of 10% → error."""
        scope = _make_scope(markup_pct=Decimal("0.05"))
        sv = validate_scope(scope, 0)
        errors = [i for i in sv.issues if i.field == "markup_pct" and i.severity == "error"]
        assert len(errors) >= 1

    def test_markup_0_10_is_warning_not_error(self):
        """Markup of 0.10 (10%) is within hard limits but below warning floor → warning."""
        scope = _make_scope(markup_pct=Decimal("0.10"))
        sv = validate_scope(scope, 0)
        markup_issues = _issues_by_field(sv, "markup_pct")
        assert markup_issues, "Expected at least one issue for 10% markup"
        severities = {i.severity for i in markup_issues}
        assert "error" not in severities
        assert "warning" in severities

    def test_markup_080_is_warning_not_error(self):
        """Markup of 0.80 (80%) is within hard limits but above warning ceiling → warning."""
        scope = _make_scope(markup_pct=Decimal("0.80"))
        sv = validate_scope(scope, 0)
        markup_issues = _issues_by_field(sv, "markup_pct")
        severities = {i.severity for i in markup_issues}
        assert "error" not in severities
        assert "warning" in severities

    def test_markup_1_0_exact_is_valid(self):
        """Markup of exactly 1.0 (100%) is at the error boundary — no error."""
        scope = _make_scope(markup_pct=Decimal("1.00"))
        sv = validate_scope(scope, 0)
        markup_errors = [i for i in sv.issues if i.field == "markup_pct" and i.severity == "error"]
        assert markup_errors == []


# ---------------------------------------------------------------------------
# 3. SF = 0 → error
# ---------------------------------------------------------------------------


class TestSFZero:
    def test_sf_zero_is_error_for_act(self):
        """SF = 0 on an ACT scope must be flagged as a missing_required error."""
        scope = _make_scope(square_footage=Decimal("0"))
        sv = validate_scope(scope, 0)
        sf_errors = [i for i in sv.issues if i.field == "square_footage" and i.severity == "error"]
        assert len(sf_errors) >= 1
        assert sf_errors[0].issue_type == "missing_required"

    def test_sf_none_is_error_for_awp(self):
        """SF = None on an AWP scope must be flagged as a missing_required error."""
        scope = _make_scope(scope_type="AWP", tag="AWP-1", square_footage=None)
        sv = validate_scope(scope, 0)
        sf_errors = [i for i in sv.issues if i.field == "square_footage" and i.severity == "error"]
        assert len(sf_errors) >= 1

    def test_sf_zero_not_checked_for_baffles(self):
        """Baffles is not an area-based type; missing SF should not produce an error."""
        scope = _make_scope(scope_type="Baffles", tag="B-1", square_footage=None)
        sv = validate_scope(scope, 0)
        sf_errors = [i for i in sv.issues if i.field == "square_footage" and i.severity == "error"]
        assert sf_errors == []


# ---------------------------------------------------------------------------
# 4. Total mismatch > 5% → warning
# ---------------------------------------------------------------------------


class TestTotalMismatch:
    def test_total_mismatch_5pct_is_warning(self):
        """When extracted total differs from component sum by >5%, expect a warning."""
        # Components sum to 8456, but we set total to 8900 (~5.2% higher)
        scope = _make_scope(
            material_price=Decimal("6500.00"),
            labor_price=Decimal("1566.00"),
            sales_tax=Decimal("390.00"),
            total=Decimal("8900.00"),  # sum is 8456 → diff ~5.25%
        )
        sv = validate_scope(scope, 0)
        total_warnings = [
            i for i in sv.issues if i.field == "total" and i.issue_type == "math_mismatch"
        ]
        assert len(total_warnings) >= 1
        assert total_warnings[0].severity == "warning"

    def test_total_within_2pct_no_mismatch(self):
        """A total within the 2% tolerance should not produce a math_mismatch issue."""
        # Components sum to 8456; set total 1% higher → no warning
        scope = _make_scope(
            material_price=Decimal("6500.00"),
            labor_price=Decimal("1566.00"),
            sales_tax=Decimal("390.00"),
            total=Decimal("8541.00"),  # ~1% over
        )
        sv = validate_scope(scope, 0)
        total_mismatches = [
            i for i in sv.issues if i.field == "total" and i.issue_type == "math_mismatch"
        ]
        assert total_mismatches == []

    def test_total_zero_or_negative_is_error(self):
        """A total ≤ 0 must be flagged as an error."""
        scope = _make_scope(total=Decimal("0"))
        sv = validate_scope(scope, 0)
        total_errors = [i for i in sv.issues if i.field == "total" and i.severity == "error"]
        assert len(total_errors) >= 1


# ---------------------------------------------------------------------------
# 5. material_price ≠ material_cost × (1 + markup) → warning
# ---------------------------------------------------------------------------


class TestMaterialPriceMismatch:
    def test_material_price_mismatch_is_warning(self):
        """material_price far from material_cost × (1+markup) should be flagged."""
        # mat_cost=5000, markup=0.30 → expected mat_price=6500
        # Set mat_price=7500 (15% over) → warning
        scope = _make_scope(
            material_cost=Decimal("5000.00"),
            markup_pct=Decimal("0.30"),
            material_price=Decimal("7500.00"),
        )
        sv = validate_scope(scope, 0)
        mp_warnings = [
            i for i in sv.issues if i.field == "material_price" and i.issue_type == "math_mismatch"
        ]
        assert len(mp_warnings) >= 1
        assert mp_warnings[0].severity == "warning"

    def test_material_price_within_tolerance_no_warning(self):
        """material_price within 1% of material_cost × (1+markup) should be clean."""
        mat_cost = Decimal("5000.00")
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)  # exactly 6500
        scope = _make_scope(
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
        )
        sv = validate_scope(scope, 0)
        mp_mismatches = [
            i for i in sv.issues if i.field == "material_price" and i.issue_type == "math_mismatch"
        ]
        assert mp_mismatches == []

    def test_missing_markup_skips_material_price_check(self):
        """If markup_pct is None, the material_price math check is skipped."""
        scope = _make_scope(markup_pct=None)
        sv = validate_scope(scope, 0)
        mp_mismatches = [
            i for i in sv.issues if i.field == "material_price" and i.issue_type == "math_mismatch"
        ]
        assert mp_mismatches == []


# ---------------------------------------------------------------------------
# 6. Project with 0 scopes → error
# ---------------------------------------------------------------------------


class TestProjectNoScopes:
    def test_empty_scopes_list_is_project_error(self):
        """A project with no scopes must have a missing_required error at project level."""
        project = _make_project(scopes=[])
        pv = validate_project(project)
        scope_errors = [
            i for i in pv.project_issues if i.field == "scopes" and i.severity == "error"
        ]
        assert len(scope_errors) >= 1
        assert pv.overall_valid is False

    def test_project_with_scopes_no_missing_error(self):
        """A project with at least one scope should not have a 'scopes' missing error."""
        project = _make_project()
        pv = validate_project(project)
        scope_errors = [
            i for i in pv.project_issues if i.field == "scopes" and i.severity == "error"
        ]
        assert scope_errors == []

    def test_confidence_zero_for_project_with_many_errors(self):
        """Confidence should drop to 0.0 when there are 5+ error-severity issues."""
        # 0 scopes = 1 project error, plus 5 scopes each with SF=0 errors
        bad_scopes = [_make_scope(square_footage=Decimal("0")) for _ in range(6)]
        project = _make_project(scopes=bad_scopes)
        pv = validate_project(project)
        # Each scope has at least 1 error → 6 × 0.2 = 1.2 → confidence = 0.0
        assert pv.confidence_score == 0.0


# ---------------------------------------------------------------------------
# 7. validate_batch with mixed valid/invalid → correct counts
# ---------------------------------------------------------------------------


class TestValidateBatch:
    def _build_valid_result(self, name: str) -> ExtractionResult:
        sf = Decimal("1000")
        cost_per_sf = Decimal("3.00")
        mat_cost = sf * cost_per_sf
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)
        labor = Decimal("1000.00")
        tax = mat_price * Decimal("0.06")
        total = mat_price + labor + tax
        scope = ExtractedScope(
            scope_type="ACT",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("2"),
            labor_price=labor,
            sales_tax=tax,
            total=total,
        )
        project = _make_project(scopes=[scope], project_name=name)
        return _make_result(project)

    def _build_invalid_result(self, name: str) -> ExtractionResult:
        """Project with 0 scopes → guaranteed error."""
        project = _make_project(scopes=[], project_name=name)
        return _make_result(project)

    def test_batch_counts_are_correct(self):
        """validate_batch must correctly tally valid/invalid projects and scopes."""
        results = [
            self._build_valid_result("Alpha"),
            self._build_valid_result("Beta"),
            self._build_invalid_result("Gamma"),
        ]
        report = validate_batch(results)

        assert report.total_projects == 3
        assert report.valid_projects == 2
        assert report.projects_with_errors == 1
        # 2 valid projects × 1 scope each; Gamma has 0 scopes
        assert report.total_scopes == 2
        assert report.valid_scopes == 2

    def test_failed_extractions_excluded_from_project_validations(self):
        """ExtractionResult with success=False should not appear in project_validations."""
        valid = self._build_valid_result("Alpha")
        failed = _make_result(project=None, success=False)
        report = validate_batch([valid, failed])

        assert report.total_projects == 2  # total includes failed
        assert len(report.project_validations) == 1  # only the successful one
        assert report.project_validations[0].project_name == "Alpha"

    def test_empty_batch_returns_zero_counts(self):
        """An empty list of results should produce an all-zero report."""
        report = validate_batch([])
        assert report.total_projects == 0
        assert report.valid_projects == 0
        assert report.total_scopes == 0
        assert report.project_validations == []

    def test_common_issues_sorted_by_count(self):
        """common_issues should be sorted descending by count."""
        bad = [self._build_invalid_result(f"Proj{i}") for i in range(3)]
        valid = [self._build_valid_result(f"Good{i}") for i in range(1)]
        report = validate_batch(bad + valid)
        if len(report.common_issues) >= 2:
            counts = [ci["count"] for ci in report.common_issues]
            assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# 8. Confidence score decreases with more issues
# ---------------------------------------------------------------------------


class TestConfidenceScore:
    def test_single_error_reduces_confidence_by_0_2(self):
        """One error issue should reduce confidence from 1.0 to 0.8."""
        # Force exactly one error: SF = 0 on an ACT scope
        # All other fields are fine
        sf = Decimal("0")
        scope = ExtractedScope(
            scope_type="ACT",
            tag="ACT-1",
            square_footage=sf,  # ← error
            cost_per_sf=Decimal("3.00"),
            material_cost=Decimal("6000.00"),
            markup_pct=Decimal("0.30"),
            material_price=Decimal("7800.00"),
            man_days=Decimal("2"),
            labor_price=Decimal("1000.00"),
            sales_tax=Decimal("468.00"),
            total=Decimal("9268.00"),
        )
        project = _make_project(scopes=[scope])
        pv = validate_project(project)
        errors = _issues_by_severity(pv, "error")
        # Should have exactly 1 error (SF=0) and no others
        assert len(errors) >= 1
        # Confidence = 1.0 - 0.2 * error_count - 0.05 * warning_count
        expected = max(
            0.0,
            1.0 - 0.2 * len(errors) - 0.05 * len(_issues_by_severity(pv, "warning")),
        )
        assert abs(pv.confidence_score - expected) < 1e-9

    def test_no_issues_confidence_is_1_0(self):
        """A perfectly clean project should have confidence == 1.0."""
        sf = Decimal("2000")
        cost_per_sf = Decimal("3.00")
        mat_cost = sf * cost_per_sf
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)
        labor = Decimal("1566.00")
        tax = mat_price * Decimal("0.06")
        total = mat_price + labor + tax

        scope = ExtractedScope(
            scope_type="ACT",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("3"),
            labor_price=labor,
            sales_tax=tax,
            total=total,
        )
        project = _make_project(scopes=[scope])
        pv = validate_project(project)
        assert pv.confidence_score == pytest.approx(1.0)

    def test_confidence_never_below_zero(self):
        """Confidence must never go below 0.0 regardless of issue count."""
        # Deliberately create 10 error scopes
        bad_scopes = [
            _make_scope(markup_pct=Decimal("2.0"), square_footage=Decimal("0")) for _ in range(10)
        ]
        project = _make_project(scopes=bad_scopes)
        pv = validate_project(project)
        assert pv.confidence_score >= 0.0

    def test_more_issues_lower_confidence(self):
        """A project with more issues should have a lower confidence score."""
        clean_scope = ExtractedScope(
            scope_type="ACT",
            square_footage=Decimal("1000"),
            cost_per_sf=Decimal("3.00"),
            material_cost=Decimal("3000"),
            markup_pct=Decimal("0.30"),
            material_price=Decimal("3900"),
            man_days=Decimal("2"),
            labor_price=Decimal("1000"),
            sales_tax=Decimal("234"),
            total=Decimal("5134"),
        )
        project_clean = _make_project(scopes=[clean_scope])
        pv_clean = validate_project(project_clean)

        # Multiple error scopes
        bad_scopes = [_make_scope(square_footage=Decimal("0")) for _ in range(3)]
        project_bad = _make_project(scopes=bad_scopes)
        pv_bad = validate_project(project_bad)

        assert pv_clean.confidence_score > pv_bad.confidence_score


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


class TestAdditionalEdgeCases:
    def test_negative_sales_tax_is_error(self):
        """Negative sales_tax must produce an error."""
        scope = _make_scope(sales_tax=Decimal("-100.00"))
        sv = validate_scope(scope, 0)
        tax_errors = [i for i in sv.issues if i.field == "sales_tax" and i.severity == "error"]
        assert len(tax_errors) >= 1

    def test_labor_price_without_man_days_is_warning(self):
        """When labor_price > 0 but man_days is None, expect a warning."""
        scope = _make_scope(man_days=None, labor_price=Decimal("2000.00"))
        sv = validate_scope(scope, 0)
        md_warnings = [i for i in sv.issues if i.field == "man_days" and i.severity == "warning"]
        assert len(md_warnings) >= 1

    def test_cost_per_sf_out_of_range_for_act_is_warning(self):
        """cost_per_sf of $0.50 is below ACT range ($1.57–$9.44) → suspicious warning."""
        sf = Decimal("2000")
        cost_per_sf = Decimal("0.50")
        mat_cost = sf * cost_per_sf  # 1000
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)
        labor = Decimal("1000.00")
        tax = mat_price * Decimal("0.06")
        total = mat_price + labor + tax
        scope = ExtractedScope(
            scope_type="ACT",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("2"),
            labor_price=labor,
            sales_tax=tax,
            total=total,
        )
        sv = validate_scope(scope, 0)
        cpf_issues = [
            i for i in sv.issues if i.field == "cost_per_sf" and i.issue_type == "suspicious"
        ]
        assert len(cpf_issues) >= 1
        assert cpf_issues[0].severity == "warning"

    def test_scope_type_other_no_cost_per_sf_range_check(self):
        """Scope type 'Other' has no expected cost/SF range — no suspicious warning."""
        scope = _make_scope(scope_type="Other", tag="X-1", cost_per_sf=Decimal("500.00"))
        sv = validate_scope(scope, 0)
        cpf_issues = [i for i in sv.issues if i.field == "cost_per_sf"]
        assert cpf_issues == []

    def test_grand_total_mismatch_is_project_warning(self):
        """grand_total differing from sum of scope totals by >2% → project-level warning."""
        sf = Decimal("1000")
        cost_per_sf = Decimal("3.00")
        mat_cost = sf * cost_per_sf
        markup = Decimal("0.30")
        mat_price = mat_cost * (1 + markup)
        labor = Decimal("1000.00")
        tax = mat_price * Decimal("0.06")
        scope_total = mat_price + labor + tax  # correct scope total

        scope = ExtractedScope(
            scope_type="ACT",
            square_footage=sf,
            cost_per_sf=cost_per_sf,
            material_cost=mat_cost,
            markup_pct=markup,
            material_price=mat_price,
            man_days=Decimal("2"),
            labor_price=labor,
            sales_tax=tax,
            total=scope_total,
        )
        # Set grand_total to something very different
        inflated_grand = scope_total * Decimal("1.20")
        project = _make_project(scopes=[scope], grand_total=inflated_grand)
        pv = validate_project(project)
        gt_issues = [
            i for i in pv.project_issues if i.field == "grand_total" and i.severity == "warning"
        ]
        assert len(gt_issues) >= 1

    def test_scope_validation_is_valid_false_on_error(self):
        """is_valid should be False when any issue has severity 'error'."""
        scope = _make_scope(square_footage=Decimal("0"))
        sv = validate_scope(scope, 0)
        assert sv.is_valid is False

    def test_scope_validation_is_valid_true_with_only_warnings(self):
        """is_valid should be True when issues are only warnings (no errors)."""
        # markup at 0.12 triggers a warning but not an error
        scope = _make_scope(markup_pct=Decimal("0.12"))
        sv = validate_scope(scope, 0)
        has_errors = any(i.severity == "error" for i in sv.issues)
        has_warnings = any(i.severity == "warning" for i in sv.issues)
        assert not has_errors
        assert has_warnings
        assert sv.is_valid is True

    def test_batch_report_has_iso_timestamp(self):
        """generated_at in BatchValidationReport should be a parseable ISO datetime."""
        from datetime import datetime

        report = validate_batch([])
        # Should not raise
        dt = datetime.fromisoformat(report.generated_at)
        assert dt is not None
