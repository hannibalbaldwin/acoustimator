"""Top-level plan reading orchestrator.

Usage:
    from src.extraction.plan_reader import read_plan
    result = read_plan(Path("path/to/drawing.pdf"), use_vision=False)
"""

import asyncio
from decimal import Decimal
from pathlib import Path

import fitz

from src.extraction.plan_parser.ceiling_extractor import extract_ceiling_specs
from src.extraction.plan_parser.models import (
    BluebeamAnnotation,
    CeilingSpec,
    PlanPage,
    PlanReadResult,
    Room,
)
from src.extraction.plan_parser.page_classifier import classify_page
from src.extraction.plan_parser.room_extractor import extract_rooms
from src.extraction.plan_parser.scope_suggester import suggest_scopes
from src.extraction.plan_parser.sf_estimator import estimate_total_sf
from src.extraction.plan_parser.text_extractor import extract_annotations

# Maximum raster pages to send to Vision API (cost control)
MAX_VISION_PAGES = 5


def _compute_confidence(
    pages: list[PlanPage],
    all_annotations: list[BluebeamAnnotation],
) -> float:
    """Compute an overall extraction confidence score.

    1.0  — Bluebeam polygon annotations found (most reliable)
    0.6  — Text-rich pages present but no area annotations
    0.3  — Mostly raster, no annotations
    """
    polygon_annotations = [a for a in all_annotations if a.annotation_type == "polygon"]
    if polygon_annotations:
        return 1.0

    vector_count = sum(1 for p in pages if p.is_vector_rich)
    if vector_count > 0:
        return 0.6

    return 0.3


async def _read_plan_async(
    pdf_path: Path,
    use_vision: bool = True,
) -> PlanReadResult:
    """Internal async implementation of read_plan."""
    from src.extraction.plan_parser.vision_extractor import extract_raster_page_vision

    source_file = str(pdf_path)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        return PlanReadResult(
            source_file=source_file,
            total_pages=0,
            vector_rich_pages=0,
            raster_pages=0,
            pages=[],
            rooms=[],
            ceiling_specs=[],
            scope_suggestions=[],
            total_area_sf=None,
            extraction_confidence=0.0,
            vision_pages_used=0,
            error=f"Failed to open PDF: {exc}",
            success=False,
        )

    total_pages = len(doc)
    pages: list[PlanPage] = []
    all_annotations: list[BluebeamAnnotation] = []
    all_rooms: list[Room] = []
    all_ceiling_specs: list[CeilingSpec] = []
    all_text_parts: list[str] = []
    vision_pages_used = 0
    raster_count = 0

    for i, fitz_page in enumerate(doc):
        page_num = i + 1  # 1-based

        # Classify and extract text
        page_info = classify_page(fitz_page, page_num, total_pages)
        annotations = extract_annotations(fitz_page, page_num)
        all_annotations.extend(annotations)

        plan_page = PlanPage(
            annotations=annotations,
            **page_info,
        )
        pages.append(plan_page)

        if plan_page.is_vector_rich:
            all_text_parts.append(plan_page.text)

            # Extract rooms and ceiling specs from vector text
            rooms = extract_rooms(plan_page.text, annotations)
            all_rooms.extend(rooms)

            ceiling_specs = extract_ceiling_specs(plan_page.text, annotations, page_num)
            all_ceiling_specs.extend(ceiling_specs)
        else:
            raster_count += 1
            # Optionally fall back to Vision API (capped at MAX_VISION_PAGES)
            if use_vision and vision_pages_used < MAX_VISION_PAGES:
                vision_data = await extract_raster_page_vision(
                    fitz_page, page_num, plan_page.page_type
                )
                vision_pages_used += 1

                # Convert vision rooms to Room models
                for r in vision_data.get("rooms", []):
                    try:
                        area = Decimal(str(r["area_sf"])) if r.get("area_sf") else None
                    except Exception:
                        area = None
                    all_rooms.append(
                        Room(
                            room_name=r.get("name", ""),
                            room_number=r.get("number"),
                            floor=None,
                            area_sf=area,
                            ceiling_height=r.get("height"),
                            ceiling_type=r.get("ceiling_type"),
                            scope_tag=None,
                        )
                    )

                # Convert vision ceiling specs to CeilingSpec models
                for cs in vision_data.get("ceiling_specs", []):
                    try:
                        area = Decimal(str(cs["area_sf"])) if cs.get("area_sf") else None
                    except Exception:
                        area = None
                    all_ceiling_specs.append(
                        CeilingSpec(
                            ceiling_type=cs.get("type", "unknown"),
                            grid_pattern=None,
                            height=cs.get("height"),
                            product_spec=None,
                            area_sf=area,
                            scope_tag=None,
                            source_page=page_num,
                        )
                    )

    doc.close()

    vector_rich_count = total_pages - raster_count
    all_text = "\n".join(all_text_parts)

    # Use the multi-strategy SF estimator (Bluebeam → explicit labels → dimensions)
    sf_estimate = estimate_total_sf(pages)
    total_area_sf = sf_estimate.get("total_sf")

    confidence = _compute_confidence(pages, all_annotations)

    scope_suggestions = suggest_scopes(all_rooms, all_ceiling_specs, all_annotations, all_text)

    return PlanReadResult(
        source_file=source_file,
        total_pages=total_pages,
        vector_rich_pages=vector_rich_count,
        raster_pages=raster_count,
        pages=pages,
        rooms=all_rooms,
        ceiling_specs=all_ceiling_specs,
        scope_suggestions=scope_suggestions,
        total_area_sf=total_area_sf,
        extraction_confidence=confidence,
        vision_pages_used=vision_pages_used,
        error=None,
        success=True,
    )


def read_plan(pdf_path: Path, use_vision: bool = True) -> PlanReadResult:
    """Read an architectural drawing PDF and extract structured data.

    Args:
        pdf_path: Path to the PDF file.
        use_vision: Whether to use Claude Vision API for raster pages.
                    Set False in tests to avoid API costs.

    Returns:
        PlanReadResult with extracted pages, rooms, ceiling specs, and scope suggestions.
    """
    return asyncio.run(_read_plan_async(pdf_path, use_vision=use_vision))
