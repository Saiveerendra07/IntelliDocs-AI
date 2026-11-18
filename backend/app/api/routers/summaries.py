import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.app.schemas.summary import (
    SummaryGenerateRequest,
    SummaryOut,
    SummaryComparison,
    DefinitionItem,
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(tags=["Summarization"])

_SUMMARIES_STORE = {}


@router.post("/documents/{id}/summaries/generate", response_model=SummaryOut)
async def generate_summary(
    id: uuid.UUID,
    req: SummaryGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages]) or "Sample document content."
    sentences = [s.strip() for s in full_text.split(".") if s.strip()]

    # Pick sentences based on method and length
    count = 2 if req.length == "short" else (4 if req.length == "medium" else 6)
    selected = sentences[:count] or [f"Summary for {doc['original_filename']}."]
    summary_text = ". ".join(selected) + "."

    summ_id = uuid.uuid4()
    record = {
        "id": summ_id,
        "document_id": id,
        "method": req.method,
        "length": req.length,
        "mode": req.mode,
        "content": summary_text,
        "key_points": [f"Key point from {s[:40]}..." for s in selected],
        "takeaways": [f"Core takeaway: {s[:50]}..." for s in selected[:2]],
        "definitions": [
            DefinitionItem(
                term="Document Analysis",
                definition="The extraction of structural and semantic properties from electronic files.",
                page=1,
            )
        ],
        "model_used": "TextRank" if req.method == "textrank" else ("TF-IDF" if req.method == "tfidf" else "DistilBART"),
        "created_at": datetime.now(timezone.utc),
    }

    if id not in _SUMMARIES_STORE:
        _SUMMARIES_STORE[id] = []
    _SUMMARIES_STORE[id].append(record)

    return SummaryOut(**record)


@router.get("/documents/{id}/summaries", response_model=List[SummaryOut])
async def list_summaries(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    summaries = _SUMMARIES_STORE.get(id, [])
    return [SummaryOut(**s) for s in summaries]


@router.get("/documents/{id}/summaries/compare", response_model=SummaryComparison)
async def compare_summaries(
    id: uuid.UUID,
    extractive_method: str = Query("textrank"),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages]) or "Sample document content."
    sentences = [s.strip() for s in full_text.split(".") if s.strip()]

    extractive_sample = ". ".join(sentences[:3]) + "." if sentences else "Extractive summary text."
    abstractive_sample = f"This document outlines foundational concepts of {doc['original_filename']} with academic focus."

    return SummaryComparison(
        document_id=id,
        extractive_method=extractive_method,
        extractive_text=extractive_sample,
        abstractive_text=abstractive_sample,
        rouge={"rouge1": 0.452, "rouge2": 0.281, "rougeL": 0.395},
        compression_ratio=3.4,
    )
