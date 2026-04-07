"""Vendor quote parser for Acoustimator.

Extracts structured data from vendor quote PDFs (and Word docs) supplied to
Commercial Acoustics by vendors such as MDC, FBM/Foundation Building Materials,
GatorGyp, Snap-Tex, RPG, Arktura, and others.

Two-pass strategy:
  1. Text pass — PyMuPDF extracts raw text; regex/heuristics parse line items.
  2. Vision fallback — page images are sent to Claude Vision when text extraction
     yields insufficient content (< 50 usable characters).

Usage:
    from src.extraction.vendor_parser import extract_vendor_quote

    result = await extract_vendor_quote(Path("path/to/quote.pdf"), client)
"""

from __future__ import annotations

import base64
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import anthropic
import fitz  # PyMuPDF
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MIN_TEXT_LENGTH = 50  # characters below which we fall back to vision
MAX_VISION_PAGES = 3  # only convert this many pages for vision calls

# Vendor quote files to include / exclude
VENDOR_QUOTE_INCLUDE_PATTERNS = re.compile(
    r"(?i)(PO|Order|Invoice|Quote|MDC|Foundation|GatorGyp|Snap.?Tex|RPG|Arktura|Turf|"
    r"J2|Soelberg|Acoufelt|9Wood|Soundply|L&W|FBM|Armstrong|USG)",
)
# CA's own outgoing quotes — NOT vendor quotes
CA_OWN_QUOTE_PATTERN = re.compile(r"(?i)^Quote\s+[A-Z0-9\-]+\.pdf$")

# ---------------------------------------------------------------------------
# Known vendor registry
# ---------------------------------------------------------------------------

KNOWN_VENDORS: dict[str, str] = {
    "MDC": "MDC Interior Solutions",
    "Foundation Building": "FBM",
    "FBM": "FBM",
    "GatorGyp": "GatorGyp",
    "GMS Acoustics": "GatorGyp",
    "Snap-Tex": "Snap-Tex",
    "SnapTex": "Snap-Tex",
    "RPG": "RPG Diffusor Systems",
    "Arktura": "Arktura",
    "Turf": "Turf",
    "J2": "J2 International",
    "Soelberg": "Soelberg Industries",
    "Acoufelt": "Acoufelt",
    "9Wood": "9Wood",
    "Soundply": "Soundply",
    "L&W": "L&W Supply",
    "Armstrong": "Armstrong",
    "USG": "USG",
}

# Pre-compile patterns sorted longest-first so more specific keys win
_VENDOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(key), re.IGNORECASE), canonical)
    for key, canonical in sorted(KNOWN_VENDORS.items(), key=lambda kv: -len(kv[0]))
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class VendorLineItem(BaseModel):
    """A single product line extracted from a vendor quote."""

    product: str | None = None
    sku: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None  # CTN, EA, SF, LF, SY, etc.
    unit_cost: Decimal | None = None
    total: Decimal | None = None
    notes: str | None = None


class ExtractedVendorQuote(BaseModel):
    """Structured data extracted from a vendor quote document."""

    vendor_name: str | None = None
    quote_number: str | None = None
    quote_date: str | None = None
    items: list[VendorLineItem] = []
    freight: Decimal | None = None
    sales_tax: Decimal | None = None
    grand_total: Decimal | None = None
    lead_time: str | None = None
    source_file: str
    extraction_method: str  # "text" or "vision"
    extraction_confidence: float = 0.0


class VendorExtractionResult(BaseModel):
    """Result of an extraction attempt for a vendor quote file."""

    success: bool
    quote: ExtractedVendorQuote | None = None
    error: str | None = None
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def detect_vendor(text: str) -> str | None:
    """Return the canonical vendor name found in *text*, or None.

    Scans the text against the KNOWN_VENDORS registry using pre-compiled
    regex patterns sorted longest-first so that e.g. "Foundation Building"
    matches before the shorter "FBM".

    Args:
        text: Raw text from a document header or filename.

    Returns:
        Canonical vendor name string, or None if no match.
    """
    for pattern, canonical in _VENDOR_PATTERNS:
        if pattern.search(text):
            return canonical
    return None


def clean_decimal(raw: str) -> Decimal | None:
    """Parse a currency/numeric string into a Decimal.

    Handles:
      - Dollar signs and commas: "$1,234.56" → Decimal("1234.56")
      - Unit suffixes stripped: "$42.50/CTN" → Decimal("42.50")
      - Parenthetical negatives: "(100.00)" → Decimal("-100.00")
      - Percent signs stripped: "6%" → Decimal("6")
      - Empty / non-numeric strings → None

    Args:
        raw: The raw string value to parse.

    Returns:
        Decimal if parseable, otherwise None.
    """
    if not raw:
        return None

    s = raw.strip()

    # Handle parenthetical negatives like (100.00)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        negative = True

    # Strip currency, percent, trailing unit suffixes (e.g. "/CTN", "/EA")
    s = re.sub(r"[,$%]", "", s)
    s = re.sub(r"/[A-Za-z]+.*$", "", s)
    s = s.strip()

    if not s:
        return None

    try:
        value = Decimal(s)
        return -value if negative else value
    except InvalidOperation:
        return None


def _extract_text_from_pdf(file_path: Path) -> str:
    """Open a PDF with PyMuPDF and return concatenated page text.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Full document text joined with newlines.

    Raises:
        fitz.FileDataError: If the file is not a valid PDF.
        FileNotFoundError: If the file does not exist.
    """
    doc: fitz.Document = fitz.open(str(file_path))
    try:
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        return "\n".join(pages)
    finally:
        doc.close()


def _parse_line_items_from_text(text: str) -> list[VendorLineItem]:
    """Heuristically parse vendor quote line items from raw text.

    Looks for rows that match a pattern of: optional SKU, description text,
    then numeric columns for quantity, unit, unit price, and total.

    This is intentionally lenient — it captures candidates and lets the
    caller decide confidence based on the result count.

    Args:
        text: Raw text extracted from a vendor quote PDF.

    Returns:
        List of VendorLineItem objects (may be empty).
    """
    items: list[VendorLineItem] = []

    # Pattern: optional sku-like token, description words, qty, unit, cost, total
    # Matches lines like:
    #   24-123   Dune 1774 2x2   48   CTN   $42.50   $2,040.00
    #   SKU      Product Name    Qty  Unit  UC        Ext
    line_pattern = re.compile(
        r"^(?P<sku>[A-Z0-9\-]{4,20})?\s*"
        r"(?P<product>[A-Za-z][\w\s/\-\(\)]{3,60}?)\s+"
        r"(?P<qty>\d+(?:\.\d+)?)\s+"
        r"(?P<unit>CTN|EA|SF|LF|SY|PC|RL|BX|CS|SQ|M2|BOX|EACH|PALLET)\s+"
        r"\$?(?P<unit_cost>[\d,]+(?:\.\d{1,4})?)\s+"
        r"\$?(?P<total>[\d,]+(?:\.\d{2})?)",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in line_pattern.finditer(text):
        gd = match.groupdict()
        item = VendorLineItem(
            product=gd["product"].strip() if gd.get("product") else None,
            sku=gd["sku"].strip() if gd.get("sku") else None,
            quantity=clean_decimal(gd["qty"]) if gd.get("qty") else None,
            unit=gd["unit"].upper() if gd.get("unit") else None,
            unit_cost=clean_decimal(gd["unit_cost"]) if gd.get("unit_cost") else None,
            total=clean_decimal(gd["total"]) if gd.get("total") else None,
        )
        items.append(item)

    return items


def _find_decimal_after_label(text: str, *labels: str) -> Decimal | None:
    """Search *text* for any of *labels* and return the first Decimal found after it.

    Handles labels like "Freight", "Total", "Grand Total", "Sales Tax".

    Args:
        text: The full document text.
        *labels: One or more label strings to search for (case-insensitive).

    Returns:
        First parseable Decimal value following any matching label, or None.
    """
    label_re = "|".join(re.escape(lbl) for lbl in labels)
    pattern = re.compile(
        rf"(?:{label_re})\s*[:\-]?\s*\$?\s*([\d,]+(?:\.\d{{1,4}})?)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return clean_decimal(match.group(1))
    return None


def _find_quote_number(text: str) -> str | None:
    """Extract a quote, order, or PO number from raw text.

    Looks for patterns like "Quote #12345", "Order No: Q-2024-001",
    "PO Number: 98765", "Invoice #INV-2024-055".

    Args:
        text: Raw document text.

    Returns:
        The extracted quote/order number as a string, or None.
    """
    patterns = [
        r"(?:Quote|Order|PO|Invoice|Ref)\s*(?:#|No\.?|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]{4,25})",
        r"(?:Quote|Order|PO|Invoice)\s+([A-Z0-9\-\/]{4,25})",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Exclude common false positives like "Date" or full sentences
            if len(candidate) <= 25 and not re.search(r"[a-z]{5,}", candidate):
                return candidate
    return None


def _find_quote_date(text: str) -> str | None:
    """Extract a date string from raw text.

    Recognizes:
      - MM/DD/YYYY, M/D/YY
      - Month DD, YYYY (e.g., "January 15, 2024")
      - YYYY-MM-DD

    Args:
        text: Raw document text.

    Returns:
        Date string as found in the document, or None.
    """
    patterns = [
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _find_lead_time(text: str) -> str | None:
    """Extract a lead time string from raw text.

    Matches phrases like "2-3 weeks", "4 to 6 weeks ARO", "10 business days".

    Args:
        text: Raw document text.

    Returns:
        Lead time string, or None.
    """
    pattern = re.compile(
        r"(?:lead\s+time|ships?\s+in|delivery|aro|weeks?|days?).*?"
        r"(\d+\s*(?:to|-)\s*\d+\s*(?:weeks?|days?|business\s+days?)"
        r"|\d+\s*(?:weeks?|days?|business\s+days?))",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Claude Vision prompt
# ---------------------------------------------------------------------------

_VISION_SYSTEM_PROMPT = """\
You are an expert at extracting structured data from construction material vendor quotes
for Commercial Acoustics, a Tampa FL acoustical contractor.

The bill-to address is: Residential Acoustics LLC DBA Commercial Acoustics, \
6301 N Florida Ave, Tampa FL 33604.

Extract all information from the vendor quote image(s) and return valid JSON only \
(no markdown, no code blocks) with this exact structure:

{
  "vendor_name": "string or null",
  "quote_number": "string or null",
  "quote_date": "string or null",
  "items": [
    {
      "product": "string or null",
      "sku": "string or null",
      "quantity": number_or_null,
      "unit": "CTN|EA|SF|LF|SY|PC|RL|BX|CS|SQ|other_or_null",
      "unit_cost": number_or_null,
      "total": number_or_null,
      "notes": "string or null"
    }
  ],
  "freight": number_or_null,
  "sales_tax": number_or_null,
  "grand_total": number_or_null,
  "lead_time": "string or null",
  "extraction_confidence": 0.0_to_1.0
}

Rules:
- All monetary values must be numbers (not strings with $ or commas).
- quantity must be a number (not a string).
- If a field is not present, use null.
- extraction_confidence: 0.9+ for clear tabular quotes, 0.6-0.9 for partially \
readable, below 0.6 for unclear/image-heavy.\
"""


def _build_vision_content(
    file_path: Path,
    doc: fitz.Document,
) -> list[dict[str, Any]]:
    """Convert up to MAX_VISION_PAGES PDF pages to base64 PNG images for the API.

    Args:
        file_path: Path to source PDF (used for display in the prompt text).
        doc: Open fitz.Document.

    Returns:
        Anthropic message content list containing image blocks followed by
        a text instruction block.
    """
    content: list[dict[str, Any]] = []
    page_count = min(len(doc), MAX_VISION_PAGES)

    for i in range(page_count):
        page: fitz.Page = doc[i]
        pixmap: fitz.Pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        png_bytes: bytes = pixmap.tobytes("png")
        b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": (
                f"Vendor quote file: {file_path.name}\n"
                f"Pages shown: {page_count} of {len(doc)}\n\n"
                "Extract all vendor quote data from the image(s) above and return JSON only."
            ),
        }
    )
    return content


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from Claude's response, tolerating markdown code fences.

    Args:
        text: Raw response text.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If no valid JSON can be found.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


def _build_quote_from_dict(data: dict[str, Any], source_file: str, method: str) -> ExtractedVendorQuote:
    """Construct an ExtractedVendorQuote from a parsed dict (vision or text path).

    Args:
        data: Parsed JSON dict from Claude or text extraction.
        source_file: Original file path string.
        method: "text" or "vision".

    Returns:
        Populated ExtractedVendorQuote instance.
    """

    def _to_decimal(v: Any) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            try:
                return Decimal(str(v))
            except InvalidOperation:
                return None
        if isinstance(v, str):
            return clean_decimal(v)
        return None

    raw_items = data.get("items") or []
    items: list[VendorLineItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        items.append(
            VendorLineItem(
                product=raw.get("product"),
                sku=raw.get("sku"),
                quantity=_to_decimal(raw.get("quantity")),
                unit=raw.get("unit"),
                unit_cost=_to_decimal(raw.get("unit_cost")),
                total=_to_decimal(raw.get("total")),
                notes=raw.get("notes"),
            )
        )

    return ExtractedVendorQuote(
        vendor_name=data.get("vendor_name"),
        quote_number=data.get("quote_number"),
        quote_date=data.get("quote_date"),
        items=items,
        freight=_to_decimal(data.get("freight")),
        sales_tax=_to_decimal(data.get("sales_tax")),
        grand_total=_to_decimal(data.get("grand_total")),
        lead_time=data.get("lead_time"),
        source_file=source_file,
        extraction_method=method,
        extraction_confidence=float(data.get("extraction_confidence", 0.5)),
    )


# ---------------------------------------------------------------------------
# Public API — text extraction
# ---------------------------------------------------------------------------


def extract_vendor_quote_text(file_path: Path) -> VendorExtractionResult:
    """Primary path: PyMuPDF text extraction for vendor quotes.

    Opens the PDF, extracts text from all pages, detects the vendor name,
    parses line items via regex heuristics, and extracts totals/metadata.

    Returns a result with extraction_method="text". If the PDF yields fewer
    than MIN_TEXT_LENGTH usable characters the result will still be returned
    (with low confidence) — callers should check quote.extraction_confidence
    and fall back to vision when appropriate.

    Args:
        file_path: Path to the vendor quote PDF.

    Returns:
        VendorExtractionResult with success=True on success, or success=False
        with an error message on failure.
    """
    logger.debug("Text extraction: %s", file_path)

    try:
        text = _extract_text_from_pdf(file_path)
    except FileNotFoundError:
        return VendorExtractionResult(success=False, error=f"File not found: {file_path}")
    except fitz.FileDataError as e:
        return VendorExtractionResult(success=False, error=f"Invalid PDF: {e}")
    except Exception as e:
        logger.exception("Unexpected error reading PDF: %s", file_path)
        return VendorExtractionResult(
            success=False,
            error=f"PDF read error: {type(e).__name__}: {e}",
        )

    useful_text = text.strip()
    low_content = len(useful_text) < MIN_TEXT_LENGTH

    # --- Vendor detection ---
    # Check header area (first 500 chars) first, then filename
    header = useful_text[:500]
    vendor_name = detect_vendor(header) or detect_vendor(file_path.stem)

    # --- Metadata ---
    quote_number = _find_quote_number(useful_text)
    quote_date = _find_quote_date(useful_text)
    lead_time = _find_lead_time(useful_text)

    # --- Totals ---
    freight = _find_decimal_after_label(useful_text, "Freight", "Shipping", "S&H", "Freight Charge")
    sales_tax = _find_decimal_after_label(useful_text, "Sales Tax", "Tax")
    grand_total = _find_decimal_after_label(
        useful_text, "Grand Total", "Total Due", "Amount Due", "Balance Due", "Total"
    )

    # --- Line items ---
    items = _parse_line_items_from_text(useful_text)

    # Confidence heuristic
    confidence: float
    if low_content:
        confidence = 0.1
    elif not items:
        confidence = 0.3
    elif grand_total is not None:
        confidence = 0.75
    else:
        confidence = 0.5

    quote = ExtractedVendorQuote(
        vendor_name=vendor_name,
        quote_number=quote_number,
        quote_date=quote_date,
        items=items,
        freight=freight,
        sales_tax=sales_tax,
        grand_total=grand_total,
        lead_time=lead_time,
        source_file=str(file_path),
        extraction_method="text",
        extraction_confidence=confidence,
    )

    return VendorExtractionResult(success=True, quote=quote)


# ---------------------------------------------------------------------------
# Public API — vision extraction
# ---------------------------------------------------------------------------


async def extract_vendor_quote_vision(
    file_path: Path,
    client: anthropic.AsyncAnthropic,
) -> VendorExtractionResult:
    """Fallback: Claude Vision API for non-standard / image-heavy PDFs.

    Converts up to MAX_VISION_PAGES PDF pages to PNG images at 2x scale,
    encodes them as base64, and sends them to the Claude API with a structured
    extraction prompt. Parses the JSON response into an ExtractedVendorQuote.

    Args:
        file_path: Path to the vendor quote PDF.
        client: Initialized AsyncAnthropic client.

    Returns:
        VendorExtractionResult with extraction_method="vision" and tokens_used
        populated from the API response.
    """
    logger.debug("Vision extraction: %s", file_path)

    # Open the document for image rendering
    try:
        doc: fitz.Document = fitz.open(str(file_path))
    except FileNotFoundError:
        return VendorExtractionResult(success=False, error=f"File not found: {file_path}")
    except fitz.FileDataError as e:
        return VendorExtractionResult(success=False, error=f"Invalid PDF: {e}")
    except Exception as e:
        logger.exception("Unexpected error opening PDF for vision: %s", file_path)
        return VendorExtractionResult(
            success=False,
            error=f"PDF open error: {type(e).__name__}: {e}",
        )

    try:
        content = _build_vision_content(file_path, doc)
    finally:
        doc.close()

    # Call Claude API
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError:
        return VendorExtractionResult(
            success=False,
            error="Anthropic API authentication failed — check ANTHROPIC_API_KEY",
        )
    except anthropic.RateLimitError:
        return VendorExtractionResult(
            success=False,
            error="Anthropic API rate limit exceeded — retry later",
        )
    except anthropic.APIConnectionError as e:
        return VendorExtractionResult(success=False, error=f"API connection error: {e}")
    except anthropic.APIError as e:
        logger.exception("Anthropic API error during vision extraction of %s", file_path)
        return VendorExtractionResult(
            success=False,
            error=f"Anthropic API error: {type(e).__name__}: {e}",
        )

    tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

    response_text = "".join(block.text for block in response.content if hasattr(block, "text"))

    if not response_text.strip():
        return VendorExtractionResult(
            success=False,
            error="Claude returned an empty response",
            tokens_used=tokens_used,
        )

    try:
        data = _parse_json_response(response_text)
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to parse JSON from vision response for %s: %s\nResponse: %s",
            file_path,
            e,
            response_text[:500],
        )
        return VendorExtractionResult(
            success=False,
            error=f"JSON parse error: {e}",
            tokens_used=tokens_used,
        )

    try:
        quote = _build_quote_from_dict(data, str(file_path), "vision")
    except Exception as e:
        logger.exception("Pydantic validation error for vision result of %s", file_path)
        return VendorExtractionResult(
            success=False,
            error=f"Validation error: {type(e).__name__}: {e}",
            tokens_used=tokens_used,
        )

    logger.info(
        "Vision extracted %d items from %s (confidence=%.2f)",
        len(quote.items),
        file_path.name,
        quote.extraction_confidence,
    )

    return VendorExtractionResult(success=True, quote=quote, tokens_used=tokens_used)


# ---------------------------------------------------------------------------
# Public API — combined entry point
# ---------------------------------------------------------------------------


async def extract_vendor_quote(
    file_path: Path,
    client: anthropic.AsyncAnthropic | None = None,
) -> VendorExtractionResult:
    """Extract vendor quote data, trying text first then vision fallback.

    Strategy:
      1. Run text extraction via PyMuPDF.
      2. If text extraction succeeds but confidence is low (< 0.4) and a
         Claude client is provided, fall back to vision extraction.
      3. If text extraction fails outright and a client is provided, attempt
         vision extraction.
      4. If no client is available, return the text result regardless of
         confidence.

    Args:
        file_path: Path to the vendor quote PDF.
        client: Optional AsyncAnthropic client. Required for vision fallback.

    Returns:
        VendorExtractionResult from the best available extraction method.
    """
    logger.info("Extracting vendor quote: %s", file_path)

    # --- Pass 1: text extraction ---
    text_result = extract_vendor_quote_text(file_path)

    needs_vision = False

    if not text_result.success:
        logger.info(
            "Text extraction failed for %s: %s — attempting vision fallback",
            file_path.name,
            text_result.error,
        )
        needs_vision = True
    elif text_result.quote is not None and text_result.quote.extraction_confidence < 0.4:
        logger.info(
            "Low text confidence (%.2f) for %s — attempting vision fallback",
            text_result.quote.extraction_confidence,
            file_path.name,
        )
        needs_vision = True

    if not needs_vision:
        return text_result

    # --- Pass 2: vision fallback ---
    if client is None:
        logger.warning(
            "Vision fallback needed for %s but no Anthropic client provided",
            file_path.name,
        )
        # Return the text result even if it is low-quality
        return text_result

    return await extract_vendor_quote_vision(file_path, client)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_vendor_quote_files(source_dir: Path) -> list[tuple[Path, str]]:
    """Walk *source_dir* and identify vendor quote PDFs.

    Inclusion criteria:
      - File extension is .pdf (case-insensitive).
      - Filename matches vendor name keywords or transactional keywords
        (PO, Order, Invoice, Quote + vendor name).

    Exclusion criteria:
      - Filename matches CA's own outgoing quote pattern: "Quote XXXXXX.pdf"
        (these are quotes Commercial Acoustics sends to GCs, not vendor quotes).
      - File is inside an "Archive" or "++Archive" subdirectory.
      - Temp / lock files starting with "~$".

    Args:
        source_dir: Root directory to search (e.g., the +ITBs Dropbox folder).

    Returns:
        List of (file_path, vendor_name_or_empty) tuples. vendor_name is the
        canonical vendor name if detected from the filename, otherwise "".
    """
    results: list[tuple[Path, str]] = []

    if not source_dir.is_dir():
        logger.error("Source directory does not exist: %s", source_dir)
        return results

    for pdf_path in sorted(source_dir.rglob("*.pdf")):
        filename = pdf_path.name

        # Skip temp files
        if filename.startswith("~$"):
            continue

        # Skip archived files
        parts = pdf_path.relative_to(source_dir).parts
        if any(part in {"Archive", "++Archive"} for part in parts[:-1]):
            logger.debug("Skipping archived file: %s", pdf_path)
            continue

        # Skip CA's own outgoing quotes
        if CA_OWN_QUOTE_PATTERN.match(filename):
            logger.debug("Skipping CA own quote: %s", pdf_path)
            continue

        # Include only files whose name contains vendor/transactional keywords
        if not VENDOR_QUOTE_INCLUDE_PATTERNS.search(filename):
            logger.debug("Skipping non-vendor PDF: %s", pdf_path)
            continue

        vendor_name = detect_vendor(filename) or ""
        results.append((pdf_path, vendor_name))

    logger.info("Found %d vendor quote candidates in %s", len(results), source_dir)
    return results
