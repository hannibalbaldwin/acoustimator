"""Routes for estimate threaded notes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.models import Estimate, EstimateNote

router = APIRouter(tags=["estimate-notes"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EstimateNoteResponse(BaseModel):
    id: UUID
    estimate_id: UUID
    content: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CreateNoteBody(BaseModel):
    content: str
    author_name: str = "Unknown"


class UpdateNoteBody(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_estimate_or_404(estimate_id: UUID, db: AsyncSession) -> Estimate:
    result = await db.execute(select(Estimate).where(Estimate.id == estimate_id))
    estimate = result.scalar_one_or_none()
    if estimate is None:
        raise HTTPException(status_code=404, detail=f"Estimate {estimate_id} not found")
    return estimate


async def _get_note_or_404(note_id: UUID, estimate_id: UUID, db: AsyncSession) -> EstimateNote:
    result = await db.execute(
        select(EstimateNote).where(
            EstimateNote.id == note_id,
            EstimateNote.estimate_id == estimate_id,
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    return note


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{estimate_id}/notes", response_model=list[EstimateNoteResponse])
async def list_notes(estimate_id: UUID, db: AsyncSession = Depends(get_db)) -> list[EstimateNote]:
    """List all notes for an estimate, ordered by created_at asc."""
    await _get_estimate_or_404(estimate_id, db)
    result = await db.execute(
        select(EstimateNote)
        .where(EstimateNote.estimate_id == estimate_id)
        .order_by(EstimateNote.created_at.asc())
    )
    return list(result.scalars().all())


@router.post("/{estimate_id}/notes", response_model=EstimateNoteResponse, status_code=201)
async def create_note(
    estimate_id: UUID,
    body: CreateNoteBody,
    db: AsyncSession = Depends(get_db),
) -> EstimateNote:
    """Create a new note on an estimate."""
    await _get_estimate_or_404(estimate_id, db)
    note = EstimateNote(
        estimate_id=estimate_id,
        content=body.content,
        author_name=body.author_name,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.patch("/{estimate_id}/notes/{note_id}", response_model=EstimateNoteResponse)
async def update_note(
    estimate_id: UUID,
    note_id: UUID,
    body: UpdateNoteBody,
    db: AsyncSession = Depends(get_db),
) -> EstimateNote:
    """Update the content of a note."""
    note = await _get_note_or_404(note_id, estimate_id, db)
    note.content = body.content
    note.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{estimate_id}/notes/{note_id}", status_code=204)
async def delete_note(
    estimate_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a note."""
    note = await _get_note_or_404(note_id, estimate_id, db)
    await db.delete(note)
    await db.commit()
