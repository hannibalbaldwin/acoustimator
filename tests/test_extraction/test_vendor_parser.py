"""Unit tests for the vendor quote parser.

Tests cover:
  - Vendor name detection from text strings
  - Decimal cleaning (currency, ranges, unit suffixes)
  - find_vendor_quote_files directory walking and filtering
  - Text-extraction path with a mocked fitz document
  - Model instantiation and validation

No real API calls are made — all Claude API interactions are mocked.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.extraction.vendor_parser import (
    KNOWN_VENDORS,
    ExtractedVendorQuote,
    VendorExtractionResult,
    VendorLineItem,
    clean_decimal,
    detect_vendor,
    extract_vendor_quote,
    extract_vendor_quote_text,
    extract_vendor_quote_vision,
    find_vendor_quote_files,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_fitz_page(text: str) -> MagicMock:
    """Return a mock fitz Page whose get_text() returns *text*."""
    page = MagicMock()
    page.get_text.return_value = text
    return page


def _make_mock_fitz_doc(pages_text: list[str]) -> MagicMock:
    """Return a mock fitz.Document with the given per-page texts."""
    doc = MagicMock()
    pages = [_make_mock_fitz_page(t) for t in pages_text]
    doc.__len__.return_value = len(pages)
    doc.__iter__.return_value = iter(pages)
    doc.__getitem__ = lambda self, i: pages[i]
    doc.close = MagicMock()
    return doc


# ---------------------------------------------------------------------------
# detect_vendor
# ---------------------------------------------------------------------------


class TestDetectVendor:
    """Tests for vendor name detection from arbitrary text."""

    def test_detects_mdc(self) -> None:
        """MDC should map to 'MDC Interior Solutions'."""
        assert detect_vendor("MDC Interior Solutions — Quote #12345") == "MDC Interior Solutions"

    def test_detects_foundation_building(self) -> None:
        """'Foundation Building' should map to 'FBM' (longer key wins)."""
        assert detect_vendor("Foundation Building Materials, Inc.") == "FBM"

    def test_detects_fbm_short(self) -> None:
        """Bare 'FBM' should also match."""
        assert detect_vendor("FBM Tampa Distribution Center") == "FBM"

    def test_detects_gatorgyp(self) -> None:
        """GatorGyp should be detected by exact name."""
        assert detect_vendor("GatorGyp LLC — Order Confirmation") == "GatorGyp"

    def test_detects_gms_acoustics(self) -> None:
        """'GMS Acoustics' is an alias for GatorGyp."""
        assert detect_vendor("GMS Acoustics of Central Florida") == "GatorGyp"

    def test_detects_snap_tex(self) -> None:
        """Snap-Tex (with hyphen) should be detected."""
        assert detect_vendor("Snap-Tex Track Systems Quote") == "Snap-Tex"

    def test_detects_snaptex_no_hyphen(self) -> None:
        """SnapTex (no hyphen) should also be detected."""
        assert detect_vendor("SnapTex fabric track") == "Snap-Tex"

    def test_detects_rpg(self) -> None:
        """RPG should map to 'RPG Diffusor Systems'."""
        result = detect_vendor("RPG Diffusor Systems — QRD Panel Quote")
        assert result == "RPG Diffusor Systems"

    def test_detects_arktura(self) -> None:
        """Arktura should be detected case-insensitively."""
        assert detect_vendor("ARKTURA Vapor 1x6 quote") == "Arktura"

    def test_detects_9wood(self) -> None:
        """9Wood should be detected."""
        assert detect_vendor("9Wood Wood Ceilings Price List") == "9Wood"

    def test_detects_armstrong(self) -> None:
        """Armstrong should be detected from filename-style text."""
        assert detect_vendor("Armstrong_Dune_Quote_2024") == "Armstrong"

    def test_detects_usg(self) -> None:
        """USG should be detected."""
        assert detect_vendor("USG Ceilings — Grid Pricing") == "USG"

    def test_returns_none_for_unknown(self) -> None:
        """Unknown vendor text should return None."""
        assert detect_vendor("Some Random Supplier LLC") is None

    def test_case_insensitive(self) -> None:
        """Vendor detection should be case-insensitive."""
        assert detect_vendor("mdc interior solutions") == "MDC Interior Solutions"

    def test_all_known_vendors_detectable(self) -> None:
        """Every key in KNOWN_VENDORS should be detectable from a string."""
        for key, canonical in KNOWN_VENDORS.items():
            result = detect_vendor(f"This is a quote from {key} Inc.")
            assert result == canonical, f"Failed to detect '{key}' → '{canonical}'"

    def test_empty_string(self) -> None:
        """Empty string should return None without raising."""
        assert detect_vendor("") is None


# ---------------------------------------------------------------------------
# clean_decimal
# ---------------------------------------------------------------------------


class TestCleanDecimal:
    """Tests for the decimal cleaning / parsing helper."""

    def test_plain_number(self) -> None:
        """Plain numeric strings should parse cleanly."""
        assert clean_decimal("42") == Decimal("42")

    def test_dollar_sign(self) -> None:
        """Dollar signs should be stripped."""
        assert clean_decimal("$1234.56") == Decimal("1234.56")

    def test_comma_thousands(self) -> None:
        """Thousands separators should be stripped."""
        assert clean_decimal("$12,345.00") == Decimal("12345.00")

    def test_unit_suffix(self) -> None:
        """Unit suffixes like '/CTN' should be stripped."""
        assert clean_decimal("$42.50/CTN") == Decimal("42.50")

    def test_unit_suffix_ea(self) -> None:
        """/EA suffix should be stripped."""
        assert clean_decimal("$10.00/EA") == Decimal("10.00")

    def test_parenthetical_negative(self) -> None:
        """Parenthetical negatives like (100.00) should parse as negative."""
        assert clean_decimal("(100.00)") == Decimal("-100.00")

    def test_percent_stripped(self) -> None:
        """Percent signs should be stripped (value preserved)."""
        assert clean_decimal("6%") == Decimal("6")

    def test_zero(self) -> None:
        """Zero should parse cleanly."""
        assert clean_decimal("0") == Decimal("0")

    def test_zero_dollar(self) -> None:
        """'$0.00' should parse to Decimal zero."""
        assert clean_decimal("$0.00") == Decimal("0.00")

    def test_empty_string(self) -> None:
        """Empty string should return None."""
        assert clean_decimal("") is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only string should return None."""
        assert clean_decimal("   ") is None

    def test_non_numeric(self) -> None:
        """Non-numeric string should return None."""
        assert clean_decimal("N/A") is None

    def test_large_amount(self) -> None:
        """Large dollar amounts should parse correctly."""
        assert clean_decimal("$1,234,567.89") == Decimal("1234567.89")

    def test_decimal_precision(self) -> None:
        """Four decimal places should be preserved."""
        assert clean_decimal("0.1234") == Decimal("0.1234")


# ---------------------------------------------------------------------------
# VendorLineItem model
# ---------------------------------------------------------------------------


class TestVendorLineItem:
    """Tests for the VendorLineItem Pydantic model."""

    def test_all_fields(self) -> None:
        """VendorLineItem should accept all fields."""
        item = VendorLineItem(
            product="Dune 1774 2x2",
            sku="270-24",
            quantity=Decimal("48"),
            unit="CTN",
            unit_cost=Decimal("42.50"),
            total=Decimal("2040.00"),
            notes="Color: White",
        )
        assert item.product == "Dune 1774 2x2"
        assert item.quantity == Decimal("48")
        assert item.unit == "CTN"

    def test_minimal_item(self) -> None:
        """All fields except those set are optional."""
        item = VendorLineItem()
        assert item.product is None
        assert item.sku is None
        assert item.total is None

    def test_none_fields(self) -> None:
        """Explicitly-None fields should be stored as None."""
        item = VendorLineItem(product=None, sku=None)
        assert item.product is None


# ---------------------------------------------------------------------------
# ExtractedVendorQuote model
# ---------------------------------------------------------------------------


class TestExtractedVendorQuote:
    """Tests for the ExtractedVendorQuote Pydantic model."""

    def test_minimal_quote(self) -> None:
        """Quote requires only source_file, extraction_method."""
        q = ExtractedVendorQuote(
            source_file="/tmp/test.pdf",
            extraction_method="text",
        )
        assert q.vendor_name is None
        assert q.items == []
        assert q.extraction_confidence == 0.0

    def test_full_quote(self) -> None:
        """All fields should round-trip correctly."""
        q = ExtractedVendorQuote(
            vendor_name="MDC Interior Solutions",
            quote_number="Q-2024-001",
            quote_date="01/15/2024",
            items=[
                VendorLineItem(
                    product="Zintra Panel 2x4",
                    sku="ZP-24",
                    quantity=Decimal("20"),
                    unit="EA",
                    unit_cost=Decimal("85.00"),
                    total=Decimal("1700.00"),
                )
            ],
            freight=Decimal("180.00"),
            sales_tax=Decimal("0"),
            grand_total=Decimal("1880.00"),
            lead_time="3-4 weeks",
            source_file="/tmp/mdc_quote.pdf",
            extraction_method="text",
            extraction_confidence=0.75,
        )
        assert q.vendor_name == "MDC Interior Solutions"
        assert len(q.items) == 1
        assert q.grand_total == Decimal("1880.00")
        assert q.freight == Decimal("180.00")

    def test_serialization(self) -> None:
        """ExtractedVendorQuote should serialize to dict without loss."""
        q = ExtractedVendorQuote(
            vendor_name="GatorGyp",
            source_file="/tmp/gator.pdf",
            extraction_method="vision",
            extraction_confidence=0.9,
        )
        d = q.model_dump(mode="json")
        assert d["vendor_name"] == "GatorGyp"
        assert d["extraction_method"] == "vision"


# ---------------------------------------------------------------------------
# VendorExtractionResult model
# ---------------------------------------------------------------------------


class TestVendorExtractionResult:
    """Tests for the VendorExtractionResult container model."""

    def test_success_result(self) -> None:
        """A successful result should carry a quote and zero error."""
        q = ExtractedVendorQuote(
            source_file="/tmp/test.pdf",
            extraction_method="text",
        )
        result = VendorExtractionResult(success=True, quote=q)
        assert result.success is True
        assert result.error is None
        assert result.tokens_used == 0

    def test_failure_result(self) -> None:
        """A failed result should carry an error and no quote."""
        result = VendorExtractionResult(
            success=False,
            error="File not found: /tmp/missing.pdf",
        )
        assert result.success is False
        assert result.quote is None
        assert "not found" in (result.error or "")

    def test_tokens_used_defaults_zero(self) -> None:
        """tokens_used should default to 0."""
        result = VendorExtractionResult(success=False, error="oops")
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# extract_vendor_quote_text — mocked fitz
# ---------------------------------------------------------------------------


SAMPLE_QUOTE_TEXT = """\
MDC Interior Solutions
12345 Commerce Way, Atlanta, GA

Quote #Q-2024-0567
Date: 03/15/2024
Bill To: Residential Acoustics LLC DBA Commercial Acoustics
6301 N Florida Ave, Tampa, FL 33604

Item              SKU         Qty   Unit   Unit Price   Extended
Zintra Panel 2x4  ZP24-0010   20    EA     $85.00       $1,700.00
Zintra Baffle 1x4 ZB14-0020   30    EA     $62.00       $1,860.00

Freight:  $225.00
Sales Tax: $0.00
Grand Total: $3,785.00

Lead Time: 3-4 weeks ARO
"""


class TestExtractVendorQuoteText:
    """Tests for the synchronous text-extraction path."""

    def test_text_extraction_success(self, tmp_path: Path) -> None:
        """A valid-looking text PDF should return a successful result."""
        pdf_file = tmp_path / "mdc_quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.vendor_name == "MDC Interior Solutions"
        assert result.quote.extraction_method == "text"

    def test_text_extraction_detects_quote_number(self, tmp_path: Path) -> None:
        """Quote number should be extracted from the text."""
        pdf_file = tmp_path / "quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.quote_number is not None

    def test_text_extraction_detects_date(self, tmp_path: Path) -> None:
        """Quote date should be extracted from the text."""
        pdf_file = tmp_path / "quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.quote_date == "03/15/2024"

    def test_text_extraction_detects_freight(self, tmp_path: Path) -> None:
        """Freight charge should be extracted as a Decimal."""
        pdf_file = tmp_path / "quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.freight == Decimal("225.00")

    def test_text_extraction_detects_grand_total(self, tmp_path: Path) -> None:
        """Grand total should be extracted as a Decimal."""
        pdf_file = tmp_path / "quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.grand_total == Decimal("3785.00")

    def test_text_extraction_detects_lead_time(self, tmp_path: Path) -> None:
        """Lead time should be extracted from the text."""
        pdf_file = tmp_path / "quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.lead_time is not None
        assert "week" in result.quote.lead_time.lower()

    def test_text_extraction_low_content_gives_low_confidence(self, tmp_path: Path) -> None:
        """Very short text should yield low extraction confidence."""
        pdf_file = tmp_path / "sparse.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc(["MDC"])  # < 50 chars

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.extraction_confidence < 0.4

    def test_text_extraction_file_not_found(self) -> None:
        """A missing file should return a failure result."""
        with patch(
            "src.extraction.vendor_parser.fitz.open",
            side_effect=FileNotFoundError("no such file"),
        ):
            result = extract_vendor_quote_text(Path("/tmp/nonexistent_quote.pdf"))

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_text_extraction_source_file_set(self, tmp_path: Path) -> None:
        """source_file on the quote should match the input path."""
        pdf_file = tmp_path / "vendor_quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.source_file == str(pdf_file)

    def test_text_extraction_vendor_from_filename(self, tmp_path: Path) -> None:
        """If header text doesn't name the vendor, the filename should be used."""
        pdf_file = tmp_path / "Arktura_order_2024.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        # Body text has no vendor name
        body_text = (
            "Quote #Q-2024-999\nDate: 04/01/2024\n"
            "Grand Total: $5,000.00\n"
            "Some product  SKU-99  10  EA  $500.00  $5,000.00\n"
        )
        mock_doc = _make_mock_fitz_doc([body_text])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = extract_vendor_quote_text(pdf_file)

        assert result.quote is not None
        assert result.quote.vendor_name == "Arktura"


# ---------------------------------------------------------------------------
# extract_vendor_quote_vision — mocked API
# ---------------------------------------------------------------------------


class TestExtractVendorQuoteVision:
    """Tests for the async vision-extraction path (API mocked)."""

    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        """Return a mock AsyncAnthropic client."""
        client = MagicMock()
        client.messages = MagicMock()
        return client

    @pytest.fixture()
    def good_vision_response(self) -> dict:
        """A plausible vision API response payload."""
        return {
            "vendor_name": "GatorGyp",
            "quote_number": "GG-2024-0088",
            "quote_date": "03/20/2024",
            "items": [
                {
                    "product": "Armstrong Dune 2x2",
                    "sku": "1774",
                    "quantity": 100,
                    "unit": "CTN",
                    "unit_cost": 38.50,
                    "total": 3850.00,
                    "notes": None,
                }
            ],
            "freight": 350.00,
            "sales_tax": 0,
            "grand_total": 4200.00,
            "lead_time": "2-3 weeks",
            "extraction_confidence": 0.88,
        }

    @pytest.mark.asyncio
    async def test_vision_success(
        self, tmp_path: Path, mock_client: MagicMock, good_vision_response: dict
    ) -> None:
        """Vision extraction should parse a well-formed API response."""
        pdf_file = tmp_path / "gatorgyp_quote.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc(["page 1"])
        # Simulate pixmap
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_doc[0].get_pixmap.return_value = mock_pixmap

        mock_response = MagicMock()
        mock_response.usage.input_tokens = 1500
        mock_response.usage.output_tokens = 300
        text_block = MagicMock()
        text_block.text = json.dumps(good_vision_response)
        mock_response.content = [text_block]

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = await extract_vendor_quote_vision(pdf_file, mock_client)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.vendor_name == "GatorGyp"
        assert result.quote.extraction_method == "vision"
        assert result.quote.grand_total == Decimal("4200.00")
        assert result.quote.freight == Decimal("350.00")
        assert result.tokens_used == 1800

    @pytest.mark.asyncio
    async def test_vision_file_not_found(self, mock_client: MagicMock) -> None:
        """Missing file should return a failure result without calling the API."""
        with patch(
            "src.extraction.vendor_parser.fitz.open",
            side_effect=FileNotFoundError("no such file"),
        ):
            result = await extract_vendor_quote_vision(Path("/tmp/nonexistent.pdf"), mock_client)

        assert result.success is False
        assert result.error is not None
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_vision_empty_api_response(self, tmp_path: Path, mock_client: MagicMock) -> None:
        """An empty API response should return a failure result."""
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc(["page 1"])
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_doc[0].get_pixmap.return_value = mock_pixmap

        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 0
        empty_block = MagicMock()
        empty_block.text = ""
        mock_response.content = [empty_block]

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = await extract_vendor_quote_vision(pdf_file, mock_client)

        assert result.success is False
        assert "empty" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# extract_vendor_quote — combined entry point
# ---------------------------------------------------------------------------


class TestExtractVendorQuote:
    """Tests for the combined async entry point."""

    @pytest.mark.asyncio
    async def test_uses_text_when_confident(self, tmp_path: Path) -> None:
        """When text extraction is confident, vision fallback should NOT be called."""
        pdf_file = tmp_path / "good_text.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc([SAMPLE_QUOTE_TEXT])
        mock_client = MagicMock()
        mock_client.messages = MagicMock()

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = await extract_vendor_quote(pdf_file, mock_client)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.extraction_method == "text"
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_vision_on_low_confidence(self, tmp_path: Path) -> None:
        """Low-confidence text result should trigger vision fallback."""
        pdf_file = tmp_path / "sparse.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        # Sparse doc → low confidence
        mock_doc = _make_mock_fitz_doc(["   "])  # nearly empty
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_doc[0].get_pixmap.return_value = mock_pixmap

        vision_payload = {
            "vendor_name": "Snap-Tex",
            "quote_number": "ST-001",
            "quote_date": "04/01/2024",
            "items": [],
            "freight": None,
            "sales_tax": None,
            "grand_total": 999.00,
            "lead_time": None,
            "extraction_confidence": 0.85,
        }

        mock_response = MagicMock()
        mock_response.usage.input_tokens = 1000
        mock_response.usage.output_tokens = 200
        text_block = MagicMock()
        text_block.text = json.dumps(vision_payload)
        mock_response.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = await extract_vendor_quote(pdf_file, mock_client)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.extraction_method == "vision"
        assert result.quote.vendor_name == "Snap-Tex"

    @pytest.mark.asyncio
    async def test_no_client_returns_text_result_even_if_low_confidence(
        self, tmp_path: Path
    ) -> None:
        """Without a client, even a low-confidence text result should be returned."""
        pdf_file = tmp_path / "noapi.pdf"
        pdf_file.write_bytes(b"fake pdf bytes")

        mock_doc = _make_mock_fitz_doc(["tiny"])

        with patch("src.extraction.vendor_parser.fitz.open", return_value=mock_doc):
            result = await extract_vendor_quote(pdf_file, client=None)

        assert result.success is True
        assert result.quote is not None
        assert result.quote.extraction_method == "text"


# ---------------------------------------------------------------------------
# find_vendor_quote_files
# ---------------------------------------------------------------------------


class TestFindVendorQuoteFiles:
    """Tests for the vendor quote file discovery function."""

    def test_finds_vendor_named_pdf(self, tmp_path: Path) -> None:
        """PDFs named with known vendor keywords should be discovered."""
        project = tmp_path / "Project A"
        project.mkdir()
        (project / "MDC_quote_2024.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        assert any(p.name == "MDC_quote_2024.pdf" for p, _ in results)

    def test_finds_invoice_pdf(self, tmp_path: Path) -> None:
        """PDFs with 'Invoice' in the name should be included."""
        project = tmp_path / "Project B"
        project.mkdir()
        (project / "Armstrong Invoice 2024-003.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        assert any("Invoice" in p.name for p, _ in results)

    def test_finds_po_pdf(self, tmp_path: Path) -> None:
        """PDFs with 'PO' in the name should be included."""
        project = tmp_path / "Project C"
        project.mkdir()
        (project / "FBM PO 12345.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        assert any("PO" in p.name for p, _ in results)

    def test_excludes_ca_own_quotes(self, tmp_path: Path) -> None:
        """CA's own outgoing quotes 'Quote XXXXX.pdf' should be excluded."""
        project = tmp_path / "Project D"
        project.mkdir()
        (project / "Quote ABC-123.pdf").write_bytes(b"CA quote")
        (project / "MDC Quote 2024.pdf").write_bytes(b"vendor quote")

        results = find_vendor_quote_files(tmp_path)
        names = [p.name for p, _ in results]
        assert "Quote ABC-123.pdf" not in names
        assert "MDC Quote 2024.pdf" in names

    def test_excludes_non_matching_pdfs(self, tmp_path: Path) -> None:
        """Generic PDFs without vendor/transactional keywords should be excluded."""
        project = tmp_path / "Project E"
        project.mkdir()
        (project / "Architectural Plans.pdf").write_bytes(b"plans")
        (project / "Scope of Work.pdf").write_bytes(b"sow")

        results = find_vendor_quote_files(tmp_path)
        names = [p.name for p, _ in results]
        assert "Architectural Plans.pdf" not in names
        assert "Scope of Work.pdf" not in names

    def test_excludes_archived_files(self, tmp_path: Path) -> None:
        """Files inside '++Archive' subdirectories should be excluded."""
        archive = tmp_path / "++Archive" / "Old Project"
        archive.mkdir(parents=True)
        (archive / "MDC_quote_old.pdf").write_bytes(b"old pdf")

        results = find_vendor_quote_files(tmp_path)
        assert not any(p.name == "MDC_quote_old.pdf" for p, _ in results)

    def test_excludes_archive_not_double_plus(self, tmp_path: Path) -> None:
        """Files inside plain 'Archive' folder should also be excluded."""
        archive = tmp_path / "Project X" / "Archive"
        archive.mkdir(parents=True)
        (archive / "RPG_old_quote.pdf").write_bytes(b"old pdf")

        results = find_vendor_quote_files(tmp_path)
        assert not any(p.name == "RPG_old_quote.pdf" for p, _ in results)

    def test_excludes_non_pdf(self, tmp_path: Path) -> None:
        """Non-PDF files should not be included even if vendor-named."""
        project = tmp_path / "Project F"
        project.mkdir()
        (project / "MDC_quote.xlsx").write_bytes(b"xlsx")
        (project / "FBM_order.docx").write_bytes(b"docx")
        (project / "GatorGyp_quote.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        assert all(p.suffix == ".pdf" for p, _ in results)

    def test_returns_vendor_name_when_detectable(self, tmp_path: Path) -> None:
        """Vendor name should be populated from filename when detectable."""
        project = tmp_path / "Project G"
        project.mkdir()
        (project / "Arktura_order_2024.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        matches = [(p, v) for p, v in results if "Arktura" in p.name]
        assert matches
        assert matches[0][1] == "Arktura"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory should return an empty list."""
        assert find_vendor_quote_files(tmp_path) == []

    def test_nonexistent_directory(self) -> None:
        """Nonexistent directory should return empty list without raising."""
        result = find_vendor_quote_files(Path("/nonexistent/path/xyz"))
        assert result == []

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        """PDF files in nested subdirectories should be discovered."""
        nested = tmp_path / "Projects" / "Sub" / "Vendor Quotes"
        nested.mkdir(parents=True)
        (nested / "Soelberg_quote_001.pdf").write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        assert any("Soelberg" in p.name for p, _ in results)

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Results should be in sorted (deterministic) order."""
        for name in ("ZZZ_MDC_quote.pdf", "AAA_FBM_order.pdf", "MMM_RPG_quote.pdf"):
            (tmp_path / name).write_bytes(b"pdf")

        results = find_vendor_quote_files(tmp_path)
        paths = [p for p, _ in results]
        assert paths == sorted(paths)
