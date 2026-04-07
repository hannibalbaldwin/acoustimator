"""Ceiling specification extraction from architectural plan text and Bluebeam annotations.

Detects ceiling types (ACT, GWB, Exposed Structure, Baffles, FW, WW, SM),
grid patterns, product specs, scope tags, and area (SF) from drawing text and
Bluebeam polygon annotation labels.

Usage:
    from src.extraction.plan_parser.ceiling_extractor import extract_ceiling_specs

    specs = extract_ceiling_specs(page_text, annotations=page.annotations)
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Ceiling type classification rules
# Order matters — more specific patterns first.
# ---------------------------------------------------------------------------

_CEILING_RULES: list[tuple[re.Pattern, str]] = [
    # ACT variants
    (
        re.compile(
            r"\bACOUSTICAL\s+(?:CEILING\s+)?TILE\b|\bACOUSTICAL\s+TILE\b|\bACT\b",
            re.IGNORECASE,
        ),
        "ACT",
    ),
    # Gypsum / drywall
    (re.compile(r"\bGWB\b|\bGYPSUM\b|\bDRYWALL\b|\bDRY\s+WALL\b", re.IGNORECASE), "GWB"),
    # Exposed / open structure
    (
        re.compile(
            r"\bEXPOSED\s+STRUCTURE\b|\bOPEN\s+TO\s+(?:ABOVE|STRUCTURE)\b|\bEXPOSED\b",
            re.IGNORECASE,
        ),
        "Exposed Structure",
    ),
    # Baffles / clouds / hanging elements
    (re.compile(r"\bBAFFLE\b|\bCLOUD\b|\bHANGING\b", re.IGNORECASE), "Baffles"),
    # Fabric wall / Snap-Tex
    (re.compile(r"\bFABRIC\s+WALL\b|\bSNAP-?TEX\b", re.IGNORECASE), "FW"),
    # Wood systems
    (re.compile(r"\bWOOD(?:WORKS)?\b|\bLINEAR\s+WOOD\b", re.IGNORECASE), "WW"),
    # Sound masking
    (re.compile(r"\bSOUND\s+MASKING\b|\bMASKING\s+SYSTEM\b", re.IGNORECASE), "SM"),
]

# ---------------------------------------------------------------------------
# Grid pattern detection
# ---------------------------------------------------------------------------

# Matches "2X2", "2x4", "2 X 4", "24X24", "24X48", "1x4"
_GRID_RE = re.compile(
    r"\b((?:1|2|24|48)\s*[xX]\s*(?:2|4|24|48))\b",
)

# Normalise e.g. "24X48" -> "2x4", "24X24" -> "2x2"
_GRID_NORM: dict[str, str] = {
    "24x24": "2x2",
    "24x48": "2x4",
    "48x24": "2x4",
    "2x2": "2x2",
    "2x4": "2x4",
    "4x2": "2x4",
    "1x4": "1x4",
    "4x1": "1x4",
}


def _normalise_grid(raw: str) -> str:
    key = re.sub(r"\s+", "", raw).lower()
    return _GRID_NORM.get(key, raw.lower())


# ---------------------------------------------------------------------------
# Height normalisation (reuse logic from room_extractor)
# ---------------------------------------------------------------------------

_HEIGHT_RE = re.compile(
    r"""
    (?:
        (\d{1,2})'[-\s]?(\d{1,2})"  # e.g. 9'-0" or 9'0"
        |(\d{1,2})\s*(?:FT|FEET)     # e.g. 9FT
        |(\d{2,3})"                   # e.g. 108"
    )
    (?:\s*AFF)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalise_height(raw: str) -> str | None:
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
# Scope tag detection
# ---------------------------------------------------------------------------

# Matches "ACT-1", "ACT-2A", "AWP-1", "FW-1", "WW-2", "SM-1" etc.
_SCOPE_TAG_RE = re.compile(r"\b([A-Z]{2,4}-\d+[A-Z]?)\b")

# Bluebeam label: "ACT-1 - 2,450 SF"
_BB_LABEL_RE = re.compile(
    r"^([A-Z]{2,4}-\d+[A-Z]?)\s*[-–]?\s*([\d,]+(?:\.\d+)?)\s*SF\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Product spec extraction
# ---------------------------------------------------------------------------

# Known brand/product keywords (extend as needed)
_PRODUCT_BRANDS = re.compile(
    r"\b(ARMSTRONG|CERTAINTEED|USG|CHICAGO\s+METALLIC|ECOPHON|KNAUF|MINERAL\s+BASE|CORTEGA|DUNE|"
    r"FINE\s+FISSURED|SUPRAFINE|OPTIMA|BIOGUARD|CERAMAGUARD|TUNDRA|ORION)\b",
    re.IGNORECASE,
)


def _extract_product_spec(context: str, ceiling_type_end: int) -> str | None:
    """Grab product name tokens that follow the ceiling type tag on the same line."""
    # Take text after the ceiling type match position, up to 80 chars
    snippet = context[ceiling_type_end : ceiling_type_end + 80]
    # Grab up to 4 non-empty tokens, stop at another keyword or punctuation
    tokens = re.findall(r"[A-Za-z0-9&./'-]+", snippet)
    product_tokens: list[str] = []
    for tok in tokens:
        # Stop if we hit a grid pattern or height
        if re.fullmatch(r"\d{1,2}[xX]\d{1,2}", tok):
            break
        if re.fullmatch(r"\d{1,2}'", tok) or re.fullmatch(r"\d{1,3}\"", tok):
            break
        # Stop at structural keywords
        if tok.upper() in {"AFF", "GRID", "TILE", "CEILING", "ROOM", "FINISH"}:
            break
        product_tokens.append(tok)
        if len(product_tokens) >= 4:
            break
    if not product_tokens:
        return None
    # Filter: at least one token should look like a brand/product name (not just noise)
    candidate = " ".join(product_tokens)
    if _PRODUCT_BRANDS.search(candidate):
        return candidate
    # Heuristic: if it's 2+ capitalised words, treat as product
    if sum(1 for t in product_tokens if t[0].isupper()) >= 1 and len(product_tokens) >= 2:
        return candidate
    return None


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def _make_spec(
    ceiling_type: str,
    grid_pattern: str | None = None,
    height: str | None = None,
    product_spec: str | None = None,
    area_sf: Decimal | None = None,
    scope_tag: str | None = None,
    source_page: int = 0,
) -> dict[str, Any]:
    return {
        "ceiling_type": ceiling_type,
        "grid_pattern": grid_pattern,
        "height": height,
        "product_spec": product_spec,
        "area_sf": area_sf,
        "scope_tag": scope_tag,
        "source_page": source_page,
    }


def _parse_annotation_specs(annotations: list, source_page: int) -> list[dict[str, Any]]:
    """Extract ceiling specs implied by Bluebeam scope-tag annotations."""
    specs: list[dict[str, Any]] = []
    for ann in annotations:
        label = getattr(ann, "label", None) or (ann.get("label") if isinstance(ann, dict) else None)
        area_sf_raw = getattr(ann, "area_sf", None) or (
            ann.get("area_sf") if isinstance(ann, dict) else None
        )
        if not label:
            continue
        m = _BB_LABEL_RE.match(label.strip())
        if m:
            scope_tag = m.group(1).upper()
        elif _SCOPE_TAG_RE.match(label.strip()):
            scope_tag = _SCOPE_TAG_RE.match(label.strip()).group(1).upper()
        else:
            continue

        # Infer ceiling type from scope tag prefix
        prefix = re.match(r"^([A-Z]+)", scope_tag)
        prefix_str = prefix.group(1) if prefix else ""
        ceiling_type: str | None = None
        for pattern, label_type in _CEILING_RULES:
            if pattern.search(prefix_str):
                ceiling_type = label_type
                break
        if ceiling_type is None:
            # Map common prefixes directly
            _PREFIX_MAP = {
                "ACT": "ACT",
                "AWP": "ACT",  # acoustic wall panel – treat as ACT family? No — leave as-is
                "GWB": "GWB",
                "FW": "FW",
                "WW": "WW",
                "SM": "SM",
            }
            ceiling_type = _PREFIX_MAP.get(prefix_str, prefix_str)

        try:
            sf = (
                Decimal(m.group(2).replace(",", ""))
                if m
                else (Decimal(str(area_sf_raw)) if area_sf_raw is not None else None)
            )
        except InvalidOperation:
            sf = None

        specs.append(
            _make_spec(
                ceiling_type=ceiling_type,
                area_sf=sf,
                scope_tag=scope_tag,
                source_page=source_page,
            )
        )
    return specs


def extract_ceiling_specs(
    text: str,
    annotations: list | None = None,
    source_page: int = 0,
) -> list[dict[str, Any]]:
    """Extract ceiling specifications from plan text and optional Bluebeam annotations.

    Parameters
    ----------
    text:
        Full text content of one drawing page.
    annotations:
        Optional list of BluebeamAnnotation objects or dicts from the same page.
    source_page:
        Page number (0-based) to embed in each spec for traceability.

    Returns
    -------
    list of dicts with keys: ceiling_type, grid_pattern, height, product_spec,
    area_sf, scope_tag, source_page
    """
    specs: list[dict[str, Any]] = []
    seen_scope_tags: set[str] = set()

    lines = text.splitlines()

    for i, line in enumerate(lines):
        # Check each ceiling rule against this line
        for pattern, ceiling_label in _CEILING_RULES:
            m = pattern.search(line)
            if not m:
                continue

            # Forward context: this line + up to 4 lines ahead (for multi-line entries)
            fwd_end = min(len(lines), i + 5)
            fwd_context = "\n".join(lines[i:fwd_end])
            # Broad context (2 lines back) for grid and height when not found inline
            ctx_start = max(0, i - 2)
            broad_context = "\n".join(lines[ctx_start:fwd_end])
            inline_context = line  # for product spec (keep tightly scoped)

            # Grid pattern — prefer forward context, fall back to broad
            grid_match = _GRID_RE.search(fwd_context) or _GRID_RE.search(broad_context)
            grid_pattern = _normalise_grid(grid_match.group(1)) if grid_match else None

            # Height — prefer forward context, fall back to broad
            height = _normalise_height(fwd_context) or _normalise_height(broad_context)

            # Product spec (text right after the ceiling type hit)
            product_spec = _extract_product_spec(inline_context, m.end())

            # Scope tag — search forward context only to avoid picking up tags from earlier specs
            tag_match = _SCOPE_TAG_RE.search(fwd_context)
            scope_tag = tag_match.group(1).upper() if tag_match else None

            # Deduplicate by scope_tag when present
            dedup_key = scope_tag or f"{ceiling_label}:{i}"
            if dedup_key in seen_scope_tags:
                continue
            seen_scope_tags.add(dedup_key)

            specs.append(
                _make_spec(
                    ceiling_type=ceiling_label,
                    grid_pattern=grid_pattern,
                    height=height,
                    product_spec=product_spec,
                    scope_tag=scope_tag,
                    source_page=source_page,
                )
            )
            # Only match the first rule per line (most specific wins)
            break

    # ---- Bluebeam annotation specs ----
    if annotations:
        ann_specs = _parse_annotation_specs(annotations, source_page)
        # Only add annotation specs whose scope tag isn't already present
        existing_tags = {s["scope_tag"] for s in specs if s["scope_tag"]}
        for spec in ann_specs:
            if spec["scope_tag"] not in existing_tags:
                specs.append(spec)
                if spec["scope_tag"]:
                    existing_tags.add(spec["scope_tag"])

    return specs
