"""Unit tests for the PDF quote parser.

All tests are pure-Python — no real PDF I/O against the Dropbox folder.
PyMuPDF (fitz) is monkey-patched / avoided via tmp_path or direct helper calls.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.extraction.pdf_parser import (
    ExtractedQuote,
    QuoteExtractionResult,
    QuoteLineItem,
    _clean_decimal,
    _compute_confidence,
    _detect_template,
    _extract_date,
    _extract_grand_total,
    _extract_line_items,
    _extract_payment_terms,
    _extract_quote_number,
    _extract_subtotals,
    extract_quote,
    find_quote_files,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal realistic page-1 text for a T-004A quote
SAMPLE_T004A_TEXT = """\
COMMERCIAL ACOUSTICS
Quote Number: 02537
Date: 03/15/2024

General Contractor: Turner Construction
Contact: John Smith
Project: 123 Main Street, Tampa FL 33601

QTY TYPE DESCRIPTION COST PER UNIT TOTAL
1 ACT-1 Armstrong Dune 1774, 2x2 $45,000.00 $45,000.00
1 AWP-1 Fabric Wall Panels 9,500.00 9,500.00

SUBTOTAL
Material Subtotal $38,000.00
Labor Subtotal $14,000.00
Tax Subtotal $2,280.00
GRAND TOTAL $54,280.00

PAYMENT TERMS
MILESTONE BILLING
"""

SAMPLE_T004B_TEXT = """\
COMMERCIAL ACOUSTICS
ACOUSTIC PANEL FAB & INSTALL
Quote Number: 05906-R1
Quote Date: January 15, 2024

General Contractor: Skanska USA
Contact: Maria Lopez
Project Address: 456 Oak Ave, Orlando FL 32801

QTY TYPE DESCRIPTION COST PER UNIT TOTAL
24 AWP-1 Fabric-wrapped panels 12x12 $850.00 $20,400.00

Material Subtotal $16,800.00
Labor Subtotal $3,600.00
Tax Subtotal $1,008.00
GRAND TOTAL $21,408.00

PAYMENT TERMS
50% DOWN / BALANCE NET 15
"""

SAMPLE_T004E_TEXT = """\
COMMERCIAL ACOUSTICS
SOUND MASKING SYSTEM
Quote Number: 03001
Date: 07/04/2023

QTY TYPE DESCRIPTION COST PER UNIT TOTAL
1 SM Sound Masking System $18,000.00 $18,000.00

GRAND TOTAL $18,000.00

PAYMENT TERMS
NET 30
"""


# ---------------------------------------------------------------------------
# 1. Non-existent file → graceful failure
# ---------------------------------------------------------------------------


class TestExtractQuoteFileErrors:
    """extract_quote returns success=False for files that cannot be opened."""

    def test_nonexistent_file_returns_failure(self) -> None:
        """A path that does not exist must yield success=False with an error."""
        result = extract_quote(Path("/totally/nonexistent/Quote 99999 - Ghost.pdf"))
        assert result.success is False
        assert result.quote is None
        assert result.error is not None
        assert "not found" in result.error.lower() or "no such" in result.error.lower()

    def test_error_message_contains_path(self) -> None:
        """The error message should mention the offending file path."""
        path = Path("/nonexistent/Quote 00001 - Nobody.pdf")
        result = extract_quote(path)
        assert result.success is False
        assert str(path) in (result.error or "")


# ---------------------------------------------------------------------------
# 2. Quote number regex
# ---------------------------------------------------------------------------


class TestExtractQuoteNumber:
    """_extract_quote_number correctly identifies 5-digit quote numbers."""

    def test_plain_five_digit(self) -> None:
        """Standard 5-digit quote number."""
        full, revision = _extract_quote_number("Quote Number: 02537")
        assert full == "02537"
        assert revision is None

    def test_with_revision_r1(self) -> None:
        """Quote number with -R1 suffix."""
        full, revision = _extract_quote_number("Quote 05906-R1 dated today")
        assert full == "05906-R1"
        assert revision == "R1"

    def test_with_revision_r2(self) -> None:
        """Quote number with -R2 suffix."""
        full, revision = _extract_quote_number("05906-R2 is the revision")
        assert full == "05906-R2"
        assert revision == "R2"

    def test_no_match_returns_none(self) -> None:
        """Text with no 5-digit number returns (None, None)."""
        full, revision = _extract_quote_number("No numbers here at all")
        assert full is None
        assert revision is None

    def test_ignores_four_digit_numbers(self) -> None:
        """4-digit numbers should not be matched."""
        full, revision = _extract_quote_number("Invoice 1234 payment due")
        assert full is None

    def test_ignores_six_digit_numbers(self) -> None:
        """6-digit numbers should not be matched as quote numbers."""
        full, revision = _extract_quote_number("Reference 123456 for order")
        assert full is None

    def test_finds_embedded_number(self) -> None:
        """Should find a 5-digit number embedded in surrounding text."""
        full, revision = _extract_quote_number("Please refer to quote 03001 for full details.")
        assert full == "03001"

    def test_full_sample_t004a(self) -> None:
        """Should extract quote number from realistic T-004A text."""
        full, revision = _extract_quote_number(SAMPLE_T004A_TEXT)
        assert full == "02537"
        assert revision is None

    def test_full_sample_t004b(self) -> None:
        """Should extract revised quote number from T-004B text."""
        full, revision = _extract_quote_number(SAMPLE_T004B_TEXT)
        assert full == "05906-R1"
        assert revision == "R1"


# ---------------------------------------------------------------------------
# 3. Template type detection
# ---------------------------------------------------------------------------


class TestDetectTemplate:
    """_detect_template returns the correct template family."""

    def test_t004b_keyword_fab_install(self) -> None:
        """'ACOUSTIC PANEL FAB & INSTALL' signals T-004B."""
        result = _detect_template("ACOUSTIC PANEL FAB & INSTALL\nSome content")
        assert result == "T-004B"

    def test_t004b_partial_keyword(self) -> None:
        """'ACOUSTIC PANEL FAB' alone is enough for T-004B."""
        result = _detect_template("ACOUSTIC PANEL FAB\nContent here")
        assert result == "T-004B"

    def test_t004e_sound_masking(self) -> None:
        """'SOUND MASKING' signals T-004E."""
        result = _detect_template("SOUND MASKING SYSTEM\nQuote details")
        assert result == "T-004E"

    def test_t004e_case_insensitive(self) -> None:
        """Template detection is case-insensitive."""
        result = _detect_template("sound masking system")
        assert result == "T-004E"

    def test_none_for_general_text(self) -> None:
        """Generic text without a template keyword returns None."""
        result = _detect_template("Some random document without keywords")
        assert result is None

    def test_t004b_takes_priority_over_sound_masking(self) -> None:
        """T-004B keyword checked before T-004E in implementation order."""
        # Both keywords in same text — T-004B wins because it appears first
        result = _detect_template("ACOUSTIC PANEL FAB and SOUND MASKING together")
        assert result == "T-004B"

    def test_t004a_not_returned_by_detect_template(self) -> None:
        """_detect_template returns None for T-004A (caller applies fallback)."""
        result = _detect_template("COMMERCIAL ACOUSTICS\nGeneral Contractor quote")
        assert result is None

    def test_sample_t004a_text(self) -> None:
        """No T-004B/E keyword in sample T-004A → None."""
        result = _detect_template(SAMPLE_T004A_TEXT)
        assert result is None

    def test_sample_t004b_text(self) -> None:
        """Sample T-004B text returns T-004B."""
        result = _detect_template(SAMPLE_T004B_TEXT)
        assert result == "T-004B"

    def test_sample_t004e_text(self) -> None:
        """Sample T-004E text returns T-004E."""
        result = _detect_template(SAMPLE_T004E_TEXT)
        assert result == "T-004E"


# ---------------------------------------------------------------------------
# 4. Date parsing
# ---------------------------------------------------------------------------


class TestExtractDate:
    """_extract_date returns the first date-like string found."""

    def test_date_with_label_slash(self) -> None:
        """'Date: MM/DD/YYYY' format."""
        result = _extract_date("Date: 03/15/2024\nOther text")
        assert result == "03/15/2024"

    def test_quote_date_label(self) -> None:
        """'Quote Date:' label variant."""
        result = _extract_date("Quote Date: January 15, 2024")
        assert result == "January 15, 2024"

    def test_bare_date(self) -> None:
        """Standalone MM/DD/YYYY without a label."""
        result = _extract_date("Submitted on 07/04/2023 for approval")
        assert result == "07/04/2023"

    def test_month_name_long(self) -> None:
        """Written-out month name (long form)."""
        result = _extract_date("Date: November 20, 2023")
        assert result == "November 20, 2023"

    def test_month_name_short(self) -> None:
        """Abbreviated month name."""
        result = _extract_date("Date: Jan 5 2024")
        assert result == "Jan 5 2024"

    def test_no_date_returns_none(self) -> None:
        """Text with no date-like string returns None."""
        result = _extract_date("No dates anywhere in this document")
        assert result is None

    def test_hyphen_date_separator(self) -> None:
        """Dates using hyphens as separators (MM-DD-YYYY)."""
        result = _extract_date("Date: 01-15-2024")
        assert result == "01-15-2024"


# ---------------------------------------------------------------------------
# 5. Decimal cleaning
# ---------------------------------------------------------------------------


class TestCleanDecimal:
    """_clean_decimal strips currency formatting and returns a Decimal."""

    def test_plain_number(self) -> None:
        """Plain integer string → Decimal."""
        assert _clean_decimal("1234") == Decimal("1234")

    def test_with_dollar_sign(self) -> None:
        """Leading $ stripped."""
        assert _clean_decimal("$1,234.56") == Decimal("1234.56")

    def test_with_commas(self) -> None:
        """Commas stripped."""
        assert _clean_decimal("45,000.00") == Decimal("45000.00")

    def test_with_whitespace(self) -> None:
        """Leading/trailing whitespace stripped."""
        assert _clean_decimal("  500.00  ") == Decimal("500.00")

    def test_dollar_and_comma_and_space(self) -> None:
        """Combined $ + commas + spaces."""
        assert _clean_decimal("$ 1,000,000.00") == Decimal("1000000.00")

    def test_zero(self) -> None:
        """Zero value."""
        assert _clean_decimal("0.00") == Decimal("0.00")

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert _clean_decimal("") is None

    def test_non_numeric_returns_none(self) -> None:
        """Non-numeric text returns None."""
        assert _clean_decimal("N/A") is None

    def test_only_dollar_sign_returns_none(self) -> None:
        """Just a $ with no number returns None."""
        assert _clean_decimal("$") is None

    def test_decimal_precision_preserved(self) -> None:
        """Full decimal precision is preserved."""
        result = _clean_decimal("$9,999.99")
        assert result == Decimal("9999.99")


# ---------------------------------------------------------------------------
# 6. Payment terms extraction
# ---------------------------------------------------------------------------


class TestExtractPaymentTerms:
    """_extract_payment_terms identifies payment term strings."""

    def test_milestone_billing(self) -> None:
        """MILESTONE BILLING detected."""
        result = _extract_payment_terms("PAYMENT TERMS\nMILESTONE BILLING\n")
        assert result is not None
        assert "MILESTONE" in result

    def test_50_down_balance_net_15(self) -> None:
        """50% DOWN / BALANCE NET 15 detected."""
        result = _extract_payment_terms("50% DOWN / BALANCE NET 15")
        assert result is not None
        assert "50%" in result
        assert "NET 15" in result

    def test_net_30(self) -> None:
        """NET 30 detected."""
        result = _extract_payment_terms("Terms: NET 30 days from invoice")
        assert result is not None
        assert "NET 30" in result

    def test_net_15(self) -> None:
        """NET 15 detected."""
        result = _extract_payment_terms("Payment: NET 15")
        assert result is not None
        assert "NET 15" in result

    def test_50_deposit(self) -> None:
        """50% DEPOSIT variant detected."""
        result = _extract_payment_terms("Requires 50% DEPOSIT before work begins")
        assert result is not None
        assert "50%" in result

    def test_case_insensitive(self) -> None:
        """Payment term detection is case-insensitive."""
        result = _extract_payment_terms("milestone billing applies")
        assert result is not None

    def test_no_match_returns_none(self) -> None:
        """Text with no payment term keywords returns None."""
        result = _extract_payment_terms("Please contact us for payment details")
        assert result is None

    def test_milestone_takes_priority_over_net(self) -> None:
        """MILESTONE BILLING is matched before generic NET terms."""
        text = "MILESTONE BILLING — NET 30 applies after milestone"
        result = _extract_payment_terms(text)
        assert result is not None
        assert "MILESTONE" in result


# ---------------------------------------------------------------------------
# 7. Grand total extraction
# ---------------------------------------------------------------------------


class TestExtractGrandTotal:
    """_extract_grand_total finds the quote's grand total amount."""

    def test_grand_total_label(self) -> None:
        """'GRAND TOTAL' label followed by amount."""
        result = _extract_grand_total("GRAND TOTAL $54,280.00")
        assert result == Decimal("54280.00")

    def test_project_total_label(self) -> None:
        """'PROJECT TOTAL' label."""
        result = _extract_grand_total("PROJECT TOTAL $21,408.00")
        assert result == Decimal("21408.00")

    def test_total_label_standalone(self) -> None:
        """'TOTAL' on its own line."""
        result = _extract_grand_total("TOTAL $18,000.00")
        assert result == Decimal("18000.00")

    def test_no_total_returns_none(self) -> None:
        """Text without a total label returns None."""
        result = _extract_grand_total("Subtotals only, no grand total here")
        assert result is None


# ---------------------------------------------------------------------------
# 8. Subtotals extraction
# ---------------------------------------------------------------------------


class TestExtractSubtotals:
    """_extract_subtotals parses material, labor, and tax subtotals."""

    def test_all_three_subtotals(self) -> None:
        """All three subtotals parsed from sample T-004A text."""
        mat, lab, tax = _extract_subtotals(SAMPLE_T004A_TEXT)
        assert mat == Decimal("38000.00")
        assert lab == Decimal("14000.00")
        assert tax == Decimal("2280.00")

    def test_missing_subtotals_return_none(self) -> None:
        """Text without subtotal labels returns (None, None, None)."""
        mat, lab, tax = _extract_subtotals("No structured data here")
        assert mat is None
        assert lab is None
        assert tax is None


# ---------------------------------------------------------------------------
# 9. Confidence scoring
# ---------------------------------------------------------------------------


class TestComputeConfidence:
    """_compute_confidence produces correct scores for various combinations."""

    def test_all_fields_present(self) -> None:
        """All four signals → confidence 1.0."""
        score = _compute_confidence(
            quote_number="02537",
            quote_date="03/15/2024",
            grand_total=Decimal("54280.00"),
            line_items=[QuoteLineItem()],
        )
        assert score == 1.0

    def test_only_quote_number(self) -> None:
        """Quote number only → 0.3."""
        score = _compute_confidence(
            quote_number="02537",
            quote_date=None,
            grand_total=None,
            line_items=[],
        )
        assert score == pytest.approx(0.3)

    def test_quote_number_and_date(self) -> None:
        """Quote number + date → 0.5."""
        score = _compute_confidence(
            quote_number="02537",
            quote_date="03/15/2024",
            grand_total=None,
            line_items=[],
        )
        assert score == pytest.approx(0.5)

    def test_no_fields(self) -> None:
        """No signals → 0.0."""
        score = _compute_confidence(
            quote_number=None,
            quote_date=None,
            grand_total=None,
            line_items=[],
        )
        assert score == pytest.approx(0.0)

    def test_grand_total_and_items_no_number(self) -> None:
        """Grand total + line items but no quote number → 0.5."""
        score = _compute_confidence(
            quote_number=None,
            quote_date=None,
            grand_total=Decimal("1000.00"),
            line_items=[QuoteLineItem()],
        )
        assert score == pytest.approx(0.5)

    def test_score_capped_at_one(self) -> None:
        """Score never exceeds 1.0 regardless of inputs."""
        score = _compute_confidence("x", "y", Decimal("1"), [QuoteLineItem()] * 10)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# 10. Line items parsing
# ---------------------------------------------------------------------------


class TestExtractLineItems:
    """_extract_line_items parses the QTY/TYPE/DESCRIPTION/COST/TOTAL table."""

    def test_parses_items_from_sample_t004a(self) -> None:
        """Should find line items in the T-004A sample text."""
        items = _extract_line_items(SAMPLE_T004A_TEXT)
        # At least one item expected
        assert len(items) >= 1
        item = items[0]
        assert item.qty is not None
        assert item.item_type is not None

    def test_parses_items_from_sample_t004b(self) -> None:
        """Should find line items in the T-004B sample text."""
        items = _extract_line_items(SAMPLE_T004B_TEXT)
        assert len(items) >= 1
        item = items[0]
        assert item.qty == Decimal("24")
        assert item.total == Decimal("20400.00")

    def test_empty_text_returns_empty_list(self) -> None:
        """Text with no table structure returns an empty list."""
        items = _extract_line_items("No table here at all")
        assert items == []

    def test_item_type_uppercased(self) -> None:
        """Item type codes are stored in uppercase."""
        text = (
            "QTY TYPE DESCRIPTION COST PER UNIT TOTAL\n1 act-1 Ceiling tile 45.00 45.00\nSUBTOTAL\n"
        )
        items = _extract_line_items(text)
        if items:
            assert items[0].item_type == items[0].item_type.upper()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 11. Pydantic model validation
# ---------------------------------------------------------------------------


class TestQuoteLineItem:
    """QuoteLineItem model validation."""

    def test_all_fields_none_is_valid(self) -> None:
        """A QuoteLineItem with all None fields is valid."""
        item = QuoteLineItem()
        assert item.qty is None
        assert item.item_type is None

    def test_populated_fields(self) -> None:
        """QuoteLineItem stores typed values correctly."""
        item = QuoteLineItem(
            qty=Decimal("2"),
            item_type="ACT-1",
            description="Armstrong Dune 1774",
            cost_per_unit=Decimal("45000.00"),
            total=Decimal("90000.00"),
        )
        assert item.qty == Decimal("2")
        assert item.item_type == "ACT-1"
        assert item.total == Decimal("90000.00")


class TestExtractedQuote:
    """ExtractedQuote model validation."""

    def test_minimal_valid_quote(self) -> None:
        """A quote requires only source_file."""
        q = ExtractedQuote(source_file="/path/to/file.pdf")
        assert q.source_file == "/path/to/file.pdf"
        assert q.line_items == []
        assert q.extraction_confidence == 0.0

    def test_full_quote(self) -> None:
        """A fully-populated quote round-trips through model_dump."""
        q = ExtractedQuote(
            quote_number="02537",
            revision=None,
            quote_date="03/15/2024",
            template_type="T-004A",
            client_name="Turner Construction",
            project_address="123 Main Street, Tampa FL 33601",
            gc_name="Turner Construction",
            gc_contact="John Smith",
            line_items=[
                QuoteLineItem(
                    qty=Decimal("1"),
                    item_type="ACT-1",
                    description="Armstrong Dune 1774",
                    cost_per_unit=Decimal("45000.00"),
                    total=Decimal("45000.00"),
                )
            ],
            subtotal_material=Decimal("38000.00"),
            subtotal_labor=Decimal("14000.00"),
            subtotal_tax=Decimal("2280.00"),
            grand_total=Decimal("54280.00"),
            payment_terms="MILESTONE BILLING",
            source_file="/path/to/Quote 02537 - Turner Construction.pdf",
            extraction_confidence=1.0,
        )
        dumped = q.model_dump(mode="json")
        assert dumped["quote_number"] == "02537"
        assert dumped["template_type"] == "T-004A"
        assert len(dumped["line_items"]) == 1


class TestQuoteExtractionResult:
    """QuoteExtractionResult model validation."""

    def test_failed_result(self) -> None:
        """Failed result has no quote."""
        result = QuoteExtractionResult(success=False, error="File not found: x.pdf")
        assert result.success is False
        assert result.quote is None
        assert "not found" in (result.error or "")

    def test_successful_result(self) -> None:
        """Successful result carries an ExtractedQuote."""
        q = ExtractedQuote(source_file="/tmp/q.pdf")
        result = QuoteExtractionResult(success=True, quote=q)
        assert result.success is True
        assert result.quote is not None
        assert result.error is None


# ---------------------------------------------------------------------------
# 12. find_quote_files
# ---------------------------------------------------------------------------


class TestFindQuoteFiles:
    """find_quote_files walks a directory and returns quote PDFs."""

    def test_finds_matching_files(self, tmp_path: Path) -> None:
        """Files named 'Quote *.pdf' are returned."""
        project_dir = tmp_path / "Acme Corp"
        project_dir.mkdir()
        (project_dir / "Quote 02537 - Acme Corp.pdf").write_bytes(b"%PDF fake")
        (project_dir / "Quote 05906-R1 - Acme Corp.pdf").write_bytes(b"%PDF fake")

        results = find_quote_files(tmp_path)
        assert len(results) == 2

    def test_returns_folder_name(self, tmp_path: Path) -> None:
        """Second element of tuple is the parent folder name."""
        folder = tmp_path / "Turner Construction"
        folder.mkdir()
        (folder / "Quote 12345 - Turner Construction.pdf").write_bytes(b"%PDF")

        results = find_quote_files(tmp_path)
        assert len(results) == 1
        path, folder_name = results[0]
        assert folder_name == "Turner Construction"

    def test_ignores_non_quote_pdfs(self, tmp_path: Path) -> None:
        """PDFs not starting with 'Quote ' are ignored."""
        folder = tmp_path / "Project"
        folder.mkdir()
        (folder / "Quote 11111 - Client.pdf").write_bytes(b"%PDF")
        (folder / "Vendor Quote 22222.pdf").write_bytes(b"%PDF")
        (folder / "Drawing A101.pdf").write_bytes(b"%PDF")
        (folder / "ITB.pdf").write_bytes(b"%PDF")

        results = find_quote_files(tmp_path)
        assert len(results) == 1
        assert results[0][0].name == "Quote 11111 - Client.pdf"

    def test_ignores_non_pdf_files(self, tmp_path: Path) -> None:
        """Non-PDF files named 'Quote *' are not returned."""
        folder = tmp_path / "Project"
        folder.mkdir()
        (folder / "Quote 99999 - Client.xlsx").write_bytes(b"fake xlsx")

        results = find_quote_files(tmp_path)
        assert results == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        """No files → empty list."""
        results = find_quote_files(tmp_path)
        assert results == []

    def test_nonexistent_directory(self) -> None:
        """Non-existent source_dir → empty list, no exception."""
        results = find_quote_files(Path("/nonexistent/path/does/not/exist"))
        assert results == []

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        """Finds quote PDFs in nested subdirectories."""
        deep = tmp_path / "2024" / "Q1" / "Project Alpha"
        deep.mkdir(parents=True)
        (deep / "Quote 55555 - Alpha LLC.pdf").write_bytes(b"%PDF")

        results = find_quote_files(tmp_path)
        assert len(results) == 1
        assert results[0][0].name == "Quote 55555 - Alpha LLC.pdf"

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Results are sorted by file path."""
        for name in ("Zebra", "Alpha", "Middle"):
            d = tmp_path / name
            d.mkdir()
            (d / f"Quote 00001 - {name}.pdf").write_bytes(b"%PDF")

        results = find_quote_files(tmp_path)
        paths = [p for p, _ in results]
        assert paths == sorted(paths)

    def test_multiple_projects(self, tmp_path: Path) -> None:
        """Each project folder is scanned independently."""
        for project, num in (("Alpha Corp", "10001"), ("Beta Inc", "20002")):
            d = tmp_path / project
            d.mkdir()
            (d / f"Quote {num} - {project}.pdf").write_bytes(b"%PDF")

        results = find_quote_files(tmp_path)
        assert len(results) == 2
        folder_names = {fn for _, fn in results}
        assert "Alpha Corp" in folder_names
        assert "Beta Inc" in folder_names
