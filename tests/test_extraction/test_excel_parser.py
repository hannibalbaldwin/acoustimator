"""Unit tests for the Excel parser extraction module.

Tests Pydantic model validation, cell formatting, file discovery, and edge
cases. Does NOT test actual Claude API calls — that is an integration test.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from src.extraction.excel_parser import (
    ExtractedProject,
    ExtractedScope,
    ExtractionResult,
    find_buildup_files,
    format_cell_contents,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_scope_data() -> dict:
    """Minimal valid scope data."""
    return {
        "scope_type": "ACT",
        "tag": "ACT-1",
        "product_name": "Armstrong Dune 1774",
        "square_footage": Decimal("4200"),
        "material_cost": Decimal("5250.00"),
        "markup_pct": Decimal("0.30"),
    }


@pytest.fixture()
def sample_project_data(sample_scope_data: dict) -> dict:
    """Minimal valid project data."""
    return {
        "project_name": "Grant Thornton",
        "folder_name": "Grant Thornton",
        "source_file": "/data/raw/Grant Thornton/buildup.xlsx",
        "format_type": "A",
        "scopes": [sample_scope_data],
    }


@pytest.fixture()
def sample_result_data(sample_project_data: dict) -> dict:
    """Minimal valid extraction result data."""
    return {
        "success": True,
        "project": sample_project_data,
        "tokens_used": 2000,
    }


# ---------------------------------------------------------------------------
# ExtractedScope model tests
# ---------------------------------------------------------------------------


class TestExtractedScope:
    """Tests for the ExtractedScope Pydantic model."""

    def test_valid_scope(self, sample_scope_data: dict) -> None:
        """A scope with all required fields should be created successfully."""
        scope = ExtractedScope(**sample_scope_data)
        assert scope.scope_type == "ACT"
        assert scope.product_name == "Armstrong Dune 1774"
        assert scope.square_footage == Decimal("4200")

    def test_scope_type_required(self, sample_scope_data: dict) -> None:
        """scope_type is required and cannot be omitted."""
        del sample_scope_data["scope_type"]
        with pytest.raises((ValueError, TypeError)):
            ExtractedScope(**sample_scope_data)

    def test_scope_decimal_precision(self) -> None:
        """Decimal values should preserve full precision."""
        scope = ExtractedScope(
            scope_type="ACT",
            tag="ACT-1",
            product_name="Test",
            square_footage=Decimal("1234.5678"),
            material_cost=Decimal("9999.99"),
            markup_pct=Decimal("0.3333"),
        )
        assert scope.square_footage == Decimal("1234.5678")
        assert scope.markup_pct == Decimal("0.3333")

    def test_scope_optional_fields(self) -> None:
        """Scope should accept minimal data with only required fields."""
        scope = ExtractedScope(scope_type="AWP")
        assert scope.scope_type == "AWP"
        assert scope.product_name is None

    def test_scope_all_types(self) -> None:
        """All known scope types should be accepted."""
        for scope_type in ("ACT", "AWP", "AP", "Baffles", "FW", "SM", "WW", "RPG", "Other"):
            scope = ExtractedScope(scope_type=scope_type)
            assert scope.scope_type == scope_type


# ---------------------------------------------------------------------------
# ExtractedProject model tests
# ---------------------------------------------------------------------------


class TestExtractedProject:
    """Tests for the ExtractedProject Pydantic model."""

    def test_valid_project(self, sample_project_data: dict) -> None:
        """A project with all fields should be created successfully."""
        project = ExtractedProject(**sample_project_data)
        assert project.project_name == "Grant Thornton"
        assert project.format_type == "A"
        assert len(project.scopes) == 1

    def test_project_multiple_scopes(self, sample_project_data: dict) -> None:
        """A project can contain multiple scopes."""
        sample_project_data["scopes"].append(
            {
                "scope_type": "AWP",
                "tag": "AWP-1",
                "product_name": "Fabric Wall Panel",
                "square_footage": Decimal("800"),
            }
        )
        project = ExtractedProject(**sample_project_data)
        assert len(project.scopes) == 2
        assert project.scopes[1].scope_type == "AWP"

    def test_project_empty_scopes(self, sample_project_data: dict) -> None:
        """A project with an empty scopes list should still be valid."""
        sample_project_data["scopes"] = []
        project = ExtractedProject(**sample_project_data)
        assert project.scopes == []

    def test_project_format_types(self) -> None:
        """All known format types should be valid."""
        for fmt in ("A", "B", "C", "D"):
            project = ExtractedProject(
                project_name="Test",
                folder_name="Test",
                source_file="test.xlsx",
                format_type=fmt,
                scopes=[],
            )
            assert project.format_type == fmt


# ---------------------------------------------------------------------------
# ExtractionResult model tests
# ---------------------------------------------------------------------------


class TestExtractionResult:
    """Tests for the ExtractionResult Pydantic model."""

    def test_successful_result(self, sample_result_data: dict) -> None:
        """A successful result includes a project and token counts."""
        result = ExtractionResult(**sample_result_data)
        assert result.success is True
        assert result.project is not None
        assert result.tokens_used == 2000

    def test_failed_result(self) -> None:
        """A failed result includes an error message and no project data."""
        result = ExtractionResult(
            success=False,
            error="Unsupported format: no recognizable buildup structure",
        )
        assert result.success is False
        assert result.error is not None
        assert "Unsupported format" in result.error

    def test_result_token_counts_default(self) -> None:
        """Token counts should default to zero if not provided."""
        result = ExtractionResult(
            success=False,
            error="test error",
        )
        assert result.tokens_used == 0

    def test_result_serialization(self, sample_result_data: dict) -> None:
        """Result should round-trip through model_dump without data loss."""
        result = ExtractionResult(**sample_result_data)
        dumped = result.model_dump(mode="json")
        assert dumped["success"] is True
        assert dumped["project"]["project_name"] == "Grant Thornton"


# ---------------------------------------------------------------------------
# format_cell_contents tests
# ---------------------------------------------------------------------------


class TestFormatCellContents:
    """Tests for the cell content formatting function."""

    def test_string_passthrough(self) -> None:
        """Plain strings should pass through unchanged."""
        assert format_cell_contents("Hello World") == "Hello World"

    def test_numeric_value(self) -> None:
        """Numeric values should be converted to string representation."""
        result = format_cell_contents(42)
        assert "42" in str(result)

    def test_float_value(self) -> None:
        """Float values should be formatted as strings."""
        result = format_cell_contents(3.14)
        assert "3.14" in str(result)

    def test_none_value(self) -> None:
        """None should produce an empty string."""
        result = format_cell_contents(None)
        assert result == ""

    def test_boolean_value(self) -> None:
        """Boolean values should be stringified."""
        result = format_cell_contents(True)
        assert result == "True"

    def test_whitespace_handling(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        result = format_cell_contents("  spaced out  ")
        assert result == "spaced out"

    def test_multiline_content(self) -> None:
        """Multi-line cell content should be preserved."""
        content = "Line 1\nLine 2\nLine 3"
        result = format_cell_contents(content)
        assert "Line 1" in result
        assert "Line 2" in result


# ---------------------------------------------------------------------------
# find_buildup_files tests
# ---------------------------------------------------------------------------


class TestFindBuildupFiles:
    """Tests for the file discovery and filtering function.

    find_buildup_files returns list[tuple[Path, str]] where the tuple is
    (file_path, folder_name).
    """

    def test_finds_xlsx_files(self, tmp_path: Path) -> None:
        """Should discover .xlsx files in the directory tree."""
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir()
        (project_dir / "buildup.xlsx").write_bytes(b"fake xlsx content")

        files = find_buildup_files(tmp_path)
        assert len(files) >= 1
        assert any(path.name == "buildup.xlsx" for path, _ in files)

    def test_ignores_non_xlsx(self, tmp_path: Path) -> None:
        """Should skip non-.xlsx files."""
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir()
        (project_dir / "quote.pdf").write_bytes(b"pdf content")
        (project_dir / "notes.docx").write_bytes(b"docx content")
        (project_dir / "buildup.xlsx").write_bytes(b"xlsx content")

        files = find_buildup_files(tmp_path)
        assert all(path.suffix == ".xlsx" for path, _ in files)

    def test_skips_vendor_quotes(self, tmp_path: Path) -> None:
        """Should filter out vendor quote Excel files."""
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir()
        (project_dir / "buildup.xlsx").write_bytes(b"real buildup")
        (project_dir / "vendor_quote_armstrong.xlsx").write_bytes(b"vendor quote")
        (project_dir / "Vendor Quote - Knauf.xlsx").write_bytes(b"vendor quote")

        files = find_buildup_files(tmp_path)
        names = [path.name.lower() for path, _ in files]
        assert not any("vendor" in n for n in names)

    def test_skips_template_files(self, tmp_path: Path) -> None:
        """Should filter out template files (T-004A, T-004B, etc)."""
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir()
        (project_dir / "buildup.xlsx").write_bytes(b"real buildup")
        (project_dir / "T-004A Quote Template.xlsx").write_bytes(b"template")
        (project_dir / "T-004B.xlsx").write_bytes(b"template")

        files = find_buildup_files(tmp_path)
        names = [path.name for path, _ in files]
        assert not any("T-004" in n for n in names)

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        """Should skip hidden files (prefixed with ~$ or .)."""
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir()
        (project_dir / "buildup.xlsx").write_bytes(b"real buildup")
        (project_dir / "~$buildup.xlsx").write_bytes(b"temp lock file")

        files = find_buildup_files(tmp_path)
        names = [path.name for path, _ in files]
        assert not any(n.startswith("~$") for n in names)

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Should return an empty list for a directory with no .xlsx files."""
        files = find_buildup_files(tmp_path)
        assert files == []

    def test_nonexistent_directory(self) -> None:
        """Should handle a nonexistent directory gracefully."""
        files = find_buildup_files(Path("/nonexistent/path/that/does/not/exist"))
        assert files == []

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        """Should find .xlsx files in nested subdirectories."""
        nested = tmp_path / "Projects" / "Sub" / "Deep"
        nested.mkdir(parents=True)
        (nested / "buildup.xlsx").write_bytes(b"deep buildup")

        files = find_buildup_files(tmp_path)
        assert len(files) >= 1

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Returned files should be in a deterministic order."""
        for name in ("Zebra", "Alpha", "Middle"):
            d = tmp_path / name
            d.mkdir()
            (d / "buildup.xlsx").write_bytes(b"content")

        files = find_buildup_files(tmp_path)
        paths = [path for path, _ in files]
        assert paths == sorted(paths)
