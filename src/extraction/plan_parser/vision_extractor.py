import base64
import json
import re

import fitz

from src.config import settings


async def extract_raster_page_vision(page: fitz.Page, page_num: int, page_type: str) -> dict:
    """Send a raster PDF page to Claude Vision for text/room extraction.

    Renders the page at 150 DPI and asks Claude to extract rooms, ceiling specs,
    and dimension notes from the image.

    Returns a dict with keys: rooms, ceiling_specs, notes
    """
    import anthropic

    # Render at 150 DPI (balance quality vs token cost)
    mat = fitz.Matrix(150 / 72, 150 / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    prompt = (
        f"This is page {page_num} of an architectural drawing ({page_type}).\n\n"
        "Extract the following if visible:\n"
        "1. Room names and numbers (list them)\n"
        "2. Square footage values or area labels\n"
        "3. Ceiling type annotations (ACT, GWB, Exposed, etc.)\n"
        '4. Ceiling height notations (e.g. "9\'-0\\"", "10\'-0\\"")\n'
        "5. Any product specifications or notes\n"
        "6. Dimension strings if readable\n\n"
        "Return as JSON with keys: rooms (list of {name, number, area_sf, ceiling_type, height}), "
        "ceiling_specs (list of {type, height, area_sf}), notes (any other relevant text)."
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = response.content[0].text
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"rooms": [], "ceiling_specs": [], "notes": text}
