"""Wall panel and fabric wall extraction from interior elevation drawings.

Parses text extracted from elevation drawings and Bluebeam annotations to
identify acoustic wall panels (AWP) and fabric wall systems (FW / Snap-Tex),
their areas, panel dimensions, and linear footage for wainscot/chair rail.

Usage:
    from src.extraction.plan_parser.wall_extractor import extract_wall_treatments

    treatments = extract_wall_treatments(page_text, annotations=page.annotations)
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Bluebeam annotation label scope tag: "AWP-1", "FW-2", etc.
_SCOPE_TAG_RE = re.compile(r"\b([A-Z]{2,4}-\d+)\b")

# "AWP-1 - 2,300 SF" or "FW-2 - 450 SF"
_BB_SCOPE_AREA_RE = re.compile(
    r"^([A-Z]{2,4}-\d+)\s*[-–]?\s*([\d,]+(?:\.\d+)?)\s*SF\s*$",
    re.IGNORECASE,
)

# Keywords that identify an AWP annotation
_AWP_KEYWORDS_RE = re.compile(
    r"\b(AWP|ACOUSTIC\s+WALL\s+PANELS?|WALL\s+PANELS?|FABRIC[- ]?WRAPPED)\b",
    re.IGNORECASE,
)

# Keywords that identify a FW / Snap-Tex annotation
_FW_KEYWORDS_RE = re.compile(
    r"\b(FW|FABRIC\s+WALL|SNAP[- ]?TEX)\b",
    re.IGNORECASE,
)

# ---- Text patterns --------------------------------------------------------

# "FABRIC WALL - 450 SF", "ACOUSTIC WALL PANELS - 2,300 SF"
_TREATMENT_AREA_RE = re.compile(
    r"(ACOUSTIC\s+WALL\s+PANELS?|FABRIC\s+WALL|AWP|FW|SNAP[- ]?TEX|WALL\s+PANELS?)"
    r"\s*[-–—]\s*([\d,]+(?:\.\d+)?)\s*SF",
    re.IGNORECASE,
)

# Scope tag with optional dash and SF: "AWP-1 - 2,300 SF" or just "AWP-1"
_SCOPE_TAG_WITH_AREA_RE = re.compile(
    r"\b(AWP|FW)-(\d+)\b(?:\s*[-–]?\s*([\d,]+(?:\.\d+)?)\s*SF)?",
    re.IGNORECASE,
)

# Wainscot / chair rail linear footage: "WAINSCOT @ 36\"" or "CHAIR RAIL @ 48\""
_WAINSCOT_RE = re.compile(
    r"(WAINSCOT|CHAIR\s+RAIL)\s*@\s*(\d{2,3})[\"']?",
    re.IGNORECASE,
)

# Wainscot with linear footage: "WAINSCOT - 120 LF @ 36\""
_WAINSCOT_LF_RE = re.compile(
    r"(WAINSCOT|CHAIR\s+RAIL)\s*[-–]?\s*([\d,]+(?:\.\d+)?)\s*LF(?:\s*@\s*(\d{1,3})[\"']?)?",
    re.IGNORECASE,
)

# Panel dimensions: "4'x8' PANELS", "48"x96"", "24" x 48""
_PANEL_DIM_RE = re.compile(
    r"""
    (?:
        (\d{1,2})'[-\s]?x[-\s]?(\d{1,2})'  # e.g. 4'x8'
        |(\d{2,3})["″]\s*[xX]\s*(\d{2,3})["″]  # e.g. 48"x96"
    )
    \s*(?:PANELS?|AWP|WALL\s+PANELS?)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Panel count: "12 PANELS", "(8) PANELS"
_PANEL_COUNT_RE = re.compile(
    r"\(?(\d+)\)?\s*(?:EA\.?|PANELS?|PCS?\.?)\b",
    re.IGNORECASE,
)

# Area SF stated inline: "225 SF", "2,450 SF"
_AREA_SF_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*SF", re.IGNORECASE)

# Product hints: Snap-Tex brand names, fabric panel brands
_PRODUCT_RE = re.compile(
    r"\b(SNAP[- ]?TEX|GUILFORD\s+OF\s+MAINE|MAHARAM|DESIGNTEX|ACOUSTIMAC|"
    r"WHISPERWALL|FABRIC\s+SYSTEMS?\s+INT(?:ERN?\.?)?|FSI|KINETICS|"
    r"ECHO\s+ELIMINATOR|SONEX|AUDIMUTE)\b",
    re.IGNORECASE,
)

# Location / room reference near a treatment tag
_LOCATION_RE = re.compile(
    r"(?:ROOM|RM\.?|SUITE?|CORRIDOR|LOBBY|OFFICE|CONFERENCE|BOARD\s+ROOM|"
    r"RECEPTION|WAITING|HALLWAY)\s*(?:NO\.?\s*)?(\w+)",
    re.IGNORECASE,
)

# Height expressed as X' or X'-Y" or Xft
_HEIGHT_RE = re.compile(
    r"""
    (?:
        (\d{1,2})'\s*[-–]?\s*(\d{1,2})"  # e.g. 8'-0" or 8'6"
        |(\d{1,2})'\s*(?![xX\d])          # e.g. 8' (not followed by x or digit → not width)
        |(\d{1,2})\s*(?:FT|FEET)\b        # e.g. 8FT
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _parse_sf(raw: str) -> Decimal | None:
    """Parse a numeric string with optional commas into a Decimal SF value."""
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def _classify_type(label: str) -> str:
    """Return 'AWP', 'FW', or 'unknown' based on label text."""
    upper = label.upper()
    # FW / Snap-Tex takes priority over generic wall panel
    if _FW_KEYWORDS_RE.search(upper):
        return "FW"
    if _AWP_KEYWORDS_RE.search(upper):
        return "AWP"
    # Pure scope-tag heuristic
    m = _SCOPE_TAG_RE.search(upper)
    if m:
        tag = m.group(1).upper()
        if tag.startswith("FW"):
            return "FW"
        if tag.startswith("AWP"):
            return "AWP"
    return "unknown"


def _extract_panel_dims(context: str) -> tuple[Decimal | None, Decimal | None]:
    """Return (width_ft, height_ft) from dimension strings in the context window.

    Handles both foot-form ("4'x8'") and inch-form ("48\"x96\"").
    Convention: width × height (narrower × taller).
    """
    m = _PANEL_DIM_RE.search(context)
    if not m:
        return None, None
    ft_w, ft_h, in_w, in_h = m.groups()
    if ft_w is not None:
        w = Decimal(ft_w)
        h = Decimal(ft_h)
    else:
        w = Decimal(in_w) / Decimal("12")
        h = Decimal(in_h) / Decimal("12")
    return w, h


def _extract_height(context: str) -> Decimal | None:
    """Return the first standalone height value found (feet as Decimal)."""
    m = _HEIGHT_RE.search(context)
    if not m:
        return None
    ft_str, in_str, ft_only, ft_word = m.groups()
    if ft_str is not None:
        feet = Decimal(ft_str)
        inches = Decimal(in_str) if in_str else Decimal("0")
        return feet + inches / Decimal("12")
    if ft_only is not None:
        return Decimal(ft_only)
    if ft_word is not None:
        return Decimal(ft_word)
    return None


def _extract_product(context: str) -> str | None:
    m = _PRODUCT_RE.search(context)
    return m.group(0).strip() if m else None


def _extract_location(context: str) -> str | None:
    m = _LOCATION_RE.search(context)
    return m.group(0).strip() if m else None


def _make_treatment(
    treatment_type: str = "unknown",
    scope_tag: str | None = None,
    area_sf: Decimal | None = None,
    length_lf: Decimal | None = None,
    height_ft: Decimal | None = None,
    width_ft: Decimal | None = None,
    product_hint: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    return {
        "treatment_type": treatment_type,
        "scope_tag": scope_tag,
        "area_sf": area_sf,
        "length_lf": length_lf,
        "height_ft": height_ft,
        "width_ft": width_ft,
        "product_hint": product_hint,
        "location": location,
    }


# ---------------------------------------------------------------------------
# Annotation parsing
# ---------------------------------------------------------------------------


def _parse_annotation_treatments(annotations: list) -> list[dict[str, Any]]:
    """Extract wall treatments from Bluebeam polygon annotations."""
    results: list[dict[str, Any]] = []

    for ann in annotations:
        # Support both Pydantic models and plain dicts
        label = getattr(ann, "label", None) or (ann.get("label") if isinstance(ann, dict) else None)
        area_sf = getattr(ann, "area_sf", None) or (ann.get("area_sf") if isinstance(ann, dict) else None)
        length_lf = getattr(ann, "length_lf", None) or (ann.get("length_lf") if isinstance(ann, dict) else None)

        if not label:
            continue

        label_str = label.strip()
        upper = label_str.upper()

        # Check if this annotation concerns wall treatments at all
        is_awp = bool(_AWP_KEYWORDS_RE.search(upper)) or upper.startswith("AWP")
        is_fw = bool(_FW_KEYWORDS_RE.search(upper)) or upper.startswith("FW")
        # Also match scope tags like "AWP-1 - 2,300 SF"
        scope_m = _SCOPE_TAG_RE.search(upper)
        if scope_m:
            tag_prefix = scope_m.group(1)
            if tag_prefix.startswith("AWP"):
                is_awp = True
            elif tag_prefix.startswith("FW"):
                is_fw = True

        if not (is_awp or is_fw):
            continue

        treatment_type = "FW" if is_fw else "AWP"

        # Try "AWP-1 - 2,300 SF" format first
        bb_m = _BB_SCOPE_AREA_RE.match(label_str)
        if bb_m:
            scope_tag = bb_m.group(1).upper()
            sf = _parse_sf(bb_m.group(2))
            results.append(
                _make_treatment(
                    treatment_type=treatment_type,
                    scope_tag=scope_tag,
                    area_sf=sf,
                    product_hint=_extract_product(label_str),
                )
            )
            continue

        # Bare scope tag, pull area from annotation object
        scope_tag = scope_m.group(1).upper() if scope_m else None
        try:
            sf = Decimal(str(area_sf)) if area_sf is not None else None
        except InvalidOperation:
            sf = None
        try:
            lf = Decimal(str(length_lf)) if length_lf is not None else None
        except InvalidOperation:
            lf = None

        results.append(
            _make_treatment(
                treatment_type=treatment_type,
                scope_tag=scope_tag,
                area_sf=sf,
                length_lf=lf,
                product_hint=_extract_product(label_str),
                location=_extract_location(label_str),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Text parsing
# ---------------------------------------------------------------------------


def _parse_text_treatments(text: str) -> list[dict[str, Any]]:
    """Extract wall treatments from raw plan text."""
    results: list[dict[str, Any]] = []
    lines = text.splitlines()
    seen_tags: set[str] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # ---- 1. Wainscot / chair rail (linear footage item) ----------------
        lf_m = _WAINSCOT_LF_RE.search(stripped)
        if lf_m:
            lf = _parse_sf(lf_m.group(2))
            height_in = lf_m.group(3)  # e.g. "36" inches
            height_ft = Decimal(height_in) / Decimal("12") if height_in else None
            results.append(
                _make_treatment(
                    treatment_type="AWP",
                    length_lf=lf,
                    height_ft=height_ft,
                    location=_extract_location(stripped),
                )
            )
            continue

        # Wainscot without explicit LF (just records the height for reference)
        wain_m = _WAINSCOT_RE.search(stripped)
        if wain_m:
            height_in = wain_m.group(2)
            height_ft = Decimal(height_in) / Decimal("12")
            results.append(
                _make_treatment(
                    treatment_type="AWP",
                    height_ft=height_ft,
                    location=_extract_location(stripped),
                )
            )
            continue

        # ---- 2. Treatment label + area: "FABRIC WALL - 450 SF" -------------
        area_m = _TREATMENT_AREA_RE.search(stripped)
        if area_m:
            raw_type = area_m.group(1).upper()
            sf = _parse_sf(area_m.group(2))
            treatment_type = _classify_type(raw_type)
            # Grab context for extra metadata
            ctx = "\n".join(lines[max(0, i - 2) : i + 3])
            width_ft, height_ft = _extract_panel_dims(ctx)
            results.append(
                _make_treatment(
                    treatment_type=treatment_type,
                    area_sf=sf,
                    height_ft=height_ft,
                    width_ft=width_ft,
                    product_hint=_extract_product(ctx),
                    location=_extract_location(ctx),
                )
            )
            continue

        # ---- 3. Scope tags: "AWP-1", "AWP-1 - 2,300 SF", "FW-2" -----------
        for m in _SCOPE_TAG_WITH_AREA_RE.finditer(stripped):
            prefix = m.group(1).upper()  # "AWP" or "FW"
            number = m.group(2)
            scope_tag = f"{prefix}-{number}"
            if scope_tag in seen_tags:
                continue
            seen_tags.add(scope_tag)

            sf_raw = m.group(3)
            sf = _parse_sf(sf_raw) if sf_raw else None

            # If no inline SF, scan the surrounding lines for one
            ctx = "\n".join(lines[max(0, i - 2) : i + 4])
            if sf is None:
                sf_m = _AREA_SF_RE.search(ctx)
                sf = _parse_sf(sf_m.group(1)) if sf_m else None

            width_ft, height_ft = _extract_panel_dims(ctx)

            # Panel count × size → area estimate
            if sf is None and width_ft is not None and height_ft is not None:
                count_m = _PANEL_COUNT_RE.search(ctx)
                if count_m:
                    count = Decimal(count_m.group(1))
                    sf = count * width_ft * height_ft

            treatment_type = "FW" if prefix == "FW" else "AWP"

            results.append(
                _make_treatment(
                    treatment_type=treatment_type,
                    scope_tag=scope_tag,
                    area_sf=sf,
                    height_ft=height_ft,
                    width_ft=width_ft,
                    product_hint=_extract_product(ctx),
                    location=_extract_location(ctx),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_wall_treatments(text: str, annotations: list | None = None) -> list[dict[str, Any]]:
    """Extract wall panel and fabric wall areas from plan text.

    Processes both Bluebeam polygon annotations (highest confidence) and raw
    text extracted from interior elevation drawings.

    Parameters
    ----------
    text:
        Full text content of one drawing page (from PyMuPDF ``page.get_text("text")``)
    annotations:
        Optional list of BluebeamAnnotation objects (or plain dicts) from the same page.

    Returns
    -------
    list of dicts with keys:
        treatment_type  - "AWP" | "FW" | "unknown"
        scope_tag       - e.g. "AWP-1", "FW-2", or None
        area_sf         - Decimal | None — square footage (from annotation or text)
        length_lf       - Decimal | None — linear footage (wainscot / chair rail)
        height_ft       - Decimal | None — panel height in decimal feet
        width_ft        - Decimal | None — panel width in decimal feet
        product_hint    - str | None — any product name found nearby
        location        - str | None — room / wall reference
    """
    treatments: list[dict[str, Any]] = []

    # Annotations carry computed areas and are the most reliable source
    if annotations:
        treatments.extend(_parse_annotation_treatments(annotations))

    # Text extraction catches callouts, schedules, and notes
    treatments.extend(_parse_text_treatments(text))

    return treatments
