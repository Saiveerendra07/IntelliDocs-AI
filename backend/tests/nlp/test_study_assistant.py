import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.vectorstore import VectorStoreManager
from backend.app.nlp.explain import StudyAssistantEngine
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def tutor_test_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user = User(
        id=uuid.uuid4(),
        email=f"tutor_user_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Tutor Student",
    )
    db.add(user)
    db.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        original_filename="recurrent_neural_networks.pdf",
        stored_path="backend/storage/uploads/recurrent_neural_networks.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
        page_count=2,
    )
    db.add(doc)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        text=(
            "Recurrent neural networks suffer from the vanishing gradient problem when trained over long sequences. "
            "Gradients computed via backpropagation through time diminish exponentially as they propagate backward. "
            "Long Short-Term Memory networks introduce gating mechanisms and a separate cell state to maintain constant error carousels."
        ),
        token_count=52,
        page_start=1,
        page_end=1,
        section_title="Sequential Architectures",
    )
    db.add(chunk)
    db.commit()

    # Index into ChromaDB
    vs = VectorStoreManager()
    vs.index_chunks(
        user_id=user.id,
        document_id=doc_id,
        chunks=[{
            "id": f"{doc_id}_0",
            "text": chunk.text,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "section_title": chunk.section_title,
        }]
    )

    token = create_access_token(data={"sub": str(user.id), "email": user.email})

    yield {
        "db": db,
        "user": user,
        "doc_id": doc_id,
        "token": token,
    }

    try:
        vs.delete_document_chunks(doc_id)
        db.delete(doc)
        db.delete(user)
        db.commit()
    except Exception:
        pass
    db.close()


def test_tutor_all_four_pedagogical_modes(tutor_test_setup):
    db = tutor_test_setup["db"]
    user = tutor_test_setup["user"]
    doc_id = tutor_test_setup["doc_id"]
    engine = StudyAssistantEngine(db)

    # 1. Socratic mode
    soc = engine.assist(
        user_id=user.id,
        query="Why do recurrent networks suffer from vanishing gradients?",
        document_ids=[doc_id],
        tutor_mode="socratic",
    )
    assert soc["tutor_mode"] == "socratic"
    assert "Socratic Exploration" in soc["response"]
    assert "Reflective Questions" in soc["response"]
    assert len(soc["sources"]) >= 1

    # 2. Simplify mode
    simp = engine.assist(
        user_id=user.id,
        query="Explain how LSTM cell states work",
        document_ids=[doc_id],
        tutor_mode="simplify",
    )
    assert simp["tutor_mode"] == "simplify"
    assert "Step-by-Step Simplification" in simp["response"]
    assert "Step 1:" in simp["response"]

    # 3. Analogy mode
    ana = engine.assist(
        user_id=user.id,
        query="Give me an analogy for vanishing gradients",
        document_ids=[doc_id],
        tutor_mode="analogy",
    )
    assert ana["tutor_mode"] == "analogy"
    assert "Intuitive Mental Model" in ana["response"]
    assert "Everyday Analogy" in ana["response"]

    # 4. Misconception mode
    misc = engine.assist(
        user_id=user.id,
        query="Do standard RNNs maintain constant error carousels?",
        document_ids=[doc_id],
        tutor_mode="misconception",
    )
    assert misc["tutor_mode"] == "misconception"
    assert "Misconception Check" in misc["response"]
    assert "Key Clarification" in misc["response"]


@pytest.mark.asyncio
async def test_tutor_api_endpoint(tutor_test_setup):
    doc_id = tutor_test_setup["doc_id"]
    token = tutor_test_setup["token"]
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/assistant/tutor",
            headers=headers,
            json={
                "query": "How do gating mechanisms prevent vanishing gradients?",
                "document_ids": [str(doc_id)],
                "tutor_mode": "socratic",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["tutor_mode"] == "socratic"
        assert "Socratic Exploration" in data["response"]
        assert len(data["sources"]) >= 1
        assert data["confidence_score"] > 0
