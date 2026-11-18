import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: str
    file_size: int
    page_count: int = 1
    language: str = "en"
    is_scanned: bool = False


class DocumentOut(DocumentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    error_message: Optional[str] = None
    processing_progress: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentStatus(BaseModel):
    id: uuid.UUID
    status: str
    processing_progress: float
    error_message: Optional[str] = None


class DocumentPageOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    text: str
    ocr_applied: bool = False
    tables_json: Optional[Any] = None

    class Config:
        from_attributes = True


class DocumentChunkOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    token_count: int
    section_title: Optional[str] = None
    chroma_id: Optional[str] = None

    class Config:
        from_attributes = True
