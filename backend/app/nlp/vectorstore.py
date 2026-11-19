import os
import uuid
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.nlp.embeddings import EmbeddingEngine


class VectorStoreManager:
    """
    ChromaDB Vector Store Manager:
    Manages persistent local vector collections and guarantees strict user isolation.
    """
    def __init__(self):
        chroma_path = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        os.makedirs(chroma_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.embedding_engine = EmbeddingEngine()
        self.collection_name = "intellidocs_chunks"
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_chunks(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: List[Any],
    ) -> int:
        """
        Embeds and indexes document chunks with strict multi-user metadata.
        """
        if not chunks:
            return 0

        ids = []
        texts = []
        metadatas = []

        for c in chunks:
            c_idx = c.chunk_index if hasattr(c, "chunk_index") else c.get("chunk_index", 0)
            chunk_id = f"{document_id}_{c_idx}"
            ids.append(chunk_id)
            texts.append(c.text if hasattr(c, "text") else c["text"])

            meta = {
                "user_id": str(user_id),
                "document_id": str(document_id),
                "chunk_index": int(c.chunk_index if hasattr(c, "chunk_index") else c.get("chunk_index", 0)),
                "page_start": int(c.page_start if hasattr(c, "page_start") else c.get("page_start", 1)),
                "page_end": int(c.page_end if hasattr(c, "page_end") else c.get("page_end", 1)),
                "section_title": str((c.section_title if hasattr(c, "section_title") else c.get("section_title")) or ""),
            }
            metadatas.append(meta)

        embeddings = self.embedding_engine.embed_documents(texts)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"Indexed {len(ids)} chunks for document {document_id} (User: {user_id})")
        return len(ids)

    def search_semantic(
        self,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic nearest-neighbor search with user-isolation metadata filtering.
        """
        query_embedding = self.embedding_engine.embed_text(query)

        # Build where clause enforcing user isolation
        where_clause: Dict[str, Any] = {"user_id": str(user_id)}
        if document_ids and len(document_ids) == 1:
            where_clause = {
                "$and": [
                    {"user_id": str(user_id)},
                    {"document_id": str(document_ids[0])},
                ]
            }
        elif document_ids and len(document_ids) > 1:
            where_clause = {
                "$and": [
                    {"user_id": str(user_id)},
                    {"document_id": {"$in": [str(d) for d in document_ids]}},
                ]
            }

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"ChromaDB query error: {e}")
            return []

        hits = []
        if results and results["ids"] and results["ids"][0]:
            count = len(results["ids"][0])
            for i in range(count):
                dist = results["distances"][0][i] if results["distances"] else 0.5
                # Chroma cosine distance is in [0, 2], convert to cosine similarity [0, 1]
                similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

                hits.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": round(similarity, 4),
                })

        return hits

    def delete_document_vectors(self, user_id: uuid.UUID, document_id: uuid.UUID) -> int:
        """Deletes all indexed vectors associated with a specific document."""
        try:
            where_clause = {
                "$and": [
                    {"user_id": str(user_id)},
                    {"document_id": str(document_id)},
                ]
            }
            self.collection.delete(where=where_clause)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete document vectors for {document_id}: {e}")
            return False
