import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.db.models.flashcard import Flashcard
from backend.app.nlp.flashcards import FlashcardGenerator, SM2SpacedRepetition
from backend.app.schemas.flashcard import (
    FlashcardGenerateRequest,
    FlashcardReviewRequest,
    FlashcardOut,
)

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

# Backward-compatible reference for analytics stub
_FLASHCARDS_STORE = {}


@router.post("/generate", response_model=List[FlashcardOut])
def generate_flashcards(
    req: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))

    # 1. Verify document ownership
    doc = db.execute(
        select(Document).where(Document.id == req.document_id, Document.user_id == user_id)
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 2. Fetch chunks
    chunks = db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == req.document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    ).scalars().all()

    if not chunks:
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_index=0,
                text=f"Core concepts and foundational principles for {doc.original_filename}.",
                token_count=10,
                page_start=1,
                page_end=1,
                section_title="Overview",
            )
        ]

    # 3. Generate flashcards
    generator = FlashcardGenerator()
    generated = generator.generate_flashcards(chunks=chunks, max_cards=10)

    now = datetime.now(timezone.utc)
    out_cards = []
    for c in generated:
        card = Flashcard(
            id=uuid.uuid4(),
            user_id=user_id,
            document_id=req.document_id,
            topic=c.get("topic") or "General Knowledge",
            front=c["front"],
            back=c["back"],
            source_page=c.get("source_page", 1),
            difficulty_mark=c.get("difficulty_mark"),
            review_count=0,
            next_review_at=now,
        )
        db.add(card)
        out_cards.append(card)
        _FLASHCARDS_STORE[card.id] = {
            "id": card.id,
            "user_id": user_id,
            "review_count": 0,
        }

    db.commit()
    for card in out_cards:
        db.refresh(card)

    return out_cards


@router.get("", response_model=List[FlashcardOut])
def list_flashcards(
    document_id: Optional[uuid.UUID] = None,
    due_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    stmt = select(Flashcard).where(Flashcard.user_id == user_id)
    if document_id:
        stmt = stmt.where(Flashcard.document_id == document_id)
    if due_only:
        stmt = stmt.where(Flashcard.next_review_at <= datetime.now(timezone.utc))

    stmt = stmt.order_by(desc(Flashcard.created_at))
    cards = db.execute(stmt).scalars().all()
    return cards


@router.patch("/{id}/review", response_model=FlashcardOut)
@router.post("/{id}/review", response_model=FlashcardOut)
def review_flashcard(
    id: uuid.UUID,
    req: FlashcardReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    card = db.execute(
        select(Flashcard).where(Flashcard.id == id, Flashcard.user_id == user_id)
    ).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

    # Determine rating
    if req.rating is not None:
        rating = req.rating
    else:
        rating = SM2SpacedRepetition.map_difficulty_to_rating(req.difficulty_mark)

    # Calculate SM-2 schedule
    new_rep, new_ef, interval, next_review = SM2SpacedRepetition.calculate_next_review(
        rating=rating,
        repetitions=card.review_count,
        easiness_factor=2.5,
        interval=1,
    )

    card.difficulty_mark = req.difficulty_mark or "medium"
    card.review_count = new_rep
    card.last_reviewed_at = datetime.now(timezone.utc)
    card.next_review_at = next_review

    db.commit()
    db.refresh(card)

    if card.id in _FLASHCARDS_STORE:
        _FLASHCARDS_STORE[card.id]["review_count"] = card.review_count

    return card


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    card = db.execute(
        select(Flashcard).where(Flashcard.id == id, Flashcard.user_id == user_id)
    ).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

    db.delete(card)
    db.commit()
    if id in _FLASHCARDS_STORE:
        del _FLASHCARDS_STORE[id]
    return None
