import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    document_ids: List[uuid.UUID]
    explanation_mode: str = "technical"


class ConversationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    document_ids: List[uuid.UUID]
    explanation_mode: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SourceCitation(BaseModel):
    chunk_id: str
    document_id: str
    filename: Optional[str] = None
    page_start: int
    page_end: int
    score: float
    snippet: str


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: Optional[List[SourceCitation]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class AskQuestionRequest(BaseModel):
    query: str
    document_ids: List[uuid.UUID]
    explanation_mode: str = "technical"


class AskQuestionResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    mode: str
    confidence_score: Optional[float] = 0.85
