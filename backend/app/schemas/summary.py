import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SummaryGenerateRequest(BaseModel):
    method: str = "textrank"  # frequency | tfidf | textrank | abstractive
    length: str = "medium"    # short | medium | detailed
    mode: str = "standard"    # standard | bullet | chapter | exam


class DefinitionItem(BaseModel):
    term: str
    definition: str
    page: Optional[int] = None


class SummaryOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    method: str
    length: str
    mode: str
    content: str
    key_points: List[str] = []
    takeaways: List[str] = []
    definitions: List[DefinitionItem] = []
    model_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SummaryComparison(BaseModel):
    document_id: uuid.UUID
    extractive_method: str
    extractive_text: str
    abstractive_text: str
    rouge: Dict[str, float]
    compression_ratio: float
