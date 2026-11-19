import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FlashcardGenerateRequest(BaseModel):
    document_id: uuid.UUID


class FlashcardReviewRequest(BaseModel):
    difficulty_mark: Optional[str] = "medium"  # easy | medium | difficult
    rating: Optional[int] = None  # 0 to 5 SM-2 rating


class FlashcardOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    topic: Optional[str] = None
    front: str
    back: str
    source_page: Optional[int] = None
    difficulty_mark: Optional[str] = None
    review_count: int = 0
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
