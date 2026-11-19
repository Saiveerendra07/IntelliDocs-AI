import math
import re
import uuid
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.vectorstore import VectorStoreManager


class BM25Retriever:
    """
    BM25 (Best Matching 25) Sparse Keyword Retriever implemented from scratch:
    - Tokenizes queries and document chunks
    - Calculates Inverse Document Frequency (IDF) with Okapi smoothing
    - Scores documents using term frequency saturation (k1=1.5, b=0.75)
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def retrieve(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        query_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query)]
        if not query_tokens:
            return []

        N = len(chunks)
        doc_lens = [len(c["text"].split()) for c in chunks]
        avgdl = sum(doc_lens) / max(1, N)

        # 1. Document frequency for query terms
        df = Counter()
        doc_term_freqs = []
        for c in chunks:
            tf = Counter([w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", c["text"])])
            doc_term_freqs.append(tf)
            for t in query_tokens:
                if tf[t] > 0:
                    df[t] += 1

        # 2. Score chunks
        scored_chunks = []
        for i, c in enumerate(chunks):
            score = 0.0
            tf = doc_term_freqs[i]
            dl = doc_lens[i]

            for t in query_tokens:
                if tf[t] == 0:
                    continue
                # Okapi IDF
                n_t = df[t]
                idf = math.log((N - n_t + 0.5) / (n_t + 0.5) + 1.0)
                # Term saturation
                freq = tf[t]
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (dl / avgdl))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scored_chunks.append({
                    "id": c["id"],
                    "text": c["text"],
                    "metadata": c.get("metadata", {}),
                    "bm25_score": round(score, 4),
                })

        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_chunks[:top_k]


class HybridRetriever:
    """
    Hybrid Retrieval Engine combining:
    1. Dense Semantic Search (SentenceTransformers + ChromaDB)
    2. Sparse Keyword Search (BM25 Okapi)
    3. Reciprocal Rank Fusion (RRF with k=60)
    """
    def __init__(self, db: Session):
        self.db = db
        self.vector_store = VectorStoreManager()
        self.bm25 = BM25Retriever()

    def search_hybrid(
        self,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[uuid.UUID]] = None,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ) -> List[Dict[str, Any]]:
        # 1. Dense Semantic Search
        dense_results = self.vector_store.search_semantic(
            user_id=user_id,
            query=query,
            top_k=top_k * 2,
            document_ids=document_ids,
        )

        # 2. Fetch candidate chunks from DB for BM25
        chunk_query = select(DocumentChunk).join(Document).where(Document.user_id == user_id)
        if document_ids:
            chunk_query = chunk_query.where(DocumentChunk.document_id.in_(document_ids))

        db_chunks = self.db.execute(chunk_query).scalars().all()
        chunks_for_bm25 = [
            {
                "id": f"{c.document_id}_{c.chunk_index}",
                "text": c.text,
                "metadata": {
                    "user_id": str(user_id),
                    "document_id": str(c.document_id),
                    "chunk_index": c.chunk_index,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "section_title": c.section_title or "",
                },
            }
            for c in db_chunks
        ]

        # Sparse BM25 Search
        sparse_results = self.bm25.retrieve(query, chunks_for_bm25, top_k=top_k * 2)

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF score = sum(weight / (k + rank)) with standard k=60
        rrf_k = 60.0
        fused_scores = defaultdict(float)
        chunk_map = {}

        for rank, item in enumerate(dense_results):
            cid = item["id"]
            chunk_map[cid] = item
            fused_scores[cid] += dense_weight * (1.0 / (rrf_k + rank + 1.0))

        for rank, item in enumerate(sparse_results):
            cid = item["id"]
            if cid not in chunk_map:
                chunk_map[cid] = item
            fused_scores[cid] += sparse_weight * (1.0 / (rrf_k + rank + 1.0))

        sorted_cids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)

        final_hits = []
        for rank, cid in enumerate(sorted_cids[:top_k]):
            item = chunk_map[cid]
            meta = item.get("metadata", {})
            page_start = meta.get("page_start", 1)
            page_end = meta.get("page_end", page_start)
            doc_id = meta.get("document_id", "")

            # Look up document title
            doc_title = "Document"
            if doc_id:
                try:
                    d_obj = self.db.execute(
                        select(Document).where(Document.id == uuid.UUID(doc_id))
                    ).scalar_one_or_none()
                    if d_obj:
                        doc_title = d_obj.original_filename
                except Exception:
                    pass

            citation = f"{doc_title} (Page {page_start})" if page_start == page_end else f"{doc_title} (Pages {page_start}-{page_end})"

            final_hits.append({
                "chunk_id": cid,
                "document_id": doc_id,
                "document_title": doc_title,
                "page_start": page_start,
                "page_end": page_end,
                "section_title": meta.get("section_title", ""),
                "citation": citation,
                "text": item["text"],
                "score": round(fused_scores[cid] * 100, 4),
            })

        return final_hits
