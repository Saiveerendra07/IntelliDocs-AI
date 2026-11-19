import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.schemas.summary import (
    SummaryGenerateRequest,
    SummaryOut,
    SummaryComparison,
    DefinitionItem,
)
from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.document import Document, DocumentPage
from backend.app.db.models.nlp import Summary
from backend.app.nlp.extractive import (
    FrequencySummarizer,
    TFIDFSummarizer,
    TextRankSummarizer,
    extract_definitions,
    extract_key_points,
)
from backend.app.nlp.abstractive import AbstractiveSummarizer
from backend.app.nlp.evaluation import compute_rouge_scores, compare_extractive_abstractive
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(tags=["Summarization"])

# In-memory store fallback for cross-router compatibility
_SUMMARIES_STORE = {}

freq_summarizer = FrequencySummarizer()
tfidf_summarizer = TFIDFSummarizer()
textrank_summarizer = TextRankSummarizer()
abstractive_summarizer = AbstractiveSummarizer()


def _get_document_text(db: Session, doc_id: uuid.UUID, user_id: uuid.UUID) -> Tuple[Any, str]:
    doc = db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if doc:
        pages = db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc_id)
            .order_by(DocumentPage.page_number)
        ).scalars().all()
        full_text = "\n\n".join([p.text for p in pages if p.text])
        return doc, full_text

    doc_mem = _DOCS_STORE.get(doc_id)
    if not doc_mem or str(doc_mem["user_id"]) != str(user_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages_mem = _PAGES_STORE.get(doc_id, [])
    full_text = "\n\n".join([p["text"] for p in pages_mem if p.get("text")])
    return doc_mem, full_text


@router.post("/documents/{id}/summaries/generate", response_model=SummaryOut)
async def generate_summary(
    id: uuid.UUID,
    req: SummaryGenerateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc, full_text = _get_document_text(db, id, user_id)

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty.")

    num_sentences = 3 if req.length == "short" else (8 if req.length == "detailed" else 5)
    method = req.method.lower()

    if method == "abstractive":
        content, key_points, defs_dict, model_name = abstractive_summarizer.summarize(
            text=full_text,
            length=req.length,
            mode=req.mode,
        )
        definitions = [DefinitionItem(term=d["term"], definition=d["definition"]) for d in defs_dict]
    else:
        # Extractive methods
        if method == "frequency":
            content, selected = freq_summarizer.summarize(full_text, num_sentences=num_sentences)
            model_name = "Normalized Word Frequency"
        elif method == "tfidf":
            content, selected = tfidf_summarizer.summarize(full_text, num_sentences=num_sentences)
            model_name = "TF-IDF Sentence Scoring"
        else:
            # Default: TextRank
            content, selected = textrank_summarizer.summarize(full_text, num_sentences=num_sentences)
            model_name = "TextRank Graph Algorithm (Scratch)"

        key_points = extract_key_points(selected)
        defs_dict = extract_definitions(full_text)
        definitions = [DefinitionItem(term=d["term"], definition=d["definition"]) for d in defs_dict]

        if req.mode == "bullet":
            content = "\n".join([f"• {s}" for s in selected if s.strip()])
        elif req.mode == "exam":
            exam_header = "### Exam Key Points:\n" + "\n".join([f"• {p}" for p in key_points])
            def_sec = ""
            if definitions:
                def_sec = "\n\n### Definitions:\n" + "\n".join([f"- **{d.term}**: {d.definition}" for d in definitions])
            content = f"{content}\n\n{exam_header}{def_sec}"

    summ_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Persist in Database
    summary_record = Summary(
        id=summ_id,
        document_id=id,
        method=req.method,
        length=req.length,
        mode=req.mode,
        content=content,
        key_points=key_points,
        definitions=[d.model_dump() for d in definitions],
        model_used=model_name,
        created_at=now,
    )
    db.add(summary_record)
    db.commit()
    db.refresh(summary_record)

    # Cache for fallback
    if id not in _SUMMARIES_STORE:
        _SUMMARIES_STORE[id] = []
    _SUMMARIES_STORE[id].append({
        "id": summ_id,
        "document_id": id,
        "method": req.method,
        "length": req.length,
        "mode": req.mode,
        "content": content,
        "key_points": key_points,
        "takeaways": key_points[:3],
        "definitions": definitions,
        "model_used": model_name,
        "created_at": now,
    })

    return SummaryOut(
        id=summ_id,
        document_id=id,
        method=req.method,
        length=req.length,
        mode=req.mode,
        content=content,
        key_points=key_points,
        takeaways=key_points[:3],
        definitions=definitions,
        model_used=model_name,
        created_at=now,
    )


@router.get("/documents/{id}/summaries", response_model=List[SummaryOut])
async def list_summaries(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _get_document_text(db, id, user_id)

    db_summaries = db.execute(
        select(Summary)
        .where(Summary.document_id == id)
        .order_by(desc(Summary.created_at))
    ).scalars().all()

    if db_summaries:
        results = []
        for s in db_summaries:
            defs = [DefinitionItem(**d) if isinstance(d, dict) else d for d in (s.definitions or [])]
            results.append(SummaryOut(
                id=s.id,
                document_id=s.document_id,
                method=s.method,
                length=s.length,
                mode=s.mode,
                content=s.content,
                key_points=s.key_points or [],
                takeaways=(s.key_points or [])[:3],
                definitions=defs,
                model_used=s.model_used,
                created_at=s.created_at,
            ))
        return results

    summaries = _SUMMARIES_STORE.get(id, [])
    return [SummaryOut(**s) for s in summaries]


@router.get("/documents/{id}/summaries/compare", response_model=SummaryComparison)
async def compare_summaries(
    id: uuid.UUID,
    extractive_method: str = Query("textrank"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty.")

    # Generate or extract extractive text
    if extractive_method.lower() == "frequency":
        extractive_text, _ = freq_summarizer.summarize(full_text, num_sentences=4)
    elif extractive_method.lower() == "tfidf":
        extractive_text, _ = tfidf_summarizer.summarize(full_text, num_sentences=4)
    else:
        extractive_text, _ = textrank_summarizer.summarize(full_text, num_sentences=4)

    # Generate abstractive text
    abstractive_text, _, _, _ = abstractive_summarizer.summarize(full_text, length="medium")

    # Compute genuine ROUGE scores comparing extractive and abstractive against source
    comp = compare_extractive_abstractive(full_text, extractive_text, abstractive_text)

    # Flat ROUGE dictionary for schema backward compatibility
    rouge_f1 = {
        "rouge1": comp["abstractive"]["rouge"]["rouge1"]["fmeasure"],
        "rouge2": comp["abstractive"]["rouge"]["rouge2"]["fmeasure"],
        "rougeL": comp["abstractive"]["rouge"]["rougeL"]["fmeasure"],
    }

    return SummaryComparison(
        document_id=id,
        extractive_method=extractive_method,
        extractive_text=extractive_text,
        abstractive_text=abstractive_text,
        rouge=rouge_f1,
        compression_ratio=comp["abstractive"]["compression_ratio"],
    )


@router.get("/summaries/{id}", response_model=SummaryOut)
async def get_summary_by_id(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    summary = db.execute(select(Summary).where(Summary.id == id)).scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found.")

    # Check that document belongs to current user
    doc = db.execute(
        select(Document).where(Document.id == summary.document_id, Document.user_id == user_id)
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Summary not found.")

    defs = [DefinitionItem(**d) if isinstance(d, dict) else d for d in (summary.definitions or [])]
    return SummaryOut(
        id=summary.id,
        document_id=summary.document_id,
        method=summary.method,
        length=summary.length,
        mode=summary.mode,
        content=summary.content,
        key_points=summary.key_points or [],
        takeaways=(summary.key_points or [])[:3],
        definitions=defs,
        model_used=summary.model_used,
        created_at=summary.created_at,
    )
