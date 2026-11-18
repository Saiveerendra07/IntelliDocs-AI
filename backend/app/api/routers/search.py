import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.app.schemas.chat import SourceCitation
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(prefix="/search", tags=["Semantic Search"])


class SearchRequest(BaseModel):
    query: str
    document_ids: List[uuid.UUID]
    top_k: int = 5


class SearchResponse(BaseModel):
    query: str
    results: List[SourceCitation]


@router.post("", response_model=SearchResponse)
async def semantic_search(req: SearchRequest, current_user: dict = Depends(get_current_user)):
    results = []
    for doc_id in req.document_ids:
        doc = _DOCS_STORE.get(doc_id)
        if not doc or str(doc["user_id"]) != str(current_user["id"]):
            continue
        pages = _PAGES_STORE.get(doc_id, [])
        for p in pages:
            results.append(SourceCitation(
                chunk_id=str(p["id"]),
                document_id=str(doc_id),
                filename=doc["original_filename"],
                page_start=p["page_number"],
                page_end=p["page_number"],
                score=0.88,
                snippet=p["text"][:250],
            ))

    return SearchResponse(query=req.query, results=results[:req.top_k])
