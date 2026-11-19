import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.schemas.chat import SourceCitation
from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.nlp.retrieval import HybridRetriever

router = APIRouter(prefix="/search", tags=["Semantic Search"])


class SearchRequest(BaseModel):
    query: str
    document_ids: Optional[List[uuid.UUID]] = None
    top_k: int = 5


class SearchResponse(BaseModel):
    query: str
    results: List[SourceCitation]


@router.post("", response_model=SearchResponse)
async def semantic_search(
    req: SearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    retriever = HybridRetriever(db)

    hits = retriever.search_hybrid(
        user_id=user_id,
        query=req.query,
        top_k=req.top_k,
        document_ids=req.document_ids,
    )

    citations = []
    for h in hits:
        citations.append(SourceCitation(
            chunk_id=str(h["chunk_id"]),
            document_id=str(h["document_id"]),
            filename=h.get("document_title", "Document"),
            page_start=h["page_start"],
            page_end=h["page_end"],
            score=min(1.0, round(float(h["score"]) / 10.0, 3)),
            snippet=h["text"][:300],
        ))

    return SearchResponse(query=req.query, results=citations)
