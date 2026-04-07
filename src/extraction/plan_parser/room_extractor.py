"""Room/area extraction from architectural plan text and Bluebeam annotations.

Parses text extracted from RCPs and floor plans to identify rooms, their
numbers, ceiling heights, ceiling types, and scope tags.  Also handles
Bluebeam polygon annotation labels that carry scope + area information.

Usage:
    from src.extraction.plan_parser.room_extractor import extract_rooms

    rooms = extract_rooms(page_text, annotations=page.annotations)
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# "ROOM 101", "ROOM NO. 101", "ROOM NO 101"
_ROOM_HEADER_RE = re.compile(
    r"\bROOM\s+(?:NO\.?\s*)?(\d{2,5})\b(?:\s*[-–—]\s*(.+))?",
    re.IGNORECASE,
)

# Bare room number at start of a line followed by optional name: "101 - CONFERENCE ROOM"
_ROOM_NUMBER_LINE_RE = re.compile(
    r"^(\d{2,5})\s*[-–—]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Finish-schedule table row: "101   CONF RM   VCT    PAINT   ACT-1"
# Columns: room_no  name  floor  wall  ceiling
_FINISH_SCHEDULE_ROW_RE = re.compile(
    r"^(\d{2,5})\s{2,}(\S.*?)\s{2,}(\S+)\s{2,}(\S+)(?:\s{2,}(\S+))?",
    re.IGNORECASE | re.MULTILINE,
)

# Ceiling height: "9'-0\" AFF", "9'-0\"", "9FT", "108\"", "9 FT"
_HEIGHT_RE = re.compile(
    r"""
    (?:
        (\d{1,2})'[-\s]?(\d{1,2})"  # e.g. 9'-0" or 9'0"
        |(\d{1,2})\s*(?:FT|FEET)     # e.g. 9FT or 9 FT
        |(\d{2,3})"                   # e.g. 108"
    )
    (?:\s*AFF)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Ceiling type tag near a room: "ACT-1", "ACT-2", "GWB", "EXPOSED STRUCTURE"
_CEILING_TAG_RE = re.compile(
    r"\b(ACT-\d+|AWP-\d+|GWB|EXPOSED\s+STRUCTURE|EXPOSED|OPEN\s+TO\s+(?:ABOVE|STRUCTURE))\b",
    re.IGNORECASE,
)

# Scope tag pattern like "ACT-1", "AWP-2", "FW-1"
_SCOPE_TAG_RE = re.compile(r"\b([A-Z]{2,4}-\d+)\b")

# Open-plan area names (no room number needed)
_OPEN_AREA_RE = re.compile(
    r"\b(OPEN\s+OFFICE|LOBBY|CORRIDOR|HALLWAY|RECEPTION|WAITING\s+AREA|BREAKROOM|BREAK\s+ROOM|"
    r"CONFERENCE\s+ROOM|BOARD\s+ROOM|SERVER\s+ROOM|COPY\s+ROOM|STORAGE|RESTROOM|TOILET)\b",
    re.IGNORECASE,
)

# Bluebeam annotation label: "ACT-1 - 2,450 SF" or "ACT-1"
_BB_SCOPE_AREA_RE = re.compile(
    r"^([A-Z]{2,4}-\d+)\s*[-–]?\s*([\d,]+(?:\.\d+)?)\s*SF\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Height normalisation
# ---------------------------------------------------------------------------


def _normalise_height(raw: str) -> str | None:
    """Convert any ceiling height expression to the canonical "9'-0\\"" form."""
    m = _HEIGHT_RE.search(raw)
    if not m:
        return None
    feet_str, inches_str, ft_only, inches_only = m.groups()
    if feet_str is not None:
        feet = int(feet_str)
        inches = int(inches_str) if inches_str is not None else 0
        return f"{feet}'-{inches}\""
    if ft_only is not None:
        return f"{int(ft_only)}'-0\""
    if inches_only is not None:
        total = int(inches_only)
        feet, inches = divmod(total, 12)
        return f"{feet}'-{inches}\""
    return None


# ---------------------------------------------------------------------------
# Ceiling-type normalisation (minimal, shared with ceiling_extractor)
# ---------------------------------------------------------------------------

_CEILING_TYPE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bACT\b|\bACOUSTICAL\s+(?:CEILING\s+)?TILE\b", re.IGNORECASE), "ACT"),
    (re.compile(r"\bGWB\b|\bGYPSUM\b|\bDRYWALL\b", re.IGNORECASE), "GWB"),
    (
        re.compile(
            r"\bEXPOSED\s+STRUCTURE\b|\bOPEN\s+TO\s+(?:ABOVE|STRUCTURE)\b|\bEXPOSED\b",
            re.IGNORECASE,
        ),
        "Exposed Structure",
    ),
]


def _classify_ceiling_type(text: str) -> str | None:
    for pattern, label in _CEILING_TYPE_MAP:
        if pattern.search(text):
            return label
    return None


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def _make_room(
    room_name: str,
    room_number: str | None = None,
    floor: str | None = None,
    area_sf: Decimal | None = None,
    ceiling_height: str | None = None,
    ceiling_type: str | None = None,
    scope_tag: str | None = None,
) -> dict[str, Any]:
    return {
        "room_name": room_name.strip(),
        "room_number": room_number,
        "floor": floor,
        "area_sf": area_sf,
        "ceiling_height": ceiling_height,
        "ceiling_type": ceiling_type,
        "scope_tag": scope_tag,
    }


def _parse_annotation_rooms(annotations: list) -> list[dict[str, Any]]:
    """Extract room-like entries from Bluebeam polygon annotations."""
    rooms: list[dict[str, Any]] = []
    for ann in annotations:
        label = getattr(ann, "label", None) or (ann.get("label") if isinstance(ann, dict) else None)
        area_sf = getattr(ann, "area_sf", None) or (ann.get("area_sf") if isinstance(ann, dict) else None)
        if not label:
            continue
        # "ACT-1 - 2,450 SF" style
        m = _BB_SCOPE_AREA_RE.match(label.strip())
        if m:
            scope_tag = m.group(1).upper()
            try:
                sf = Decimal(m.group(2).replace(",", ""))
            except InvalidOperation:
                sf = area_sf
            rooms.append(
                _make_room(
                    room_name=label.strip(),
                    scope_tag=scope_tag,
                    area_sf=sf,
                )
            )
        elif _SCOPE_TAG_RE.match(label.strip()):
            # Just a scope tag with optional area from annotation object
            scope_tag = _SCOPE_TAG_RE.match(label.strip()).group(1).upper()
            try:
                sf = Decimal(str(area_sf)) if area_sf is not None else None
            except InvalidOperation:
                sf = None
            rooms.append(_make_room(room_name=label.strip(), scope_tag=scope_tag, area_sf=sf))
    return rooms


def extract_rooms(text: str, annotations: list | None = None) -> list[dict[str, Any]]:
    """Extract room information from plan text and optional Bluebeam annotations.

    Parameters
    ----------
    text:
        Full text content of one drawing page (from PyMuPDF ``page.get_text("text")``)
    annotations:
        Optional list of BluebeamAnnotation objects (or dicts) from the same page.

    Returns
    -------
    list of dicts with keys: room_name, room_number, floor, area_sf,
    ceiling_height, ceiling_type, scope_tag
    """
    rooms: list[dict[str, Any]] = []
    seen_numbers: set[str] = set()

    lines = text.splitlines()

    # ---- Pass 1: ROOM header pattern ("ROOM 101 - CONFERENCE ROOM") ----
    for i, line in enumerate(lines):
        m = _ROOM_HEADER_RE.search(line)
        if not m:
            continue
        room_no = m.group(1)
        room_name_raw = m.group(2) or ""

        # Look ahead up to 4 lines for height and ceiling tag
        context = "\n".join(lines[i : i + 5])
        height = _normalise_height(context)
        ct_match = _CEILING_TAG_RE.search(context)
        scope_match = _SCOPE_TAG_RE.search(context)
        ceiling_type: str | None = None
        scope_tag: str | None = None
        if ct_match:
            raw_ct = ct_match.group(1)
            ceiling_type = _classify_ceiling_type(raw_ct)
        if scope_match:
            scope_tag = scope_match.group(1).upper()

        # If no inline name, try next non-empty line
        if not room_name_raw:
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()
                if candidate and not _ROOM_HEADER_RE.match(candidate) and not _HEIGHT_RE.match(candidate):
                    room_name_raw = candidate
                    break

        if room_no not in seen_numbers:
            seen_numbers.add(room_no)
            rooms.append(
                _make_room(
                    room_name=room_name_raw.strip() if room_name_raw else f"ROOM {room_no}",
                    room_number=room_no,
                    ceiling_height=height,
                    ceiling_type=ceiling_type,
                    scope_tag=scope_tag,
                )
            )

    # ---- Pass 2: bare "101 - NAME" pattern (only if not already seen) ----
    for m in _ROOM_NUMBER_LINE_RE.finditer(text):
        room_no = m.group(1)
        room_name_raw = m.group(2).strip()
        if room_no in seen_numbers:
            continue
        # skip if this looks like a dimension ("12'-6\" - something")
        if re.match(r"^\d+'-", room_name_raw):
            continue
        seen_numbers.add(room_no)
        rooms.append(_make_room(room_name=room_name_raw, room_number=room_no))

    # ---- Pass 3: Finish schedule table rows ----
    for m in _FINISH_SCHEDULE_ROW_RE.finditer(text):
        room_no = m.group(1)
        if room_no in seen_numbers:
            continue
        room_name_raw = m.group(2).strip()
        ceiling_col = m.group(5)
        ceiling_type = _classify_ceiling_type(ceiling_col) if ceiling_col else None
        scope_tag = ceiling_col.upper() if ceiling_col and _SCOPE_TAG_RE.match(ceiling_col) else None
        seen_numbers.add(room_no)
        rooms.append(
            _make_room(
                room_name=room_name_raw,
                room_number=room_no,
                ceiling_type=ceiling_type,
                scope_tag=scope_tag,
            )
        )

    # ---- Pass 4: open-plan area names (no room number) ----
    open_found: set[str] = set()
    for m in _OPEN_AREA_RE.finditer(text):
        area_name = m.group(1).upper()
        if area_name in open_found:
            continue
        open_found.add(area_name)
        # Check if this area name was already captured via room header
        if any(r["room_name"].upper() == area_name for r in rooms):
            continue
        # grab a small context window around the match
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 120)
        context = text[start:end]
        height = _normalise_height(context)
        ct_match = _CEILING_TAG_RE.search(context)
        scope_match = _SCOPE_TAG_RE.search(context)
        ceiling_type = _classify_ceiling_type(ct_match.group(1)) if ct_match else None
        scope_tag = scope_match.group(1).upper() if scope_match else None
        rooms.append(
            _make_room(
                room_name=area_name,
                ceiling_height=height,
                ceiling_type=ceiling_type,
                scope_tag=scope_tag,
            )
        )

    # ---- Pass 5: Bluebeam annotations ----
    if annotations:
        annotation_rooms = _parse_annotation_rooms(annotations)
        rooms.extend(annotation_rooms)

    return rooms
