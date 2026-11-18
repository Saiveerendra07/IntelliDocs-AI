import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    ChatMessageOut,
    AskQuestionRequest,
    AskQuestionResponse,
    SourceCitation,
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])

_CONVERSATIONS_STORE = {}
_MESSAGES_STORE = {}


@router.get("/conversations", response_model=List[ConversationOut])
async def list_conversations(current_user: dict = Depends(get_current_user)):
    user_convs = [
        c for c in _CONVERSATIONS_STORE.values()
        if str(c["user_id"]) == str(current_user["id"])
    ]
    user_convs.sort(key=lambda x: x["created_at"], reverse=True)
    return [ConversationOut(**c) for c in user_convs]


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(req: ConversationCreate, current_user: dict = Depends(get_current_user)):
    conv_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    conv_record = {
        "id": conv_id,
        "user_id": current_user["id"],
        "title": req.title,
        "document_ids": req.document_ids,
        "explanation_mode": req.explanation_mode,
        "created_at": now,
        "updated_at": now,
    }
    _CONVERSATIONS_STORE[conv_id] = conv_record
    _MESSAGES_STORE[conv_id] = []
    return ConversationOut(**conv_record)


@router.get("/conversations/{id}/messages", response_model=List[ChatMessageOut])
async def get_messages(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    conv = _CONVERSATIONS_STORE.get(id)
    if not conv or str(conv["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = _MESSAGES_STORE.get(id, [])
    return [ChatMessageOut(**m) for m in messages]


@router.post("/conversations/{id}/ask", response_model=AskQuestionResponse)
async def ask_question(
    id: uuid.UUID,
    req: AskQuestionRequest,
    current_user: dict = Depends(get_current_user),
):
    conv = _CONVERSATIONS_STORE.get(id)
    if not conv or str(conv["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found.")

    now = datetime.now(timezone.utc)

    # 1. Store user message
    user_msg_id = uuid.uuid4()
    user_msg = {
        "id": user_msg_id,
        "conversation_id": id,
        "role": "user",
        "content": req.query,
        "sources": [],
        "created_at": now,
    }
    _MESSAGES_STORE[id].append(user_msg)

    # 2. Gather retrieved passages from selected documents
    sources = []
    found_any = False
    for doc_id in req.document_ids:
        doc = _DOCS_STORE.get(doc_id)
        if not doc or str(doc["user_id"]) != str(current_user["id"]):
            continue
        pages = _PAGES_STORE.get(doc_id, [])
        for p in pages:
            found_any = True
            sources.append(SourceCitation(
                chunk_id=str(p["id"]),
                document_id=str(doc_id),
                filename=doc["original_filename"],
                page_start=p["page_number"],
                page_end=p["page_number"],
                score=0.91,
                snippet=p["text"][:200],
            ))

    if not found_any or not sources:
        answer_text = "I couldn't find this in the selected document(s)."
        sources = []
    else:
        # Formulate explanation based on mode
        prefix = {
            "beginner": "In simple, beginner-friendly terms: ",
            "technical": "According to the technical documentation: ",
            "exam": "Key Exam Points: ",
            "realworld": "To illustrate with a real-world scenario: ",
        }.get(req.explanation_mode, "")

        answer_text = f"{prefix}Based on {sources[0].filename} (Page {sources[0].page_start}), the document addresses '{req.query}'.\n\n- Key Grounding: {sources[0].snippet}"

    # 3. Store assistant message
    asst_msg_id = uuid.uuid4()
    asst_msg = {
        "id": asst_msg_id,
        "conversation_id": id,
        "role": "assistant",
        "content": answer_text,
        "sources": [s.model_dump() for s in sources],
        "created_at": datetime.now(timezone.utc),
    }
    _MESSAGES_STORE[id].append(asst_msg)

    return AskQuestionResponse(
        answer=answer_text,
        sources=sources,
        mode=req.explanation_mode,
    )


@router.delete("/conversations/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    conv = _CONVERSATIONS_STORE.get(id)
    if not conv or str(conv["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _CONVERSATIONS_STORE.pop(id, None)
    _MESSAGES_STORE.pop(id, None)
    return None
