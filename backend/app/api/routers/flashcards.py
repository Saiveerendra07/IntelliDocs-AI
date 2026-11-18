import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.app.schemas.flashcard import (
    FlashcardGenerateRequest,
    FlashcardReviewRequest,
    FlashcardOut,
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

_FLASHCARDS_STORE = {}


@router.post("/generate", response_model=List[FlashcardOut])
async def generate_flashcards(req: FlashcardGenerateRequest, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(req.document_id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    new_cards = []
    card_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    card_record = {
        "id": card_id,
        "user_id": current_user["id"],
        "document_id": req.document_id,
        "topic": "Document Intelligence",
        "front": f"What is the primary role of {doc['original_filename']}?",
        "back": "To establish academic understanding and structural decomposition of technical materials.",
        "source_page": 1,
        "difficulty_mark": None,
        "review_count": 0,
        "last_reviewed_at": None,
        "next_review_at": now + timedelta(days=1),
        "created_at": now,
    }
    _FLASHCARDS_STORE[card_id] = card_record
    new_cards.append(card_record)

    return [FlashcardOut(**c) for c in new_cards]


@router.get("", response_model=List[FlashcardOut])
async def list_flashcards(
    document_id: Optional[uuid.UUID] = None,
    current_user: dict = Depends(get_current_user),
):
    cards = [
        c for c in _FLASHCARDS_STORE.values()
        if str(c["user_id"]) == str(current_user["id"])
    ]
    if document_id:
        cards = [c for c in cards if str(c["document_id"]) == str(document_id)]
    return [FlashcardOut(**c) for c in cards]


@router.patch("/{id}/review", response_model=FlashcardOut)
async def review_flashcard(
    id: uuid.UUID,
    req: FlashcardReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    card = _FLASHCARDS_STORE.get(id)
    if not card or str(card["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Flashcard not found.")

    now = datetime.now(timezone.utc)
    card["difficulty_mark"] = req.difficulty_mark
    card["review_count"] += 1
    card["last_reviewed_at"] = now

    interval_days = 1 if req.difficulty_mark == "difficult" else (3 if req.difficulty_mark == "medium" else 7)
    card["next_review_at"] = now + timedelta(days=interval_days)

    return FlashcardOut(**card)
