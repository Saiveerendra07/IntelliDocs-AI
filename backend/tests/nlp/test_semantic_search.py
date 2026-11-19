import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.nlp.embeddings import EmbeddingEngine
from backend.app.nlp.vectorstore import VectorStoreManager
from backend.app.nlp.retrieval import BM25Retriever, HybridRetriever


def test_embedding_engine():
    engine = EmbeddingEngine()
    vec = engine.embed_text("Deep neural networks and natural language understanding.")

    assert isinstance(vec, list)
    assert len(vec) == 384  # MiniLM dimension

    # Test semantic similarity
    sim_close = engine.cosine_similarity(
        engine.embed_text("Artificial intelligence and machine learning."),
        engine.embed_text("Deep learning and neural network algorithms."),
    )
    sim_far = engine.cosine_similarity(
        engine.embed_text("Artificial intelligence and machine learning."),
        engine.embed_text("Delicious chocolate cake recipe with vanilla frosting."),
    )
    assert sim_close > sim_far


def test_bm25_retriever():
    retriever = BM25Retriever(k1=1.5, b=0.75)
    chunks = [
        {"id": "c1", "text": "Operating systems manage virtual memory, paging tables, and cpu scheduling."},
        {"id": "c2", "text": "Relational databases use B-tree indexes, ACID transactions, and SQL queries."},
        {"id": "c3", "text": "Computer networks use TCP/IP packets, routing tables, and socket interfaces."},
    ]

    results = retriever.retrieve("virtual memory and paging", chunks, top_k=2)
    assert len(results) > 0
    assert results[0]["id"] == "c1"
    assert results[0]["bm25_score"] > 0.0


def test_vector_store_manager_and_isolation():
    manager = VectorStoreManager()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()

    chunks_a = [
        {"chunk_index": 0, "text": "Quantum mechanics and wave particle duality experiments.", "page_start": 1, "page_end": 1, "section_title": "Quantum Physics"},
    ]
    chunks_b = [
        {"chunk_index": 0, "text": "Organic chemistry synthesis of aromatic benzene derivatives.", "page_start": 1, "page_end": 1, "section_title": "Organic Chem"},
    ]

    # Index User A and User B
    count_a = manager.index_chunks(user_a, doc_a, chunks_a)
    count_b = manager.index_chunks(user_b, doc_b, chunks_b)
    assert count_a == 1
    assert count_b == 1

    # User A searches for physics
    res_a = manager.search_semantic(user_a, "quantum physics wave experiment", top_k=5)
    assert len(res_a) == 1
    assert "Quantum" in res_a[0]["text"]

    # CRITICAL ISOLATION: User B searching for physics finds NOTHING from User A
    res_b = manager.search_semantic(user_b, "quantum physics wave experiment", top_k=5)
    assert not any("Quantum" in item["text"] for item in res_b)
    assert all(item["metadata"]["user_id"] == str(user_b) for item in res_b)

    # Clean up
    manager.delete_document_vectors(user_a, doc_a)
    manager.delete_document_vectors(user_b, doc_b)


@pytest.mark.asyncio
async def test_search_api_endpoints_and_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        uid_a = uuid.uuid4().hex[:8]
        reg_a = await client.post("/api/v1/auth/register", json={
            "email": f"search_a_{uid_a}@univ.edu",
            "password": "Password123!",
            "full_name": "Student A",
        })
        token_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register User B
        uid_b = uuid.uuid4().hex[:8]
        reg_b = await client.post("/api/v1/auth/register", json={
            "email": f"search_b_{uid_b}@univ.edu",
            "password": "Password123!",
            "full_name": "Student B",
        })
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User A uploads a document on Computer Systems
        doc_content = (
            "Virtual memory divides addressable space into fixed-sized blocks called pages. "
            "Page tables translate virtual addresses into physical frame numbers. "
            "When a requested page is not in physical RAM, a page fault exception is generated."
        )
        upload_a = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("virtual_memory.txt", doc_content.encode("utf-8"), "text/plain")},
        )
        assert upload_a.status_code == 201
        doc_a_id = upload_a.json()["id"]

        # 1. User A performs semantic search
        search_res = await client.post(
            "/api/v1/search",
            headers=headers_a,
            json={"query": "how do page tables translate virtual addresses?", "top_k": 3},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert len(search_data["results"]) > 0
        assert "virtual_memory.txt" in search_data["results"][0]["filename"]
        assert search_data["results"][0]["page_start"] == 1

        # 2. Filter by document_ids
        filtered_search = await client.post(
            "/api/v1/search",
            headers=headers_a,
            json={
                "query": "page fault exception",
                "document_ids": [doc_a_id],
                "top_k": 2,
            },
        )
        assert filtered_search.status_code == 200
        assert len(filtered_search.json()["results"]) > 0

        # 3. CRITICAL SECURITY INVARIANT: User B searching for virtual memory gets 0 results from User A
        b_search = await client.post(
            "/api/v1/search",
            headers=headers_b,
            json={"query": "virtual memory page fault exception", "top_k": 5},
        )
        assert b_search.status_code == 200
        assert len(b_search.json()["results"]) == 0
