"""Scope type suggestion from extracted plan data and Bluebeam annotations.

Given rooms, ceiling specs, and annotations from a drawing, produce a ranked
list of ScopeSuggestion dicts that feed directly into Phase 3 cost models.

Priority order (highest → lowest confidence):
  1. Bluebeam polygon annotation with explicit scope tag label  (0.95)
  2. Ceiling spec with explicit scope_tag                       (0.85)
  3. Room ceiling_type inference                                (0.75)
  4. Bluebeam color hint                                        (0.70)
  5. Spec section numbers found in raw text                     (0.65)
  6. Keyword scan in raw text                                   (0.50)

Usage:
    from src.extraction.plan_parser.scope_suggester import suggest_scopes

    suggestions = suggest_scopes(rooms, ceiling_specs, annotations, text)
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Approximate Bluebeam color → scope type hint
# Colors are "#rrggbb" hex strings; we classify by dominant channel.
COLOR_SCOPE_HINTS: dict[str, str | None] = {
    "red": "ACT",
    "blue": "AWP",
    "green": "FW",
    "orange": "Baffles",
    "yellow": None,  # deduct area — skip
}

SPEC_SECTION_MAP: dict[str, str] = {
    "09 51": "ACT",
    "09 84": "SM",
    "09 77": "FW",
    "09 72": "FW",
    "09 64": "WW",
    "06 40": "WW",
}

# Ceiling type → scope type (None means skip — not acoustic work)
_CEILING_TYPE_SCOPE: dict[str, str | None] = {
    "ACT": "ACT",
    "GWB": None,  # not acoustic work
    "Exposed Structure": None,  # skip unless baffles noted elsewhere
    "Baffles": "Baffles",
    "CLOUD": "Baffles",
    "WW": "WW",
    "FW": "FW",
    "AWP": "AWP",
    "SM": "SM",
    "RPG": "RPG",
}

# Scope tag prefix regex: "ACT-1", "AWP-2", "FW-3", etc.
_SCOPE_TAG_RE = re.compile(r"\b([A-Z]{2,5}-\d+)\b")

# Keyword patterns for text scan (confidence 0.50)
_KEYWORD_SCOPE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bACOUSTICAL\s+CEILING\s+TILE\b|\bACT\b", re.IGNORECASE), "ACT"),
    (re.compile(r"\bSOUND\s+MASKING\b|\bLENCORE\b|\bVEKTOR\b|\b\bSM\b", re.IGNORECASE), "SM"),
    (re.compile(r"\bFABRIC\s+WALL\b|\bSNAP.?TEX\b|\bFW\b", re.IGNORECASE), "FW"),
    (re.compile(r"\bACOUSTIC\s+WALL\s+PANEL\b|\bAWP\b", re.IGNORECASE), "AWP"),
    (re.compile(r"\bWOOD\s+CEILING\b|\bWOODWORKS\b|\bWW\b", re.IGNORECASE), "WW"),
    (re.compile(r"\bBAFFLE\b|\bCLOUD\s+PANEL\b|\bACOUSTIC\s+CLOUD\b", re.IGNORECASE), "Baffles"),
    (re.compile(r"\bRPG\b|\bDIFFUSER\b", re.IGNORECASE), "RPG"),
]

# ---------------------------------------------------------------------------
# Color classification
# ---------------------------------------------------------------------------


def _color_to_scope_hint(hex_color: str | None) -> str | None:
    """Map an annotation color (#rrggbb) to a scope type hint.

    Uses the dominant RGB channel and rough thresholds to approximate the
    named color labels in COLOR_SCOPE_HINTS.  Returns None if the color is
    unrecognised or maps to a deduct (yellow).
    """
    if not hex_color:
        return None
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        return None
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None

    # Classify by dominant channel with simple heuristics.
    # Yellow must be checked before orange (both have high R and G).
    if r > 200 and g > 200 and b < 80:
        named = "yellow"
    elif r > 180 and g < 100 and b < 100:
        named = "red"
    elif r < 100 and g < 100 and b > 180:
        named = "blue"
    elif r < 100 and g > 180 and b < 100:
        named = "green"
    elif r > 180 and g > 80 and b < 80:
        named = "orange"
    else:
        return None

    return COLOR_SCOPE_HINTS.get(named)


# ---------------------------------------------------------------------------
# Scope type → canonical form and auto-numbering
# ---------------------------------------------------------------------------

_SCOPE_TYPE_ALIASES: dict[str, str] = {
    "BAFFLES": "Baffles",
    "CLOUD": "Baffles",
    "WOODWORKS": "WW",
    "WOOD": "WW",
}


def _normalise_scope_type(raw: str) -> str:
    """Return the canonical scope_type string."""
    upper = raw.strip().upper()
    return _SCOPE_TYPE_ALIASES.get(upper, upper)


def _scope_type_for_ceiling(ceiling_type: str | None) -> str | None:
    """Map a ceiling_type string to a scope_type, or None if not acoustic."""
    if ceiling_type is None:
        return None
    # Direct lookup first
    result = _CEILING_TYPE_SCOPE.get(ceiling_type)
    if result is not None or ceiling_type in _CEILING_TYPE_SCOPE:
        return result
    # Fuzzy: check if ceiling_type *contains* a known key
    ct_upper = ceiling_type.upper()
    for key, val in _CEILING_TYPE_SCOPE.items():
        if key.upper() in ct_upper:
            return val
    return None


# ---------------------------------------------------------------------------
# Building and merging suggestions
# ---------------------------------------------------------------------------


def _make_suggestion(
    scope_type: str,
    scope_tag: str,
    area_sf: Decimal | None,
    length_lf: Decimal | None,
    product_hint: str | None,
    confidence: float,
    source: str,
    rooms: list[str],
) -> dict[str, Any]:
    return {
        "scope_type": scope_type,
        "scope_tag": scope_tag,
        "area_sf": area_sf,
        "length_lf": length_lf,
        "product_hint": product_hint,
        "confidence": confidence,
        "source": source,
        "rooms": rooms,
    }


def _merge_suggestions(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge suggestions with identical scope_tag: highest confidence wins,
    areas are summed, rooms are unioned.

    Suggestions without an explicit scope_tag will have been auto-numbered
    before this step and are merged only if they share the same generated tag.
    """
    merged: dict[str, dict[str, Any]] = {}
    for s in suggestions:
        tag = s["scope_tag"]
        if tag not in merged:
            merged[tag] = dict(s)
            merged[tag]["rooms"] = list(s["rooms"])
        else:
            existing = merged[tag]
            # Keep highest confidence
            if s["confidence"] > existing["confidence"]:
                existing["confidence"] = s["confidence"]
                existing["source"] = s["source"]
            # Sum areas where available
            if s["area_sf"] is not None:
                existing["area_sf"] = (existing["area_sf"] or Decimal(0)) + s["area_sf"]
            if s["length_lf"] is not None:
                existing["length_lf"] = (existing["length_lf"] or Decimal(0)) + s["length_lf"]
            # Union rooms
            for room in s["rooms"]:
                if room not in existing["rooms"]:
                    existing["rooms"].append(room)
            # Prefer a non-None product_hint
            if existing["product_hint"] is None and s["product_hint"] is not None:
                existing["product_hint"] = s["product_hint"]

    # Return sorted by confidence descending, then scope_tag for stability
    return sorted(merged.values(), key=lambda x: (-x["confidence"], x["scope_tag"]))


def _auto_number_suggestions(
    suggestions: list[dict[str, Any]],
    existing_tags: set[str],
) -> list[dict[str, Any]]:
    """Assign "TYPE-N" tags to suggestions that lack one.

    For each scope_type seen, we maintain a counter.  Suggestions that
    already carry an explicit scope_tag are left untouched; their tag is
    registered so the counter doesn't collide.
    """
    # First pass: collect explicit tags per type
    type_max: dict[str, int] = {}
    for s in suggestions:
        tag = s["scope_tag"]
        if tag:
            m = re.match(r"^([A-Z]+)-(\d+)$", tag)
            if m:
                stype, num = m.group(1), int(m.group(2))
                type_max[stype] = max(type_max.get(stype, 0), num)
    # Also account for tags already known from higher-priority sources
    for tag in existing_tags:
        m = re.match(r"^([A-Z]+)-(\d+)$", tag)
        if m:
            stype, num = m.group(1), int(m.group(2))
            type_max[stype] = max(type_max.get(stype, 0), num)

    type_counter: dict[str, int] = dict(type_max)

    numbered: list[dict[str, Any]] = []
    for s in suggestions:
        if s["scope_tag"]:
            numbered.append(s)
            continue
        stype = s["scope_type"]
        next_n = type_counter.get(stype, 0) + 1
        type_counter[stype] = next_n
        s = dict(s)
        s["scope_tag"] = f"{stype}-{next_n}"
        numbered.append(s)
    return numbered


# ---------------------------------------------------------------------------
# Helper: access a field from either a dict or an object attribute
# ---------------------------------------------------------------------------


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Get *key* from *obj* whether it is a dict or an object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def suggest_scopes(
    rooms: list[dict],
    ceiling_specs: list[dict],
    annotations: list[dict],
    text: str = "",
) -> list[dict[str, Any]]:
    """Generate scope suggestions from extracted plan data.

    Parameters
    ----------
    rooms:
        List of room dicts from room_extractor (keys: room_name, ceiling_type,
        area_sf, scope_tag, etc.).
    ceiling_specs:
        List of ceiling spec dicts from ceiling_extractor (keys: ceiling_type,
        scope_tag, area_sf, product_spec, etc.).
    annotations:
        List of Bluebeam annotation dicts or BluebeamAnnotation objects
        (keys: annotation_type, label, area_sf, length_lf, color).
    text:
        Raw concatenated drawing text for spec section and keyword scanning.

    Returns
    -------
    List of ScopeSuggestion-like dicts, deduplicated and sorted by confidence.
    """
    raw_suggestions: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. Bluebeam polygon annotations with explicit scope tag (conf 0.95)
    # ------------------------------------------------------------------
    for ann in annotations:
        # Support both dict and Pydantic model objects
        label: str | None = _get(ann, "label")
        area_sf_raw = _get(ann, "area_sf")
        length_lf_raw = _get(ann, "length_lf")
        ann_type: str = _get(ann, "annotation_type") or ""
        color: str | None = _get(ann, "color")

        if not label:
            continue

        label_stripped = label.strip()

        # Look for explicit scope tag in label e.g. "ACT-1", "ACT-1 - 2,450 SF"
        tag_match = _SCOPE_TAG_RE.search(label_stripped)
        if tag_match and ann_type in ("polygon", "measurement") or (tag_match and area_sf_raw):
            scope_tag = tag_match.group(1).upper()
            scope_prefix = scope_tag.split("-")[0]
            scope_type = _normalise_scope_type(scope_prefix)
            try:
                area_sf: Decimal | None = (
                    Decimal(str(area_sf_raw)) if area_sf_raw is not None else None
                )
            except InvalidOperation:
                area_sf = None
            try:
                length_lf: Decimal | None = (
                    Decimal(str(length_lf_raw)) if length_lf_raw is not None else None
                )
            except InvalidOperation:
                length_lf = None
            raw_suggestions.append(
                _make_suggestion(
                    scope_type=scope_type,
                    scope_tag=scope_tag,
                    area_sf=area_sf,
                    length_lf=length_lf,
                    product_hint=None,
                    confidence=0.95,
                    source="bluebeam_annotation",
                    rooms=[],
                )
            )
            continue  # Don't also emit a lower-confidence color hint for this annotation

        # ------------------------------------------------------------------
        # 2. Bluebeam color hint (conf 0.70) — for annotations without explicit tag
        # ------------------------------------------------------------------
        color_scope = _color_to_scope_hint(color)
        if color_scope is not None:  # None means yellow (deduct) or unknown
            try:
                area_sf = Decimal(str(area_sf_raw)) if area_sf_raw is not None else None
            except InvalidOperation:
                area_sf = None
            try:
                length_lf = Decimal(str(length_lf_raw)) if length_lf_raw is not None else None
            except InvalidOperation:
                length_lf = None
            raw_suggestions.append(
                _make_suggestion(
                    scope_type=color_scope,
                    scope_tag="",  # will be auto-numbered
                    area_sf=area_sf,
                    length_lf=length_lf,
                    product_hint=None,
                    confidence=0.70,
                    source="bluebeam_annotation",
                    rooms=[],
                )
            )

    # ------------------------------------------------------------------
    # 3. Ceiling specs with scope_tag (conf 0.85)
    # ------------------------------------------------------------------
    for spec in ceiling_specs:
        ceiling_type: str = _get(spec, "ceiling_type") or ""
        scope_tag_raw: str | None = _get(spec, "scope_tag")
        area_sf_raw = _get(spec, "area_sf")
        product_spec: str | None = _get(spec, "product_spec")

        scope_type = _scope_type_for_ceiling(ceiling_type)
        if scope_type is None:
            continue  # GWB / Exposed Structure — skip

        try:
            area_sf = Decimal(str(area_sf_raw)) if area_sf_raw is not None else None
        except InvalidOperation:
            area_sf = None

        # If the spec carries an explicit tag use it; otherwise leave blank for auto-numbering
        tag = scope_tag_raw.upper() if scope_tag_raw else ""

        raw_suggestions.append(
            _make_suggestion(
                scope_type=scope_type,
                scope_tag=tag,
                area_sf=area_sf,
                length_lf=None,
                product_hint=product_spec,
                confidence=0.85,
                source="ceiling_spec",
                rooms=[],
            )
        )

    # ------------------------------------------------------------------
    # 4. Room ceiling types (conf 0.75)
    # ------------------------------------------------------------------
    for room in rooms:
        ceiling_type_r: str | None = _get(room, "ceiling_type")
        scope_tag_r: str | None = _get(room, "scope_tag")
        room_name: str = _get(room, "room_name") or ""
        area_sf_raw = _get(room, "area_sf")

        # If room already carries an explicit scope_tag, use that directly
        scope_type_r: str | None = None
        if scope_tag_r:
            prefix = scope_tag_r.split("-")[0]
            scope_type_r = _normalise_scope_type(prefix)
        else:
            scope_type_r = _scope_type_for_ceiling(ceiling_type_r)

        if scope_type_r is None:
            continue

        try:
            area_sf = Decimal(str(area_sf_raw)) if area_sf_raw is not None else None
        except InvalidOperation:
            area_sf = None

        raw_suggestions.append(
            _make_suggestion(
                scope_type=scope_type_r,
                scope_tag=scope_tag_r.upper() if scope_tag_r else "",
                area_sf=area_sf,
                length_lf=None,
                product_hint=None,
                confidence=0.75,
                source="room_tag",
                rooms=[room_name] if room_name else [],
            )
        )

    # ------------------------------------------------------------------
    # 5. Spec section numbers in text (conf 0.65)
    # ------------------------------------------------------------------
    if text:
        # Match patterns like "09 51 00", "09 51", "09.51.00"
        spec_section_re = re.compile(r"\b(0[0-9]\s*[\s.]\s*\d{2})(?:\s*[\s.]\s*\d{2})?\b")
        found_spec_types: set[str] = set()
        for m in spec_section_re.finditer(text):
            raw_section = m.group(1)
            # Normalise to "XX XX" (two groups of 2 digits)
            digits = re.sub(r"[^0-9]", "", raw_section)
            if len(digits) >= 4:
                normalised = f"{digits[:2]} {digits[2:4]}"
                scope_type_s = SPEC_SECTION_MAP.get(normalised)
                if scope_type_s and scope_type_s not in found_spec_types:
                    found_spec_types.add(scope_type_s)
                    raw_suggestions.append(
                        _make_suggestion(
                            scope_type=scope_type_s,
                            scope_tag="",  # will be auto-numbered
                            area_sf=None,
                            length_lf=None,
                            product_hint=None,
                            confidence=0.65,
                            source="spec_section",
                            rooms=[],
                        )
                    )

    # ------------------------------------------------------------------
    # 6. Keyword scan in text (conf 0.50)
    # ------------------------------------------------------------------
    if text:
        found_kw_types: set[str] = set()
        for pattern, scope_type_k in _KEYWORD_SCOPE:
            if pattern.search(text) and scope_type_k not in found_kw_types:
                found_kw_types.add(scope_type_k)
                raw_suggestions.append(
                    _make_suggestion(
                        scope_type=scope_type_k,
                        scope_tag="",  # will be auto-numbered
                        area_sf=None,
                        length_lf=None,
                        product_hint=None,
                        confidence=0.50,
                        source="keyword_scan",
                        rooms=[],
                    )
                )

    # ------------------------------------------------------------------
    # Auto-number any suggestions that are missing a scope_tag
    # ------------------------------------------------------------------
    # Collect all explicit tags so auto-numbering won't collide
    explicit_tags: set[str] = {s["scope_tag"] for s in raw_suggestions if s["scope_tag"]}
    numbered = _auto_number_suggestions(raw_suggestions, existing_tags=explicit_tags)

    # ------------------------------------------------------------------
    # Deduplicate by merging same scope_tag entries
    # ------------------------------------------------------------------
    return _merge_suggestions(numbered)
