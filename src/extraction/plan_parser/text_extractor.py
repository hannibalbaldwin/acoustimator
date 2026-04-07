import re
from decimal import Decimal

import fitz

from src.extraction.plan_parser.models import BluebeamAnnotation


def extract_page_text(page: fitz.Page) -> str:
    """Extract all text from a page in reading order."""
    return page.get_text("text")


def extract_annotations(page: fitz.Page, page_num: int) -> list[BluebeamAnnotation]:
    """Extract Bluebeam polygon annotations with area values.

    Bluebeam stores area measurements in annotation popup text like:
    'Area: 609.87 sq ft' or 'Area: 609.87 SF'
    Length measurements like 'Length: 45.5 LF' or 'Length: 45.5 ft'
    """
    annotations = []
    for annot in page.annots():
        content = annot.info.get("content", "") or ""
        subject = annot.info.get("subject", "") or ""
        title = annot.info.get("title", "") or ""

        area_sf = None
        length_lf = None

        # Parse "Area: X sq ft" or "Area: X SF"
        area_match = re.search(
            r"Area[:\s]+([0-9,]+\.?\d*)\s*(?:sq\s*ft|SF|ft²)",
            content,
            re.IGNORECASE,
        )
        if area_match:
            area_sf = Decimal(area_match.group(1).replace(",", ""))

        # Parse "Length: X LF" or "Length: X ft"
        len_match = re.search(
            r"Length[:\s]+([0-9,]+\.?\d*)\s*(?:LF|ft|')",
            content,
            re.IGNORECASE,
        )
        if len_match:
            length_lf = Decimal(len_match.group(1).replace(",", ""))

        # Get annotation color
        color = None
        try:
            colors = annot.colors
            if colors and colors.get("stroke"):
                r, g, b = [int(c * 255) for c in colors["stroke"]]
                color = f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            pass

        label = content or subject or title or ""
        annot_type = "polygon" if area_sf else "measurement" if length_lf else "text"

        annotations.append(
            BluebeamAnnotation(
                annotation_type=annot_type,
                label=label[:200],
                area_sf=area_sf,
                length_lf=length_lf,
                color=color,
                page_number=page_num,
            )
        )
    return annotations
