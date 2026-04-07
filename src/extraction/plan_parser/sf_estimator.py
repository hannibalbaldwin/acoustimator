"""SF Estimation from Plan Dimensions and Bluebeam Annotations.

Sources (in priority order):
1. Bluebeam polygon annotations — pre-calculated area values (highest accuracy)
2. Explicit SF labels in text — "2,450 SF", "2,450 SQ FT", etc.
3. Dimension pair parsing — "12'-6\" x 18'-0\"" room-dimension pairs (lowest accuracy)
"""

import re
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches: "45'-6\"", "45'6\"", "45'-6", "45'", "6\"", "0.5'", "45.5'"
_FT_IN_PATTERN = re.compile(
    r"""
    (?:(\d+(?:\.\d+)?)\s*'    # optional feet portion: digits, optional decimal, foot mark
       (?:\s*[-–]\s*          # optional separator: dash or en-dash with optional space
          (\d+(?:\.\d+)?)\s*  # optional inches portion
          "                   # inch mark
       )?
    )
    |                         # OR
    (?:(\d+(?:\.\d+)?)\s*")   # standalone inches: digits + inch mark
    """,
    re.VERBOSE,
)

# Matches dimension × dimension: "12'-6\" x 18'-0\"", "12.5 x 18", "12 x 18"
_DIM_PAIR_PATTERN = re.compile(
    r"""
    (                             # capture group 1: first dimension
        \d+(?:\.\d+)?             # integer or decimal feet
        (?:                       # optional feet-inches suffix
            \s*'                  # foot mark
            (?:\s*[-–]\s*         # optional dash
               \d+(?:\.\d+)?\s*"  # inches
            )?
        )?
        (?:\s*')?                 # bare foot mark without inches
    )
    \s*[xX×]\s*                   # separator: x, X, or ×
    (                             # capture group 2: second dimension
        \d+(?:\.\d+)?             # integer or decimal feet
        (?:
            \s*'
            (?:\s*[-–]\s*
               \d+(?:\.\d+)?\s*"
            )?
        )?
        (?:\s*')?
    )
    """,
    re.VERBOSE,
)

# Matches explicit SF/SQ FT labels: "2,450 SF", "±2,450 SF", "2,450.87 sq ft", etc.
_SF_LABEL_PATTERN = re.compile(
    r"""
    [±~]?                          # optional approximation prefix
    ([\d,]+(?:\.\d+)?)             # number with optional commas and decimal
    \s*                            # optional space
    (?:SF|SQ\.?\s*FT\.?)           # unit: SF, SQ FT, SQ. FT., etc.
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Bluebeam area line: "Area: 568.87 sq ft", "Area:\n568.87 sq ft"
_ANNOT_AREA_PATTERN = re.compile(
    r"Area\s*[:\s]\s*([\d,]+\.?\d*)\s*(?:sq\s*ft|SF|ft²)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_bluebeam_areas(annotations: list) -> dict[str, Decimal]:
    """Extract pre-calculated SF areas from Bluebeam polygon annotations.

    Args:
        annotations: list of annotation dicts (or BluebeamAnnotation models) with
                     at minimum the keys: annotation_type, label, area_sf, page_number.
                     May also be raw dicts with a 'content' key (raw PyMuPDF output).

    Returns:
        dict mapping label → area_sf (Decimal).
        Also includes the special key "__total__" with the sum of all areas.
        Unlabelled annotations are keyed by "page{n}_annot{i}" where n is the
        page number and i is a running index per page.
    """
    result: dict[str, Decimal] = {}
    page_counters: dict[int, int] = {}

    for annot in annotations:
        # Support both dict and Pydantic model access
        if hasattr(annot, "model_dump"):
            d = annot.model_dump()
        elif isinstance(annot, dict):
            d = annot
        else:
            continue

        area_sf: Decimal | None = None

        # --- Primary: use the pre-parsed area_sf field ---
        if d.get("area_sf") is not None:
            try:
                area_sf = Decimal(str(d["area_sf"]))
            except InvalidOperation:
                pass

        # --- Fallback: parse from raw content string (PyMuPDF-style) ---
        if area_sf is None:
            content = d.get("content", "") or ""
            m = _ANNOT_AREA_PATTERN.search(content)
            if m:
                try:
                    area_sf = Decimal(m.group(1).replace(",", ""))
                except InvalidOperation:
                    pass

        if area_sf is None:
            continue

        # --- Determine label ---
        label: str | None = d.get("label") or None
        if not label:
            # Try to extract label from content before "Area:" line
            content = d.get("content", "") or ""
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            non_area_lines = [
                ln
                for ln in lines
                if not re.match(r"Area\b", ln, re.IGNORECASE)
                and not re.match(r"Perimeter\b", ln, re.IGNORECASE)
                and not re.match(r"[\d,]+\.?\d*", ln)
            ]
            if non_area_lines:
                label = non_area_lines[0]

        if not label:
            page_num = d.get("page_number", 0)
            idx = page_counters.get(page_num, 0)
            page_counters[page_num] = idx + 1
            label = f"page{page_num}_annot{idx}"

        # Accumulate (multiple polygons can share the same scope tag)
        if label in result:
            result[label] += area_sf
        else:
            result[label] = area_sf

    total = sum(result.values(), Decimal("0"))
    result["__total__"] = total
    return result


def parse_dimension_string(dim_str: str) -> Decimal | None:
    """Parse a single dimension string to decimal feet.

    Handles:
        "45'-6\\"" → Decimal("45.5")
        "12'-0\\"" → Decimal("12.0")
        "18\\""    → Decimal("1.5")   (bare inches treated as feet-and-inches)
        "45.5'"    → Decimal("45.5")
        "45"       → Decimal("45")    (bare number treated as feet)

    Returns None if the string cannot be parsed.
    """
    s = dim_str.strip()
    m = _FT_IN_PATTERN.fullmatch(s)
    if not m:
        # Try a bare decimal / integer (assume feet)
        bare = re.fullmatch(r"(\d+(?:\.\d+)?)", s)
        if bare:
            try:
                return Decimal(bare.group(1))
            except InvalidOperation:
                return None
        return None

    feet_str, inches_str, bare_inches_str = m.group(1), m.group(2), m.group(3)

    if bare_inches_str is not None:
        # Standalone inch value — convert to feet
        try:
            return Decimal(bare_inches_str) / Decimal("12")
        except InvalidOperation:
            return None

    # Feet (+ optional inches)
    try:
        feet = Decimal(feet_str) if feet_str else Decimal("0")
        inches = Decimal(inches_str) / Decimal("12") if inches_str else Decimal("0")
        return feet + inches
    except InvalidOperation:
        return None


def extract_room_areas_from_dimensions(text: str) -> list[dict]:
    """Find room dimension pairs (W×L) in text and compute area.

    Looks for patterns like:
        "12'-6\\" x 18'-0\\""  → {area_sf: Decimal("225.0"), dimensions: "..."}
        "12.5 x 18"            → {area_sf: Decimal("225.0"), dimensions: "12.5 x 18"}
        "2,450 SF"             → handled by extract_explicit_sf_labels() instead

    Returns list of dicts:
        {
            "area_sf": Decimal,
            "dimensions": str,          # the matched raw string
            "width_ft": Decimal,
            "length_ft": Decimal,
            "source": "dimension_pair",
        }
    """
    results = []
    for m in _DIM_PAIR_PATTERN.finditer(text):
        raw = m.group(0).strip()
        w_str = m.group(1).strip()
        l_str = m.group(2).strip()

        width = parse_dimension_string(w_str)
        length = parse_dimension_string(l_str)

        if width is None or length is None:
            continue
        # Sanity-check: discard obviously wrong values (< 4 ft or > 500 ft per side)
        if width < Decimal("4") or length < Decimal("4"):
            continue
        if width > Decimal("500") or length > Decimal("500"):
            continue
        # Filter out common ceiling-tile / grid fixture sizes (e.g. "2x2", "2x4", "1x4")
        # that appear in legend text but are not room dimensions.
        area_check = width * length
        if area_check < Decimal("20"):
            continue

        area = (width * length).quantize(Decimal("0.01"))
        results.append(
            {
                "area_sf": area,
                "dimensions": raw,
                "width_ft": width,
                "length_ft": length,
                "source": "dimension_pair",
            }
        )
    return results


def extract_explicit_sf_labels(text: str) -> list[dict]:
    """Find explicit SF area labels in text.

    Patterns: "2,450 SF", "2450 SQ FT", "2,450 SQ. FT.", "±2,450 SF"

    Returns list of dicts:
        {
            "area_sf": Decimal,
            "context": str,     # ±30 chars surrounding the match
            "source": "explicit_label",
        }
    """
    results = []
    for m in _SF_LABEL_PATTERN.finditer(text):
        raw_num = m.group(1).replace(",", "")
        try:
            area = Decimal(raw_num)
        except InvalidOperation:
            continue

        # Discard implausibly small or large values
        if area < Decimal("10") or area > Decimal("500000"):
            continue

        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        context = text[start:end].replace("\n", " ").strip()

        results.append(
            {
                "area_sf": area,
                "context": context,
                "source": "explicit_label",
            }
        )
    return results


def estimate_total_sf(pages: list, prefer_bluebeam: bool = True) -> dict:
    """Main SF estimation function.

    Args:
        pages: list of PlanPage-like objects (Pydantic models or dicts) with
               at minimum: text (str), annotations (list), page_number (int).
        prefer_bluebeam: if True, use Bluebeam annotations when available (default).

    Returns:
        {
          "total_sf": Decimal | None,
          "by_scope_tag": dict[str, Decimal],   # label → area
          "source": "bluebeam" | "explicit_labels" | "dimension_parsing" | "none",
          "confidence": float,                  # 0.0–1.0
          "breakdown": list[dict],              # individual area items with source
        }
    """
    # --- Collect all annotations and text across pages ---
    all_annotations: list = []
    all_text_parts: list[str] = []

    for page in pages:
        if hasattr(page, "model_dump"):
            d = page.model_dump()
        elif isinstance(page, dict):
            d = page
        else:
            continue

        annots = d.get("annotations") or []
        all_annotations.extend(annots)

        text = d.get("text") or ""
        all_text_parts.append(text)

    combined_text = "\n".join(all_text_parts)

    # --- Strategy 1: Bluebeam polygon annotations ---
    bluebeam_areas: dict[str, Decimal] = {}
    if prefer_bluebeam and all_annotations:
        bluebeam_areas = extract_bluebeam_areas(all_annotations)
        bluebeam_total = bluebeam_areas.pop("__total__", Decimal("0"))
        if bluebeam_total > Decimal("0"):
            breakdown = [
                {
                    "label": label,
                    "area_sf": float(area),
                    "source": "bluebeam_annotation",
                }
                for label, area in bluebeam_areas.items()
            ]
            return {
                "total_sf": bluebeam_total,
                "by_scope_tag": {k: float(v) for k, v in bluebeam_areas.items()},
                "source": "bluebeam",
                "confidence": 0.95,
                "breakdown": breakdown,
            }

    # --- Strategy 2: Explicit SF labels in text ---
    sf_labels = extract_explicit_sf_labels(combined_text)
    if sf_labels:
        # Deduplicate: if the same value appears many times it's likely a label,
        # not a unique room area — keep only unique area values.
        seen: set[Decimal] = set()
        unique_labels = []
        for item in sf_labels:
            if item["area_sf"] not in seen:
                seen.add(item["area_sf"])
                unique_labels.append(item)

        if unique_labels:
            total = sum(item["area_sf"] for item in unique_labels)
            # If we only have one value, it might already be the whole-floor total;
            # don't blindly sum — just report as-is with lower confidence.
            confidence = 0.70 if len(unique_labels) > 1 else 0.60
            return {
                "total_sf": total,
                "by_scope_tag": {},
                "source": "explicit_labels",
                "confidence": confidence,
                "breakdown": [
                    {
                        "label": f"sf_label_{i}",
                        "area_sf": float(item["area_sf"]),
                        "context": item.get("context", ""),
                        "source": "explicit_label",
                    }
                    for i, item in enumerate(unique_labels)
                ],
            }

    # --- Strategy 3: Dimension pair parsing ---
    dim_areas = extract_room_areas_from_dimensions(combined_text)
    if dim_areas:
        total = sum(item["area_sf"] for item in dim_areas)
        return {
            "total_sf": total,
            "by_scope_tag": {},
            "source": "dimension_parsing",
            "confidence": 0.40,
            "breakdown": [
                {
                    "label": f"dim_pair_{i}",
                    "area_sf": float(item["area_sf"]),
                    "dimensions": item.get("dimensions", ""),
                    "source": "dimension_pair",
                }
                for i, item in enumerate(dim_areas)
            ],
        }

    # --- No data found ---
    return {
        "total_sf": None,
        "by_scope_tag": {},
        "source": "none",
        "confidence": 0.0,
        "breakdown": [],
    }
