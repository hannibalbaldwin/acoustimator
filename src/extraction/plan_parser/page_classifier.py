import fitz

# Minimum extractable text length to consider a page vector-rich
VECTOR_RICH_THRESHOLD = 50


def classify_page_type(text: str, page_number: int, total_pages: int) -> str:
    """Determine the page type from its text content.

    Returns one of: "rcp", "floor_plan", "elevation", "schedule", "cover", "unknown"
    """
    upper = text.upper()

    if page_number == 1:
        return "cover"

    if "REFLECTED CEILING" in upper or "RCP" in upper:
        return "rcp"

    if "FLOOR PLAN" in upper or "LEVEL" in upper:
        return "floor_plan"

    if "ELEVATION" in upper:
        return "elevation"

    if "FINISH SCHEDULE" in upper or "ROOM SCHEDULE" in upper:
        return "schedule"

    return "unknown"


def has_dimension_strings(text: str) -> bool:
    """Check whether the text contains architectural dimension strings like 12'-6\"."""
    import re

    # Match patterns like: 12'-6", 9'-0", 10'
    return bool(re.search(r"\d+'-\d+\"|\d+'-\d+\s|\d+'\s*-\s*\d+\"", text))


def classify_page(page: fitz.Page, page_number: int, total_pages: int) -> dict:
    """Classify a single fitz.Page and return a dict suitable for PlanPage construction.

    Does NOT extract annotations — caller handles that separately.
    Returns a dict with keys matching PlanPage fields (minus annotations).
    """
    text = page.get_text("text")
    stripped = text.strip()
    is_vector_rich = len(stripped) > VECTOR_RICH_THRESHOLD

    if not is_vector_rich:
        # Still run classification on whatever text we have
        text_for_type = stripped
    else:
        text_for_type = stripped

    page_type = classify_page_type(text_for_type, page_number, total_pages)
    word_count = len(stripped.split()) if stripped else 0
    dimensions = has_dimension_strings(stripped)

    return {
        "page_number": page_number,
        "page_type": page_type,
        "is_vector_rich": is_vector_rich,
        "text": text if is_vector_rich else "",
        "word_count": word_count,
        "has_dimensions": dimensions,
    }
