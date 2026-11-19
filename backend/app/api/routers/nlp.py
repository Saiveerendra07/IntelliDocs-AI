import uuid
from typing import Optional, List, Tuple, Any
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.schemas.nlp import (
    PreprocessRequest,
    PreprocessResponse,
    POSResponse,
    POSToken,
    NERResponse,
    EntityItem,
    NgramsResponse,
    NgramItem,
    FrequencyResponse,
    FrequencyItem,
    KeywordsResponse,
    KeywordItem,
    TopicsResponse,
    LDATopic,
    ChunkCluster,
    SearchTermResponse,
    SearchTermPassage,
    ReadabilityResponse,
)
from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.document import Document, DocumentPage, DocumentChunk
from backend.app.db.models.nlp import NLPAnalysis
from backend.app.nlp.preprocessing import NLPPreprocessor
from backend.app.nlp.keywords import HybridKeywordExtractor
from backend.app.nlp.topics import LDATopicModeler, KMeansChunkClusterer
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(tags=["NLP Analysis"])
preprocessor = NLPPreprocessor()
keyword_extractor = HybridKeywordExtractor()
lda_modeler = LDATopicModeler(n_topics=3, n_words=5)
chunk_clusterer = KMeansChunkClusterer(n_clusters=3)


def _get_document_text(db: Session, doc_id: uuid.UUID, user_id: uuid.UUID) -> Tuple[Any, str]:
    # Check DB first
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

    # Fallback to in-memory store
    doc_mem = _DOCS_STORE.get(doc_id)
    if not doc_mem or str(doc_mem["user_id"]) != str(user_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages_mem = _PAGES_STORE.get(doc_id, [])
    full_text = "\n\n".join([p["text"] for p in pages_mem if p.get("text")])
    return doc_mem, full_text


@router.post("/nlp/preprocess", response_model=PreprocessResponse)
async def adhoc_preprocess(req: PreprocessRequest):
    res = preprocessor.process_full(req.text)
    return PreprocessResponse(
        sample_original=res["sample_original"],
        sample_cleaned=res["sample_cleaned"],
        stats=res["stats"],
        tokens=res["tokens"][:50],
        filtered_tokens=res["filtered_tokens"][:50],
        porter_stems=res["porter_stems"][:50],
        snowball_stems=res["snowball_stems"][:50],
        lemmatized_sample=res["lemmatized_sample"][:50],
    )


@router.get("/documents/{id}/nlp/preprocessing", response_model=PreprocessResponse)
async def get_doc_preprocessing(
    id: uuid.UUID,
    sample_size: int = Query(300, ge=50, le=2000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:50000])
    return PreprocessResponse(
        sample_original=res["sample_original"],
        sample_cleaned=res["sample_cleaned"],
        stats=res["stats"],
        tokens=res["tokens"][:50],
        filtered_tokens=res["filtered_tokens"][:50],
        porter_stems=res["porter_stems"][:50],
        snowball_stems=res["snowball_stems"][:50],
        lemmatized_sample=res["lemmatized_sample"][:50],
    )


@router.get("/documents/{id}/nlp/pos", response_model=POSResponse)
async def get_doc_pos(
    id: uuid.UUID,
    sample_size: int = Query(100, ge=20, le=500),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:20000])
    pos_items = [POSToken(**item) for item in res["pos_tokens"][:sample_size]]
    return POSResponse(tokens=pos_items)


@router.get("/documents/{id}/nlp/entities", response_model=NERResponse)
async def get_doc_entities(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:50000])
    entity_items = [EntityItem(**ent) for ent in res["entities"]]
    return NERResponse(
        entities=entity_items,
        entity_counts=res["entity_counts"],
    )


@router.get("/documents/{id}/nlp/ngrams", response_model=NgramsResponse)
async def get_doc_ngrams(
    id: uuid.UUID,
    n: int = Query(2, ge=1, le=3),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:50000])
    if n == 1:
        ngrams_list = [NgramItem(**item) for item in res["unigrams"]]
    elif n == 3:
        ngrams_list = [NgramItem(**item) for item in res["trigrams"]]
    else:
        ngrams_list = [NgramItem(**item) for item in res["bigrams"]]

    return NgramsResponse(ngrams=ngrams_list)


@router.get("/documents/{id}/nlp/frequency", response_model=FrequencyResponse)
async def get_doc_frequency(
    id: uuid.UUID,
    top_n: int = Query(20, ge=5, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:50000])
    freq_items = [FrequencyItem(**item) for item in res["frequencies"][:top_n]]
    return FrequencyResponse(frequencies=freq_items)


@router.get("/documents/{id}/nlp/readability", response_model=ReadabilityResponse)
async def get_doc_readability(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    res = preprocessor.process_full(full_text[:50000])
    return ReadabilityResponse(**res["readability"])


@router.get("/documents/{id}/nlp/keywords", response_model=KeywordsResponse)
async def get_doc_keywords(
    id: uuid.UUID,
    top_n: int = Query(15, ge=3, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    raw_keywords = keyword_extractor.extract(full_text[:50000], top_n=top_n)
    keyword_items = [
        KeywordItem(term=k["term"], score=k["score"], method=k["method"])
        for k in raw_keywords
    ]
    return KeywordsResponse(keywords=keyword_items)


@router.get("/documents/{id}/nlp/topics", response_model=TopicsResponse)
async def get_doc_topics(
    id: uuid.UUID,
    n_topics: int = Query(3, ge=2, le=10),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    # 1. Fetch chunks if available, else pages or split text
    chunks = db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == id)
        .order_by(DocumentChunk.chunk_index)
    ).scalars().all()

    if chunks:
        chunk_texts = [c.text for c in chunks if c.text.strip()]
    else:
        pages = db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == id)
            .order_by(DocumentPage.page_number)
        ).scalars().all()
        chunk_texts = [p.text for p in pages if p.text.strip()] or [full_text]

    # 2. Run LDA
    modeler = LDATopicModeler(n_topics=n_topics, n_words=5)
    lda_results = modeler.fit_transform(chunk_texts)
    lda_topics = [LDATopic(**t) for t in lda_results]

    # 3. Run KMeans Clustering
    clusterer = KMeansChunkClusterer(n_clusters=min(n_topics, max(2, len(chunk_texts))))
    cluster_results = clusterer.cluster_chunks(chunk_texts)
    clusters = [ChunkCluster(**c) for c in cluster_results]

    return TopicsResponse(lda_topics=lda_topics, clusters=clusters)


@router.get("/documents/{id}/search-term", response_model=SearchTermResponse)
async def search_term_occurrences(
    id: uuid.UUID,
    term: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    _, full_text = _get_document_text(db, id, user_id)

    # Find passages in DocumentPages
    pages = db.execute(
        select(DocumentPage).where(DocumentPage.document_id == id).order_by(DocumentPage.page_number)
    ).scalars().all()

    passages = []
    term_lower = term.lower()
    for p in pages:
        if term_lower in p.text.lower():
            passages.append(SearchTermPassage(
                chunk_id=str(p.id),
                page_start=p.page_number,
                page_end=p.page_number,
                score=1.0,
                text=p.text[:300],
            ))

    if not passages and term_lower in full_text.lower():
        passages.append(SearchTermPassage(
            chunk_id=str(id),
            page_start=1,
            page_end=1,
            score=1.0,
            text=full_text[:300],
        ))

    return SearchTermResponse(term=term, passages=passages)
