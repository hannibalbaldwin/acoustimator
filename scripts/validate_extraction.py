#!/usr/bin/env python3
"""Validate extraction results against known audit data.

Loads JSON extraction results and compares key fields against a curated set
of known-good values derived from the deep audit of Commercial Acoustics
buildups. Reports pass/fail for each field with details on mismatches.

Usage:
    python scripts/validate_extraction.py
    python scripts/validate_extraction.py --results-dir data/extracted
    python scripts/validate_extraction.py --verbose
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Known test cases from the deep audit
# ---------------------------------------------------------------------------

# Each entry maps a project folder name to expected values.
# Scope comparisons use partial matching: the extraction result must contain
# at least one scope matching the expected fields. Numeric comparisons use a
# tolerance of 1% for square footage and 0.02 absolute for markup percentage.

KNOWN_VALUES: dict[str, dict] = {
    "Grant Thornton": {
        "format_type": "A",
        "scopes": [
            {
                "scope_type": "ACT",
                "product_name": "Dune",
                "square_footage": Decimal("4200"),
                "markup_pct": Decimal("0.30"),
            },
        ],
    },
    "Baycare - Dunedin Mease": {
        "format_type": "A",
        "scopes": [
            {
                "scope_type": "ACT",
                "product_name": "Cirrus",
                "square_footage": Decimal("9000"),
                "markup_pct": Decimal("0.15"),
            },
        ],
    },
    "HCA Gainesville": {
        "format_type": "A",
        "scopes": [
            {
                "scope_type": "ACT",
                "product_name": "Cortega",
                "square_footage": Decimal("6320"),
                "markup_pct": Decimal("0.35"),
            },
        ],
    },
    "BMG 231": {
        "format_type": "A",
        "scopes": [
            {
                "scope_type": "ACT",
                "product_name": "Cirrus",
                "square_footage": Decimal("9000"),
            },
        ],
    },
}

# Tolerances
SF_TOLERANCE_PCT = Decimal("0.01")  # 1% relative tolerance for square footage
MARKUP_TOLERANCE_ABS = Decimal("0.02")  # 2 percentage points absolute for markup


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------


@dataclass
class FieldCheck:
    """Result of a single field comparison."""

    field_name: str
    expected: str
    actual: str
    passed: bool
    message: str = ""


@dataclass
class ScopeCheck:
    """Result of validating one expected scope against extraction results."""

    scope_label: str
    matched: bool
    field_checks: list[FieldCheck] = field(default_factory=list)
    message: str = ""


@dataclass
class ProjectValidation:
    """Aggregated validation result for a single project."""

    project_name: str
    found: bool
    format_check: FieldCheck | None = None
    scope_checks: list[ScopeCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if not self.found:
            return False
        checks_ok = True
        if self.format_check and not self.format_check.passed:
            checks_ok = False
        for sc in self.scope_checks:
            if not sc.matched:
                checks_ok = False
            for fc in sc.field_checks:
                if not fc.passed:
                    checks_ok = False
        return checks_ok


def _decimal_from_json(value: object) -> Decimal:
    """Convert a JSON-loaded value to Decimal, handling strings and floats."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _approx_equal_pct(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    """Return True if actual is within tolerance % of expected."""
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / abs(expected) <= tolerance


def _approx_equal_abs(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    """Return True if actual is within absolute tolerance of expected."""
    return abs(actual - expected) <= tolerance


def _partial_match(haystack: str, needle: str) -> bool:
    """Case-insensitive partial string match."""
    return needle.lower() in haystack.lower()


def _find_matching_scope(
    extracted_scopes: list[dict],
    expected: dict,
) -> tuple[dict | None, list[FieldCheck]]:
    """Find the best-matching extracted scope for an expected scope.

    Returns the matched scope dict and a list of field checks. If no scope
    matches on scope_type, returns (None, []).
    """
    # First, filter to scopes with matching scope_type
    candidates = [
        s
        for s in extracted_scopes
        if s.get("scope_type", "").upper() == expected["scope_type"].upper()
    ]
    if not candidates:
        return None, []

    # If there's a product_name expectation, prefer scopes that match it
    if "product_name" in expected:
        product_matches = [
            s
            for s in candidates
            if _partial_match(s.get("product_name", ""), expected["product_name"])
        ]
        if product_matches:
            candidates = product_matches

    # Take the first candidate and run all field checks
    best = candidates[0]
    checks: list[FieldCheck] = []

    if "product_name" in expected:
        actual_name = best.get("product_name", "")
        ok = _partial_match(actual_name, expected["product_name"])
        checks.append(
            FieldCheck(
                field_name="product_name",
                expected=expected["product_name"],
                actual=actual_name,
                passed=ok,
                message="" if ok else f"Expected '{expected['product_name']}' in '{actual_name}'",
            )
        )

    if "square_footage" in expected:
        actual_sf = _decimal_from_json(best.get("square_footage"))
        expected_sf = expected["square_footage"]
        ok = _approx_equal_pct(actual_sf, expected_sf, SF_TOLERANCE_PCT)
        checks.append(
            FieldCheck(
                field_name="square_footage",
                expected=str(expected_sf),
                actual=str(actual_sf),
                passed=ok,
                message="" if ok else f"Off by {abs(actual_sf - expected_sf)} SF",
            )
        )

    if "markup_pct" in expected:
        actual_markup = _decimal_from_json(best.get("markup_pct"))
        expected_markup = expected["markup_pct"]
        ok = _approx_equal_abs(actual_markup, expected_markup, MARKUP_TOLERANCE_ABS)
        checks.append(
            FieldCheck(
                field_name="markup_pct",
                expected=str(expected_markup),
                actual=str(actual_markup),
                passed=ok,
                message="" if ok else f"Expected {expected_markup}, got {actual_markup}",
            )
        )

    return best, checks


def validate_project(project_name: str, expected: dict, result_data: dict) -> ProjectValidation:
    """Validate a single project's extraction result against expected values."""
    validation = ProjectValidation(project_name=project_name, found=True)

    # Normalise: extraction results wrap everything under a "project" key.
    # Fall back to the top-level dict for compatibility with any flat format.
    project_data = result_data.get("project", result_data)

    # Check format type
    if "format_type" in expected:
        actual_fmt = project_data.get("format_type", "")
        ok = actual_fmt.upper() == expected["format_type"].upper()
        validation.format_check = FieldCheck(
            field_name="format_type",
            expected=expected["format_type"],
            actual=actual_fmt,
            passed=ok,
            message=""
            if ok
            else f"Expected format '{expected['format_type']}', got '{actual_fmt}'",
        )

    # Check scopes
    extracted_scopes = project_data.get("scopes", [])

    for i, expected_scope in enumerate(expected.get("scopes", [])):
        label = f"{expected_scope['scope_type']}-{i + 1}"
        matched_scope, field_checks = _find_matching_scope(extracted_scopes, expected_scope)

        if matched_scope is None:
            validation.scope_checks.append(
                ScopeCheck(
                    scope_label=label,
                    matched=False,
                    message=f"No scope with type '{expected_scope['scope_type']}' found",
                )
            )
        else:
            validation.scope_checks.append(
                ScopeCheck(
                    scope_label=label,
                    matched=True,
                    field_checks=field_checks,
                )
            )

    return validation


def load_result(results_dir: Path, project_name: str) -> dict | None:
    """Load the JSON extraction result for a project by folder name.

    Tries exact name match first, then case-insensitive search.
    """
    exact_path = results_dir / f"{project_name}.json"
    if exact_path.exists():
        return json.loads(exact_path.read_text(encoding="utf-8"))

    # Case-insensitive fallback
    for path in results_dir.glob("*.json"):
        if path.stem.lower() == project_name.lower():
            return json.loads(path.read_text(encoding="utf-8"))

    return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_validation(validation: ProjectValidation, verbose: bool = False) -> None:
    """Print a human-readable validation report for one project."""
    status = "PASS" if validation.passed else "FAIL"
    marker = "+" if validation.passed else "X"
    print(f"  [{marker}] {validation.project_name}: {status}")

    if not validation.found:
        print("      -> Result file not found")
        return

    if validation.format_check and not validation.format_check.passed:
        fc = validation.format_check
        print(f"      format_type: FAIL — {fc.message}")
    elif verbose and validation.format_check:
        print(f"      format_type: PASS ({validation.format_check.actual})")

    for sc in validation.scope_checks:
        if not sc.matched:
            print(f"      scope {sc.scope_label}: FAIL — {sc.message}")
            continue

        for fc in sc.field_checks:
            if not fc.passed:
                print(f"      scope {sc.scope_label}.{fc.field_name}: FAIL — {fc.message}")
            elif verbose:
                print(f"      scope {sc.scope_label}.{fc.field_name}: PASS ({fc.actual})")


def run_validation(results_dir: Path, verbose: bool = False) -> int:
    """Run all validations and return an exit code (0 = all pass, 1 = failures)."""
    print(f"Validating extraction results in: {results_dir}\n")
    print(f"Known test cases: {len(KNOWN_VALUES)}")
    print("=" * 60)

    validations: list[ProjectValidation] = []

    for project_name, expected in sorted(KNOWN_VALUES.items()):
        result_data = load_result(results_dir, project_name)
        if result_data is None:
            v = ProjectValidation(project_name=project_name, found=False)
        else:
            v = validate_project(project_name, expected, result_data)
        validations.append(v)
        print_validation(v, verbose=verbose)

    # Summary
    passed = sum(1 for v in validations if v.passed)
    failed = sum(1 for v in validations if not v.passed)
    not_found = sum(1 for v in validations if not v.found)

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {not_found} not found")
    print("=" * 60)

    return 0 if failed == 0 else 1


def main() -> None:
    """CLI entry point for validation."""
    parser = argparse.ArgumentParser(
        description="Validate extraction results against known audit data",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="data/extracted",
        help="Directory containing extraction JSON results (default: data/extracted)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show passing checks as well as failures",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    exit_code = run_validation(results_dir, verbose=args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
