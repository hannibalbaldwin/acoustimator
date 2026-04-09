"""Routes for product catalog management."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.estimation.catalog import add_catalog_entry, list_catalog_entries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CatalogEntryResponse(BaseModel):
    """Summary view of a single catalog entry."""

    name: str
    canonical_name: str
    category: str
    alias_count: int


class AddProductRequest(BaseModel):
    """Body for POST /api/products."""

    name: str
    canonical_name: str
    category: str
    aliases: list[str] = []


# ---------------------------------------------------------------------------
# GET /api/products
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CatalogEntryResponse])
async def list_products() -> list[dict[str, Any]]:
    """Return a summary list of all catalog entries."""
    return list_catalog_entries()


# ---------------------------------------------------------------------------
# POST /api/products
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=CatalogEntryResponse)
async def create_product(body: AddProductRequest) -> dict[str, Any]:
    """Append a new product entry to the catalog JSON and return it."""
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    if not body.canonical_name.strip():
        raise HTTPException(status_code=422, detail="canonical_name is required")
    if not body.category.strip():
        raise HTTPException(status_code=422, detail="category is required")

    try:
        add_catalog_entry(
            name=body.name.strip(),
            canonical_name=body.canonical_name.strip(),
            category=body.category.strip(),
            aliases=[a.strip() for a in body.aliases if a.strip()],
        )
    except Exception as exc:
        logger.exception("Failed to add catalog entry: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to persist catalog entry") from exc

    return {
        "name": body.name.strip(),
        "canonical_name": body.canonical_name.strip(),
        "category": body.category.strip(),
        "alias_count": len([a for a in body.aliases if a.strip()]),
    }
