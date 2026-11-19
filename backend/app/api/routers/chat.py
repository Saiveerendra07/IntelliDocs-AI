import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.chat import Conversation, ChatMessage
from backend.app.db.models.document import Document
from backend.app.nlp.rag import RAGEngine
from backend.app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    ChatMessageOut,
    AskQuestionRequest,
    AskQuestionResponse,
    SourceCitation,
)

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.created_at))
    )
    convs = db.execute(stmt).scalars().all()
    return convs


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))

    # Verify that requested documents belong to current user
    for doc_id in req.document_ids:
        doc = db.execute(
            select(Document).where(Document.id == doc_id, Document.user_id == user_id)
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {doc_id} not found."
            )

    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title=req.title,
        document_ids=[str(d) for d in req.document_ids],
        explanation_mode=req.explanation_mode,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations/{id}", response_model=ConversationOut)
def get_conversation(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    conv = db.execute(
        select(Conversation).where(Conversation.id == id, Conversation.user_id == user_id)
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conv


@router.delete("/conversations/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    conv = db.execute(
        select(Conversation).where(Conversation.id == id, Conversation.user_id == user_id)
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    db.delete(conv)
    db.commit()
    return None


@router.get("/conversations/{id}/messages", response_model=List[ChatMessageOut])
def get_messages(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    conv = db.execute(
        select(Conversation).where(Conversation.id == id, Conversation.user_id == user_id)
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = db.execute(stmt).scalars().all()
    return messages


@router.post("/conversations/{id}/ask", response_model=AskQuestionResponse)
def ask_question(
    id: uuid.UUID,
    req: AskQuestionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    conv = db.execute(
        select(Conversation).where(Conversation.id == id, Conversation.user_id == user_id)
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    # 1. Save user question message
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=id,
        role="user",
        content=req.query,
        sources=[],
    )
    db.add(user_msg)

    # 2. Run Grounded RAG Engine
    rag_engine = RAGEngine(db)
    doc_uuids = req.document_ids if req.document_ids else [uuid.UUID(str(d)) for d in conv.document_ids]
    rag_result = rag_engine.generate_answer(
        user_id=user_id,
        query=req.query,
        document_ids=doc_uuids,
        explanation_mode=req.explanation_mode or conv.explanation_mode,
    )

    # 3. Format citations for schema
    citations = [
        SourceCitation(
            chunk_id=s["chunk_id"],
            document_id=str(s["document_id"]),
            filename=s["document_title"],
            page_start=s["page_start"],
            page_end=s["page_end"],
            score=s["score"],
            snippet=s["snippet"],
        )
        for s in rag_result["sources"]
    ]

    # 4. Save assistant answer message
    sources_raw = [
        {
            "chunk_id": s.chunk_id,
            "document_id": s.document_id,
            "filename": s.filename,
            "page_start": s.page_start,
            "page_end": s.page_end,
            "score": s.score,
            "snippet": s.snippet,
        }
        for s in citations
    ]
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=id,
        role="assistant",
        content=rag_result["answer"],
        sources=sources_raw,
    )
    db.add(assistant_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    return AskQuestionResponse(
        answer=rag_result["answer"],
        sources=citations,
        mode=rag_result["explanation_mode"],
        confidence_score=rag_result["confidence_score"],
    )


@router.post("/query", response_model=AskQuestionResponse)
def direct_query(
    req: AskQuestionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Direct query endpoint for one-off document Q&A without creating a persistent conversation thread."""
    user_id = uuid.UUID(str(current_user["id"]))
    rag_engine = RAGEngine(db)
    rag_result = rag_engine.generate_answer(
        user_id=user_id,
        query=req.query,
        document_ids=req.document_ids,
        explanation_mode=req.explanation_mode,
    )

    citations = [
        SourceCitation(
            chunk_id=s["chunk_id"],
            document_id=str(s["document_id"]),
            filename=s["document_title"],
            page_start=s["page_start"],
            page_end=s["page_end"],
            score=s["score"],
            snippet=s["snippet"],
        )
        for s in rag_result["sources"]
    ]

    return AskQuestionResponse(
        answer=rag_result["answer"],
        sources=citations,
        mode=rag_result["explanation_mode"],
        confidence_score=rag_result["confidence_score"],
    )
