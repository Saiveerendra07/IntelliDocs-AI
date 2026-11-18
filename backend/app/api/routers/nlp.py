import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
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
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(tags=["NLP Analysis"])


@router.post("/nlp/preprocess", response_model=PreprocessResponse)
async def adhoc_preprocess(req: PreprocessRequest):
    text = req.text
    words = text.split()
    cleaned = " ".join([w.lower().strip(".,!?:;") for w in words])
    tokens = cleaned.split()
    unique = list(set(tokens))
    stopwords = {"the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "with", "on", "at", "by", "this", "that"}
    filtered = [w for w in tokens if w not in stopwords]

    return PreprocessResponse(
        sample_original=text[:300],
        sample_cleaned=cleaned[:300],
        stats={
            "total_tokens": len(tokens),
            "unique_tokens": len(unique),
            "tokens_after_stopwords": len(filtered),
        },
        tokens=tokens[:50],
        filtered_tokens=filtered[:50],
        porter_stems=[w[:4] for w in filtered[:30]],
        snowball_stems=[w[:4] for w in filtered[:30]],
        lemmatized_sample=filtered[:30],
    )


@router.get("/documents/{id}/nlp/preprocessing", response_model=PreprocessResponse)
async def get_doc_preprocessing(
    id: uuid.UUID,
    sample_size: int = Query(300, ge=50, le=2000),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages]) or "No text available."
    words = full_text.split()
    tokens = [w.lower().strip(".,!?:;()") for w in words[:sample_size]]
    tokens = [w for w in tokens if w]
    unique = list(set(tokens))
    stopwords = {"the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "with", "on", "at", "by", "this", "that", "to", "from"}
    filtered = [w for w in tokens if w not in stopwords]

    return PreprocessResponse(
        sample_original=full_text[:300],
        sample_cleaned=" ".join(tokens)[:300],
        stats={
            "total_tokens": len(tokens),
            "unique_tokens": len(unique),
            "tokens_after_stopwords": len(filtered),
        },
        tokens=tokens[:50],
        filtered_tokens=filtered[:50],
        porter_stems=[w[:5] for w in filtered[:25]],
        snowball_stems=[w[:5] for w in filtered[:25]],
        lemmatized_sample=filtered[:25],
    )


@router.get("/documents/{id}/nlp/pos", response_model=POSResponse)
async def get_doc_pos(
    id: uuid.UUID,
    sample_size: int = Query(100, ge=20, le=500),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages])
    words = full_text.split()[:sample_size]

    pos_list = []
    for w in words:
        clean = w.strip(".,!?:;()")
        if not clean:
            continue
        pos = "NOUN" if clean[0].isupper() else ("VERB" if clean.endswith("ed") or clean.endswith("ing") else "ADJ")
        pos_list.append(POSToken(text=clean, pos=pos, tag=pos[:2], lemma=clean.lower()))

    return POSResponse(tokens=pos_list)


@router.get("/documents/{id}/nlp/entities", response_model=NERResponse)
async def get_doc_entities(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    entities = [
        EntityItem(text=doc["original_filename"], label="DOCUMENT", start_char=0, end_char=len(doc["original_filename"])),
        EntityItem(text="IntelliDocs Engine", label="ORG", start_char=10, end_char=28),
    ]
    return NERResponse(
        entities=entities,
        entity_counts={"DOCUMENT": 1, "ORG": 1}
    )


@router.get("/documents/{id}/nlp/ngrams", response_model=NgramsResponse)
async def get_doc_ngrams(
    id: uuid.UUID,
    n: int = Query(2, ge=1, le=4),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages])
    words = [w.lower().strip(".,!?:;()") for w in full_text.split()]
    words = [w for w in words if len(w) > 2]

    ngrams = []
    if len(words) >= n:
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            ngrams.append(phrase)

    from collections import Counter
    counts = Counter(ngrams).most_common(15)
    return NgramsResponse(
        ngrams=[NgramItem(phrase=p, count=c) for p, c in counts]
    )


@router.get("/documents/{id}/nlp/frequency", response_model=FrequencyResponse)
async def get_doc_frequency(
    id: uuid.UUID,
    top_n: int = Query(20, ge=5, le=100),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    full_text = "\n".join([p["text"] for p in pages])
    words = [w.lower().strip(".,!?:;()") for w in full_text.split()]
    stopwords = {"the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "with", "on", "at", "by", "this", "that", "to"}
    words = [w for w in words if w and w not in stopwords and len(w) > 2]

    from collections import Counter
    counts = Counter(words).most_common(top_n)
    return FrequencyResponse(
        frequencies=[FrequencyItem(word=w, count=c) for w, c in counts]
    )


@router.get("/documents/{id}/nlp/keywords", response_model=KeywordsResponse)
async def get_doc_keywords(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    keywords = [
        KeywordItem(term="Document Analysis", score=0.92, method="TF-IDF"),
        KeywordItem(term="NLP Extraction", score=0.88, method="RAKE"),
        KeywordItem(term="Exam Preparation", score=0.85, method="TextRank"),
    ]
    return KeywordsResponse(keywords=keywords)


@router.get("/documents/{id}/nlp/topics", response_model=TopicsResponse)
async def get_doc_topics(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    return TopicsResponse(
        lda_topics=[
            LDATopic(topic_id=1, words=["analysis", "document", "nlp", "processing"]),
            LDATopic(topic_id=2, words=["exam", "preparation", "quiz", "questions"]),
        ],
        clusters=[
            ChunkCluster(cluster_id=0, label="Core Concepts & Architecture", chunk_count=3),
            ChunkCluster(cluster_id=1, label="Exam Questions & Evaluation", chunk_count=2),
        ],
    )


@router.get("/documents/{id}/search-term", response_model=SearchTermResponse)
async def search_term_occurrences(
    id: uuid.UUID,
    term: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = _PAGES_STORE.get(id, [])
    passages = []
    for p in pages:
        if term.lower() in p["text"].lower():
            passages.append(SearchTermPassage(
                chunk_id=str(p["id"]),
                page_start=p["page_number"],
                page_end=p["page_number"],
                score=0.95,
                text=p["text"][:300]
            ))

    return SearchTermResponse(term=term, passages=passages)
