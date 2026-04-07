"""Quote PDF parser for Acoustimator.

Parses Commercial Acoustics customer-facing quote PDFs (templates T-004A, T-004B,
T-004E) using PyMuPDF and returns validated Pydantic models.

Quote PDFs live at paths like:
  /…/+ITBs/[folder]/Quote XXXXX - [ClientName].pdf

They are 2-page standardised documents:
  Page 1 — letterhead, quote number, date, contact info, line-items table
  Page 2 — material/labor/tax breakdown, terms and conditions

Usage:
    from src.extraction.pdf_parser import extract_quote, find_quote_files

    result = extract_quote(Path("Quote 05906 - Acme Corp.pdf"))
    if result.success:
        print(result.quote.quote_number)

    pairs = find_quote_files(Path("/path/to/+ITBs"))
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Quote number: 5 digits, optional revision suffix like -R1 or -R2
_QUOTE_NUMBER_RE = re.compile(r"\b(\d{5}(?:-R\d+)?)\b")

# Revision suffix on its own (captured from the full quote number)
_REVISION_RE = re.compile(r"-R(\d+)$")

# Date patterns found in Commercial Acoustics quotes
_DATE_PATTERNS: list[re.Pattern[str]] = [
    # "Date: 01/15/2024" or "Quote Date: January 15, 2024"
    re.compile(
        r"(?:Quote\s+Date|Date)\s*[:\-]\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"
        r"|[A-Za-z]+ \d{1,2},? \d{4})",
        re.IGNORECASE,
    ),
    # Standalone MM/DD/YYYY or MM-DD-YYYY
    re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\b"),
    # "January 15, 2024" or "Jan 15 2024"
    re.compile(
        r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
        re.IGNORECASE,
    ),
]

# Payment term keywords (ordered most-specific first)
_PAYMENT_TERM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"MILESTONE\s+BILLING", re.IGNORECASE),
    re.compile(r"50%\s*DOWN\s*/\s*BALANCE\s+NET\s*\d+", re.IGNORECASE),
    re.compile(r"50%\s*(?:DOWN|DEPOSIT)", re.IGNORECASE),
    re.compile(r"NET\s*30", re.IGNORECASE),
    re.compile(r"NET\s*15", re.IGNORECASE),
    re.compile(r"NET\s*\d+", re.IGNORECASE),
]

# Template-detection keywords
_TEMPLATE_KEYWORDS: dict[str, str] = {
    "ACOUSTIC PANEL FAB": "T-004B",
    "ACOUSTIC PANEL FAB & INSTALL": "T-004B",
    "SOUND MASKING": "T-004E",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class QuoteLineItem(BaseModel):
    """A single row in the quote's line-items table."""

    qty: Decimal | None = None
    item_type: str | None = None  # e.g. "ACT-1", "AWP-1"
    description: str | None = None
    cost_per_unit: Decimal | None = None
    total: Decimal | None = None


class ExtractedQuote(BaseModel):
    """All structured data extracted from a single quote PDF."""

    quote_number: str | None = None  # e.g. "05906" or "05906-R1"
    revision: str | None = None  # e.g. "R1", "R2", or None
    quote_date: str | None = None  # ISO date string or raw string from document
    template_type: str | None = None  # "T-004A", "T-004B", "T-004E", or None
    client_name: str | None = None
    project_address: str | None = None
    gc_name: str | None = None
    gc_contact: str | None = None
    line_items: list[QuoteLineItem] = []
    subtotal_material: Decimal | None = None
    subtotal_labor: Decimal | None = None
    subtotal_tax: Decimal | None = None
    grand_total: Decimal | None = None
    payment_terms: str | None = None  # e.g. "MILESTONE BILLING"
    source_file: str
    extraction_confidence: float = 0.0  # 0.0 – 1.0


class QuoteExtractionResult(BaseModel):
    """Outcome of a single extraction attempt."""

    success: bool
    quote: ExtractedQuote | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_decimal(value: str) -> Decimal | None:
    """Strip currency symbols, commas, and whitespace, then coerce to Decimal.

    Returns None when the input cannot be parsed as a number.

    Args:
        value: Raw string that may contain "$", ",", spaces, etc.

    Returns:
        A Decimal on success, or None if the string is not numeric.
    """
    cleaned = value.strip().lstrip("$").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _extract_quote_number(text: str) -> tuple[str | None, str | None]:
    """Return (quote_number_with_revision, revision_suffix) from raw text.

    Searches for the first 5-digit number (optionally followed by -R<n>).

    Args:
        text: Full text extracted from the PDF.

    Returns:
        Tuple of (full_quote_number, revision) where revision is e.g. "R1" or None.
    """
    match = _QUOTE_NUMBER_RE.search(text)
    if not match:
        return None, None

    full = match.group(1)
    rev_match = _REVISION_RE.search(full)
    revision = f"R{rev_match.group(1)}" if rev_match else None
    return full, revision


def _extract_date(text: str) -> str | None:
    """Return the first date-like string found in the text.

    Tries labelled patterns ("Date:", "Quote Date:") first, then bare dates.

    Args:
        text: Full text extracted from the PDF.

    Returns:
        The matched date string, or None if no date is found.
    """
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            # Group 1 is the date portion for all patterns
            return match.group(1).strip()
    return None


def _detect_template(text: str) -> str | None:
    """Detect the quote template family from header text.

    Args:
        text: Full text extracted from the PDF.

    Returns:
        "T-004A", "T-004B", "T-004E", or None if the template cannot be determined.
    """
    upper = text.upper()
    for keyword, template in _TEMPLATE_KEYWORDS.items():
        if keyword in upper:
            return template
    # T-004A is the fallback for documents that have neither keyword but still
    # look like a Commercial Acoustics quote (quote number was found)
    return None


def _extract_payment_terms(text: str) -> str | None:
    """Return the first recognisable payment-term string found in the text.

    Args:
        text: Full text extracted from the PDF.

    Returns:
        The matched payment-term string (uppercased), or None if not found.
    """
    for pattern in _PAYMENT_TERM_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).upper()
    return None


def _parse_money_line(line: str) -> Decimal | None:
    """Extract a single monetary amount from a line of text.

    Looks for patterns like "$1,234.56" or "1234.56" anywhere in the line.

    Args:
        line: A single line of text that may contain a dollar amount.

    Returns:
        The first Decimal value found, or None.
    """
    # Match optional $ then digits with optional commas/decimal
    money_re = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")
    match = money_re.search(line)
    if match:
        return _clean_decimal(match.group(1))
    return None


def _extract_line_items(text: str) -> list[QuoteLineItem]:
    """Parse the line-items table from the quote PDF text.

    The table has columns: QTY | TYPE | DESCRIPTION | COST PER UNIT | TOTAL

    The parser looks for numeric-leading rows within the table section and
    attempts to tokenise each into its five columns.  Columns may be separated
    by variable whitespace because PyMuPDF collapses the PDF table into a flat
    text stream.

    Args:
        text: Full text extracted from the PDF (all pages concatenated).

    Returns:
        List of QuoteLineItem objects; empty list if the table is not found.
    """
    items: list[QuoteLineItem] = []

    # Find the section between the table header and the subtotals/totals block
    # The header row typically contains "QTY" and "DESCRIPTION"
    header_re = re.compile(r"QTY\s+TYPE\s+DESCRIPTION.*?TOTAL", re.IGNORECASE)
    header_match = header_re.search(text)
    if not header_match:
        # Try a looser match for just QTY ... TOTAL
        header_re = re.compile(r"\bQTY\b.{0,80}\bTOTAL\b", re.IGNORECASE | re.DOTALL)
        header_match = header_re.search(text)
    if not header_match:
        logger.debug("Line-items table header not found")
        return items

    table_start = header_match.end()

    # Find where the table ends: look for subtotal/material keywords or blank section
    end_re = re.compile(
        r"(?:SUBTOTAL|Material\s+Subtotal|Labor\s+Subtotal|TERMS\s+AND\s+CONDITIONS"
        r"|PAYMENT\s+TERMS|Page\s+\d+\s+of\s+\d+)",
        re.IGNORECASE,
    )
    end_match = end_re.search(text, table_start)
    table_text = text[table_start : end_match.start()] if end_match else text[table_start:]

    # Each line item typically starts with a quantity (integer or decimal)
    # followed by an item type code and description, and ends with dollar amounts
    # Pattern: leading number, then optional type code (letters/digits/hyphens),
    # then description text, then prices
    line_re = re.compile(
        r"^\s*(\d+(?:\.\d+)?)\s+"  # QTY
        r"([A-Z]{1,5}-?\d*[A-Z]?\d*)\s+"  # TYPE (e.g. ACT-1, AWP-1, SM)
        r"(.+?)\s+"  # DESCRIPTION (non-greedy)
        r"\$?([\d,]+(?:\.\d+)?)\s+"  # COST PER UNIT
        r"\$?([\d,]+(?:\.\d+)?)\s*$",  # TOTAL
        re.IGNORECASE | re.MULTILINE,
    )

    for match in line_re.finditer(table_text):
        qty = _clean_decimal(match.group(1))
        item_type = match.group(2).upper()
        description = match.group(3).strip()
        cost_per_unit = _clean_decimal(match.group(4))
        total = _clean_decimal(match.group(5))

        items.append(
            QuoteLineItem(
                qty=qty,
                item_type=item_type,
                description=description,
                cost_per_unit=cost_per_unit,
                total=total,
            )
        )

    if not items:
        # Fallback: looser per-line parse — look for lines that have two
        # dollar-ish amounts at the end (cost_per_unit and total)
        loose_re = re.compile(
            r"^\s*(\d+(?:\.\d+)?)\s+(\S+)\s+(.+?)\s+"
            r"\$?\s*([\d,]+\.\d{2})\s+\$?\s*([\d,]+\.\d{2})\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        for match in loose_re.finditer(table_text):
            qty = _clean_decimal(match.group(1))
            item_type = match.group(2)
            description = match.group(3).strip()
            cost_per_unit = _clean_decimal(match.group(4))
            total = _clean_decimal(match.group(5))
            items.append(
                QuoteLineItem(
                    qty=qty,
                    item_type=item_type,
                    description=description,
                    cost_per_unit=cost_per_unit,
                    total=total,
                )
            )

    logger.debug("Parsed %d line items from table", len(items))
    return items


def _extract_subtotals(text: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Return (subtotal_material, subtotal_labor, subtotal_tax) from breakdown table.

    These appear on page 2 of the quote in a per-scope breakdown.

    Args:
        text: Full text extracted from the PDF (all pages concatenated).

    Returns:
        Tuple of (material, labor, tax) Decimals; any element may be None.
    """
    material: Decimal | None = None
    labor: Decimal | None = None
    tax: Decimal | None = None

    # Look for labelled subtotal lines
    for line in text.splitlines():
        line_upper = line.upper()
        amount = _parse_money_line(line)
        if amount is None:
            continue
        if "MATERIAL" in line_upper and "SUBTOTAL" in line_upper and material is None:
            material = amount
        elif "LABOR" in line_upper and "SUBTOTAL" in line_upper and labor is None:
            labor = amount
        elif "TAX" in line_upper and "SUBTOTAL" in line_upper and tax is None:
            tax = amount

    return material, labor, tax


def _extract_grand_total(text: str) -> Decimal | None:
    """Return the grand total from the PDF text.

    Handles several layout styles produced by PyMuPDF when extracting
    Commercial Acoustics quote PDFs:

    1. Same-line: "GRAND TOTAL  $1,234.56"
    2. Label-then-amount: "Grand Total\\n\\n$1,234.56" (up to 4 blank lines)
    3. Amount-then-label: "$1,234.56\\n\\nTotal" (Total immediately after amount)
    4. Labelled same-line: "Base Bid Grand Total – ...\\n\\n$1,234.56"
    5. Inline colon: "Total: $1,234.56" or "Total:\\n$1,234.56"

    Args:
        text: Full text extracted from the PDF.

    Returns:
        The grand-total Decimal, or None if not found.
    """
    # --- Strategy 1: same-line patterns (label + amount on one line) ----------
    same_line_patterns = [
        re.compile(r"GRAND\s+TOTAL.*?(\$?[\d,]+\.\d{2})", re.IGNORECASE),
        re.compile(r"PROJECT\s+TOTAL.*?(\$?[\d,]+\.\d{2})", re.IGNORECASE),
        re.compile(r"^Total\s*:\s*\$?([\d,]+\.\d{2})\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^TOTAL\s+(\$?[\d,]+\.\d{2})\s*$", re.IGNORECASE | re.MULTILINE),
    ]
    for pattern in same_line_patterns:
        match = pattern.search(text)
        if match:
            return _clean_decimal(match.group(1))

    # Helper: does a line contain only a standalone dollar amount?
    money_only_re = re.compile(r"^\s*\$?\s*([\d,]+\.\d{2})\s*$")

    # Broader "total label" detector used in strategies 2 & 3
    label_re = re.compile(
        r"(?:GRAND\s+TOTAL|BASE\s+BID\s+GRAND\s+TOTAL|PROJECT\s+TOTAL"
        r"|Total\s*(?:Including.*)?|Total\s*:)\s*$",
        re.IGNORECASE,
    )

    lines = text.splitlines()

    # --- Strategy 2: label line, then amount within next 4 lines --------------
    for i, line in enumerate(lines):
        if label_re.search(line.strip()):
            for j in range(i + 1, min(i + 5, len(lines))):
                m = money_only_re.match(lines[j])
                if m:
                    return _clean_decimal(m.group(1))

    # --- Strategy 3: amount line, then "Total" label within next 2 lines ------
    # Used by older single-scope quotes where the column header is "TOTAL" but
    # the amount floats above the label in PyMuPDF's text stream.
    bare_total_re = re.compile(r"^\s*Total\s*$", re.IGNORECASE)
    for i, line in enumerate(lines):
        m = money_only_re.match(line)
        if m:
            for j in range(i + 1, min(i + 4, len(lines))):
                if bare_total_re.match(lines[j].strip()):
                    return _clean_decimal(m.group(1))

    # --- Strategy 4: last standalone dollar amount before QUOTE # block -------
    # Final fallback: in very simple single-line-item quotes the last dollar
    # amount before "QUOTE #:" is the total.
    quote_num_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if re.search(r"QUOTE\s*#", lines[i], re.IGNORECASE):
            quote_num_idx = i
            break

    if quote_num_idx is not None:
        for i in range(quote_num_idx - 1, max(quote_num_idx - 10, -1), -1):
            m = money_only_re.match(lines[i])
            if m:
                return _clean_decimal(m.group(1))

    return None


def _extract_client_name(text: str, source_file: Path) -> str | None:
    """Return the client name, preferring the filename over PDF text.

    Quote filenames follow the pattern "Quote XXXXX - Client Name.pdf".
    Falling back to scanning the PDF text for address-block patterns is
    brittle, so the filename is the primary source.

    Args:
        text: Full text extracted from the PDF.
        source_file: Path to the PDF file.

    Returns:
        Client name string, or None if not determinable.
    """
    # Primary: parse "Quote NNNNN - ClientName.pdf" or "Quote NNNNN-R1 - ClientName.pdf"
    stem = source_file.stem  # e.g. "Quote 05906 - Acme Corporation"
    client_re = re.compile(r"^Quote\s+[\dA-Za-z\-]+\s*-\s*(.+)$", re.IGNORECASE)
    match = client_re.match(stem)
    if match:
        return match.group(1).strip()

    # Fallback: look for "Prepared for:" or "Attention:" in text
    for label in ("Prepared for:", "Prepared For:", "ATTENTION:", "Attention:"):
        idx = text.find(label)
        if idx != -1:
            after = text[idx + len(label) :].strip()
            # Take just the first non-empty line
            first_line = after.splitlines()[0].strip() if after else ""
            if first_line:
                return first_line

    return None


def _extract_project_address(text: str) -> str | None:
    """Return a best-effort project address from the PDF text.

    Looks for a block starting with "Project:" or "Project Address:" and
    captures the first line after it that looks like an address.

    Args:
        text: Full text extracted from the PDF.

    Returns:
        Address string, or None if not found.
    """
    addr_re = re.compile(
        r"(?:Project\s+Address|Project|Job\s+Address)\s*[:\-]\s*([^\n]+(?:\n[^\n]+)?)",
        re.IGNORECASE,
    )
    match = addr_re.search(text)
    if match:
        raw = match.group(1).strip()
        # Keep only the first two lines if multi-line
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        return " | ".join(lines[:2]) if lines else None
    return None


def _extract_gc_info(text: str) -> tuple[str | None, str | None]:
    """Return (gc_name, gc_contact) from the PDF text.

    Looks for "General Contractor:", "GC:", "Contractor:" label patterns.

    Args:
        text: Full text extracted from the PDF.

    Returns:
        Tuple of (gc_name, gc_contact); either may be None.
    """
    gc_name: str | None = None
    gc_contact: str | None = None

    gc_re = re.compile(
        r"(?:General\s+Contractor|GC|Contractor)\s*[:\-]\s*([^\n]+)",
        re.IGNORECASE,
    )
    match = gc_re.search(text)
    if match:
        gc_name = match.group(1).strip()

    contact_re = re.compile(
        r"(?:Contact|Attn|Attention|Representative)\s*[:\-]\s*([^\n]+)",
        re.IGNORECASE,
    )
    match = contact_re.search(text)
    if match:
        gc_contact = match.group(1).strip()

    return gc_name, gc_contact


def _compute_confidence(
    quote_number: str | None,
    quote_date: str | None,
    grand_total: Decimal | None,
    line_items: list[QuoteLineItem],
) -> float:
    """Compute an extraction confidence score in [0.0, 1.0].

    Scoring:
      +0.3  quote number found
      +0.2  date found
      +0.3  grand total found
      +0.2  at least one line item found

    Args:
        quote_number: Extracted quote number, or None.
        quote_date: Extracted date string, or None.
        grand_total: Extracted grand total, or None.
        line_items: List of parsed line items.

    Returns:
        Float confidence score between 0.0 and 1.0 inclusive.
    """
    score = 0.0
    if quote_number:
        score += 0.3
    if quote_date:
        score += 0.2
    if grand_total:
        score += 0.3
    if line_items:
        score += 0.2
    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_quote(file_path: Path) -> QuoteExtractionResult:
    """Extract structured data from a Commercial Acoustics quote PDF.

    Opens the PDF with PyMuPDF, extracts text from all pages, then applies
    regex-based heuristics to pull out quote metadata, line items, subtotals,
    and payment terms.  No external API calls are made.

    Confidence score reflects how many key fields were successfully extracted:
      +0.3 quote number, +0.2 date, +0.3 grand total, +0.2 line items.

    Args:
        file_path: Absolute or relative path to the .pdf quote file.

    Returns:
        QuoteExtractionResult with success=True and a populated ExtractedQuote
        on success, or success=False with an error message on failure.
    """
    file_path = Path(file_path)
    logger.info("Parsing quote PDF: %s", file_path)

    # ------------------------------------------------------------------ open
    try:
        doc = fitz.open(str(file_path))
    except (FileNotFoundError, fitz.FileNotFoundError):
        return QuoteExtractionResult(
            success=False,
            error=f"File not found: {file_path}",
        )
    except fitz.FileDataError as exc:
        return QuoteExtractionResult(
            success=False,
            error=f"Corrupted or unreadable PDF: {exc}",
        )
    except fitz.EmptyFileError as exc:
        return QuoteExtractionResult(
            success=False,
            error=f"Empty PDF file: {exc}",
        )
    except RuntimeError as exc:
        # fitz raises RuntimeError for password-protected documents
        msg = str(exc)
        if "password" in msg.lower() or "encrypted" in msg.lower():
            return QuoteExtractionResult(
                success=False,
                error=f"Password-protected PDF: {exc}",
            )
        return QuoteExtractionResult(
            success=False,
            error=f"PDF open error: {exc}",
        )

    # --------------------------------------------------------- extract text
    try:
        pages_text: list[str] = []
        for page in doc:
            pages_text.append(page.get_text("text"))
        full_text = "\n".join(pages_text)
    except Exception as exc:  # noqa: BLE001 — PyMuPDF raises generic errors
        doc.close()
        return QuoteExtractionResult(
            success=False,
            error=f"Text extraction failed: {type(exc).__name__}: {exc}",
        )
    finally:
        doc.close()

    if not full_text.strip():
        return QuoteExtractionResult(
            success=False,
            error="PDF contains no extractable text (may be image-only)",
        )

    # ---------------------------------------------------------- parse fields
    quote_number, revision = _extract_quote_number(full_text)
    quote_date = _extract_date(full_text)
    template_type = _detect_template(full_text)

    # Fall back to T-004A when a quote number is found but no specific keyword matched
    if template_type is None and quote_number is not None:
        template_type = "T-004A"

    client_name = _extract_client_name(full_text, file_path)
    project_address = _extract_project_address(full_text)
    gc_name, gc_contact = _extract_gc_info(full_text)
    line_items = _extract_line_items(full_text)
    subtotal_material, subtotal_labor, subtotal_tax = _extract_subtotals(full_text)
    grand_total = _extract_grand_total(full_text)
    payment_terms = _extract_payment_terms(full_text)

    confidence = _compute_confidence(quote_number, quote_date, grand_total, line_items)

    quote = ExtractedQuote(
        quote_number=quote_number,
        revision=revision,
        quote_date=quote_date,
        template_type=template_type,
        client_name=client_name,
        project_address=project_address,
        gc_name=gc_name,
        gc_contact=gc_contact,
        line_items=line_items,
        subtotal_material=subtotal_material,
        subtotal_labor=subtotal_labor,
        subtotal_tax=subtotal_tax,
        grand_total=grand_total,
        payment_terms=payment_terms,
        source_file=str(file_path),
        extraction_confidence=confidence,
    )

    logger.info(
        "Extracted quote %s (template=%s, items=%d, confidence=%.2f)",
        quote_number,
        template_type,
        len(line_items),
        confidence,
    )
    return QuoteExtractionResult(success=True, quote=quote)


def find_quote_files(source_dir: Path) -> list[tuple[Path, str]]:
    """Walk a directory tree and find Commercial Acoustics quote PDFs.

    Matches files whose names follow the pattern "Quote *.pdf" (case-insensitive).
    The second element of each tuple is the immediate parent folder name, which
    corresponds to the project folder in the +ITBs hierarchy.

    Args:
        source_dir: Root directory to search (e.g. the +ITBs folder).

    Returns:
        List of (pdf_path, folder_name) tuples, sorted by path.
        Returns an empty list if source_dir does not exist.
    """
    results: list[tuple[Path, str]] = []

    if not source_dir.is_dir():
        logger.warning("Quote source directory does not exist: %s", source_dir)
        return results

    for pdf_path in sorted(source_dir.rglob("Quote *.pdf")):
        folder_name = pdf_path.parent.name
        results.append((pdf_path, folder_name))

    logger.info("Found %d quote PDFs in %s", len(results), source_dir)
    return results
