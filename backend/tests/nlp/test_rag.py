import os
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.db.models.chat import Conversation, ChatMessage
from backend.app.nlp.vectorstore import VectorStoreManager
from backend.app.nlp.rag import RAGEngine
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def rag_test_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # User A
    user_a = User(
        id=uuid.uuid4(),
        email=f"rag_user_a_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="RAG User A",
    )
    # User B
    user_b = User(
        id=uuid.uuid4(),
        email=f"rag_user_b_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="RAG User B",
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    # Document for User A
    doc_id = uuid.uuid4()
    doc_a = Document(
        id=doc_id,
        user_id=user_a.id,
        original_filename="attention_mechanisms.pdf",
        stored_path="backend/storage/uploads/attention_mechanisms.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
        page_count=2,
    )
    db.add(doc_a)

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        text=(
            "The Transformer architecture relies entirely on an attention mechanism to draw global dependencies "
            "between input and output. The self-attention mechanism connects all positions of a single sequence "
            "in order to compute a representation of the sequence. Multi-head attention allows the model to "
            "jointly attend to information from different representation subspaces at different positions."
        ),
        token_count=65,
        page_start=1,
        page_end=1,
        section_title="Attention Is All You Need",
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=1,
        text=(
            "Positional encodings are added to the input embeddings at the bottoms of the encoder and decoder stacks. "
            "Since the model contains no recurrence and no convolution, positional encodings inject order information "
            "into the sequence using sine and cosine functions of different frequencies."
        ),
        token_count=55,
        page_start=2,
        page_end=2,
        section_title="Positional Encodings",
    )
    db.add(chunk_1)
    db.add(chunk_2)
    db.commit()

    # Index into ChromaDB
    vs = VectorStoreManager()
    chunks_data = [
        {
            "id": f"{doc_id}_0",
            "text": chunk_1.text,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "section_title": chunk_1.section_title,
        },
        {
            "id": f"{doc_id}_1",
            "text": chunk_2.text,
            "page_start": 2,
            "page_end": 2,
            "chunk_index": 1,
            "section_title": chunk_2.section_title,
        },
    ]
    vs.index_chunks(user_id=user_a.id, document_id=doc_id, chunks=chunks_data)

    token_a = create_access_token(data={"sub": str(user_a.id), "email": user_a.email})
    token_b = create_access_token(data={"sub": str(user_b.id), "email": user_b.email})

    yield {
        "db": db,
        "user_a": user_a,
        "user_b": user_b,
        "doc_id": doc_id,
        "token_a": token_a,
        "token_b": token_b,
    }

    # Cleanup
    try:
        vs.delete_document_chunks(doc_id)
        db.delete(doc_a)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()
    except Exception:
        pass
    db.close()


def test_rag_engine_grounded_answer(rag_test_setup):
    db = rag_test_setup["db"]
    user_a = rag_test_setup["user_a"]
    doc_id = rag_test_setup["doc_id"]

    rag_engine = RAGEngine(db)
    result = rag_engine.generate_answer(
        user_id=user_a.id,
        query="How does self-attention compute representation?",
        document_ids=[doc_id],
        explanation_mode="detailed",
    )

    assert result["answer"] != ""
    assert "Technical Analysis" in result["answer"]
    assert "attention" in result["answer"].lower()
    assert len(result["sources"]) >= 1
    assert result["sources"][0]["page_start"] == 1
    assert "Page 1" in result["answer"]
    assert result["confidence_score"] > 0.3


def test_rag_explanation_modes(rag_test_setup):
    db = rag_test_setup["db"]
    user_a = rag_test_setup["user_a"]
    doc_id = rag_test_setup["doc_id"]
    rag_engine = RAGEngine(db)

    # 1. Beginner mode
    res_beg = rag_engine.generate_answer(
        user_id=user_a.id,
        query="What is positional encoding?",
        document_ids=[doc_id],
        explanation_mode="beginner",
    )
    assert "Plain-English Overview" in res_beg["answer"]
    assert "Core Idea" in res_beg["answer"]

    # 2. Exam mode
    res_exam = rag_engine.generate_answer(
        user_id=user_a.id,
        query="Explain positional encodings and sine cosine functions",
        document_ids=[doc_id],
        explanation_mode="exam",
    )
    assert "High-Yield Exam Summary" in res_exam["answer"]
    assert "Critical Concepts" in res_exam["answer"]
    assert "Exam Tip" in res_exam["answer"]

    # 3. Example mode
    res_ex = rag_engine.generate_answer(
        user_id=user_a.id,
        query="How are transformers applied in practice?",
        document_ids=[doc_id],
        explanation_mode="example",
    )
    assert "Real-World Application" in res_ex["answer"]
    assert "Practical Context" in res_ex["answer"]


def test_rag_empty_or_unrelated_query(rag_test_setup):
    db = rag_test_setup["db"]
    user_a = rag_test_setup["user_a"]
    rag_engine = RAGEngine(db)

    res_empty = rag_engine.generate_answer(
        user_id=user_a.id,
        query="",
    )
    assert "Please ask a question" in res_empty["answer"]
    assert res_empty["confidence_score"] == 0.0


@pytest.mark.asyncio
async def test_chat_api_endpoints_and_isolation(rag_test_setup):
    doc_id = rag_test_setup["doc_id"]
    token_a = rag_test_setup["token_a"]
    token_b = rag_test_setup["token_b"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. User A creates conversation
        conv_res = await client.post(
            "/api/v1/chat/conversations",
            headers=headers_a,
            json={
                "title": "Transformers Q&A",
                "document_ids": [str(doc_id)],
                "explanation_mode": "exam",
            },
        )
        assert conv_res.status_code == 201
        conv_data = conv_res.json()
        conv_id = conv_data["id"]
        assert conv_data["title"] == "Transformers Q&A"

        # 2. User A asks question
        ask_res = await client.post(
            f"/api/v1/chat/conversations/{conv_id}/ask",
            headers=headers_a,
            json={
                "query": "What are positional encodings used for?",
                "document_ids": [str(doc_id)],
                "explanation_mode": "exam",
            },
        )
        assert ask_res.status_code == 200
        ask_data = ask_res.json()
        assert "answer" in ask_data
        assert len(ask_data["sources"]) >= 1
        assert ask_data["confidence_score"] > 0

        # 3. User A views message history
        msg_res = await client.get(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            headers=headers_a,
        )
        assert msg_res.status_code == 200
        messages = msg_res.json()
        assert len(messages) >= 2  # user message and assistant message
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert len(messages[1]["sources"]) >= 1

        # 4. Multi-tenant isolation: User B CANNOT access User A's conversation (404)
        cross_res = await client.get(
            f"/api/v1/chat/conversations/{conv_id}",
            headers=headers_b,
        )
        assert cross_res.status_code == 404

        cross_msg_res = await client.get(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            headers=headers_b,
        )
        assert cross_msg_res.status_code == 404

        # 5. User A deletes conversation
        del_res = await client.delete(
            f"/api/v1/chat/conversations/{conv_id}",
            headers=headers_a,
        )
        assert del_res.status_code == 204

        # Verify deletion
        get_again = await client.get(
            f"/api/v1/chat/conversations/{conv_id}",
            headers=headers_a,
        )
        assert get_again.status_code == 404
