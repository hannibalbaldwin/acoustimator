"""Routes for estimate additional cost items (lift, travel, bond, etc.)."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas.estimates import (
    AdditionalItemResponse,
    CreateAdditionalItemRequest,
    UpdateAdditionalItemRequest,
)
from src.db.models import Estimate, EstimateAdditionalItem

logger = logging.getLogger(__name__)

router = APIRouter(tags=["estimates"])


@router.get("/{estimate_id}/additional-items", response_model=list[AdditionalItemResponse])
async def list_additional_items(estimate_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EstimateAdditionalItem)
        .where(EstimateAdditionalItem.estimate_id == estimate_id)
        .order_by(EstimateAdditionalItem.created_at)
    )
    return result.scalars().all()


@router.post("/{estimate_id}/additional-items", response_model=AdditionalItemResponse, status_code=201)
async def create_additional_item(
    estimate_id: UUID,
    body: CreateAdditionalItemRequest,
    db: AsyncSession = Depends(get_db),
):
    # Verify estimate exists
    est = await db.get(Estimate, estimate_id)
    if est is None:
        raise HTTPException(status_code=404, detail=f"Estimate {estimate_id} not found")

    item = EstimateAdditionalItem(
        estimate_id=estimate_id,
        item_type=body.item_type,
        description=body.description,
        amount=Decimal(str(body.amount)),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{estimate_id}/additional-items/{item_id}", response_model=AdditionalItemResponse)
async def update_additional_item(
    estimate_id: UUID,
    item_id: UUID,
    body: UpdateAdditionalItemRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EstimateAdditionalItem).where(
            EstimateAdditionalItem.id == item_id,
            EstimateAdditionalItem.estimate_id == estimate_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    if body.item_type is not None:
        item.item_type = body.item_type
    if body.description is not None:
        item.description = body.description
    if body.amount is not None:
        item.amount = Decimal(str(body.amount))

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{estimate_id}/additional-items/{item_id}", status_code=204)
async def delete_additional_item(
    estimate_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EstimateAdditionalItem).where(
            EstimateAdditionalItem.id == item_id,
            EstimateAdditionalItem.estimate_id == estimate_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
