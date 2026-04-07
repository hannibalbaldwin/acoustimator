from decimal import Decimal

from pydantic import BaseModel


class BluebeamAnnotation(BaseModel):
    annotation_type: str  # "polygon", "measurement", "text", "stamp"
    label: str | None  # visible label text
    area_sf: Decimal | None  # pre-calculated area if polygon with area
    length_lf: Decimal | None  # linear footage if measurement
    color: str | None  # RGB hex, e.g. "#FF0000"
    page_number: int


class PlanPage(BaseModel):
    page_number: int
    page_type: str  # "rcp", "floor_plan", "elevation", "schedule", "cover", "unknown"
    is_vector_rich: bool  # True if text extractable; False = raster, needs vision
    text: str  # full extracted text (empty string for raster pages)
    annotations: list[BluebeamAnnotation]
    word_count: int
    has_dimensions: bool  # contains dimension strings like "12'-6\""


class Room(BaseModel):
    room_name: str
    room_number: str | None
    floor: str | None
    area_sf: Decimal | None
    ceiling_height: str | None  # "9'-0\"", "10'-0\"", etc.
    ceiling_type: str | None  # "ACT", "GWB", "Exposed", "FW"
    scope_tag: str | None  # "ACT-1", "AWP-2", etc.


class CeilingSpec(BaseModel):
    ceiling_type: str  # "ACT", "GWB", "Exposed Structure", "FW", "Baffles", "WW"
    grid_pattern: str | None  # "2x2", "2x4", "1x4"
    height: str | None
    product_spec: str | None  # any product name mentioned near this ceiling type
    area_sf: Decimal | None
    scope_tag: str | None
    source_page: int


class ScopeSuggestion(BaseModel):
    scope_type: str  # "ACT", "AWP", "FW", "SM", "WW", "Baffles", "RPG"
    scope_tag: str  # "ACT-1", "AWP-2", etc.
    area_sf: Decimal | None
    length_lf: Decimal | None
    product_hint: str | None  # any product name found near this scope
    confidence: float  # 0.0–1.0
    source: str  # "bluebeam_annotation", "text_extraction", "vision"
    rooms: list[str]  # room names this scope applies to


class PlanReadResult(BaseModel):
    source_file: str
    total_pages: int
    vector_rich_pages: int
    raster_pages: int
    pages: list[PlanPage]
    rooms: list[Room]
    ceiling_specs: list[CeilingSpec]
    scope_suggestions: list[ScopeSuggestion]
    total_area_sf: Decimal | None  # sum of all polygon annotations
    extraction_confidence: float
    vision_pages_used: int  # how many pages fell back to Vision API
    error: str | None
    success: bool
