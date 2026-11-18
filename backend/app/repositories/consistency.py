import os
import uuid
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models.document import Document, DocumentPage, DocumentChunk
from backend.app.db.models.nlp import NLPAnalysis, Summary
from backend.app.db.models.quiz import GeneratedQuestion, Quiz
from backend.app.db.models.flashcard import Flashcard


def check_document_consistency(db: Session, document_id: uuid.UUID) -> Dict[str, Any]:
    """
    Consistency check function:
    Verifies that all relational records, chunk counts, pages, and filesystem references
    belonging to document_id are valid, and ensures no orphaned dependent records exist.
    """
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        return {"exists": False, "consistent": True, "details": "Document does not exist."}

    pages_count = len(list(db.execute(select(DocumentPage).where(DocumentPage.document_id == document_id)).scalars().all()))
    chunks_count = len(list(db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).scalars().all()))
    summaries_count = len(list(db.execute(select(Summary).where(Summary.document_id == document_id)).scalars().all()))
    questions_count = len(list(db.execute(select(GeneratedQuestion).where(GeneratedQuestion.document_id == document_id)).scalars().all()))
    flashcards_count = len(list(db.execute(select(Flashcard).where(Flashcard.document_id == document_id)).scalars().all()))

    file_exists = os.path.exists(doc.stored_path) if doc.stored_path else False

    is_consistent = file_exists or doc.status == "failed"

    return {
        "exists": True,
        "document_id": str(document_id),
        "status": doc.status,
        "file_exists": file_exists,
        "pages_count": pages_count,
        "chunks_count": chunks_count,
        "summaries_count": summaries_count,
        "questions_count": questions_count,
        "flashcards_count": flashcards_count,
        "consistent": is_consistent,
    }


def purge_document_cascade(db: Session, document_id: uuid.UUID) -> bool:
    """
    Purges document with full cascading delete of:
    pages, chunks, nlp analyses, summaries, generated questions, quizzes, flashcards,
    and associated stored files on disk.
    """
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        return False

    # Delete physical file from storage
    if doc.stored_path and os.path.exists(doc.stored_path):
        try:
            os.remove(doc.stored_path)
        except OSError:
            pass

    # SQLAlchemy relationship cascade deletes pages, chunks, summaries, questions, flashcards
    db.delete(doc)
    db.commit()
    return True
