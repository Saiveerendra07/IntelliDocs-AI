import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.qgen import QuestionGenerator
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def qgen_test_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user_a = User(
        id=uuid.uuid4(),
        email=f"qgen_user_a_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="QGen User A",
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"qgen_user_b_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="QGen User B",
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    doc_id = uuid.uuid4()
    doc_a = Document(
        id=doc_id,
        user_id=user_a.id,
        original_filename="nlp_textbook_chapter3.pdf",
        stored_path="backend/storage/uploads/nlp_textbook_chapter3.pdf",
        mime_type="application/pdf",
        file_size=4096,
        status="ready",
        page_count=3,
    )
    db.add(doc_a)

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        text=(
            "Natural Language Processing is a branch of artificial intelligence that enables computers to understand text. "
            "Tokenization is the process of segmenting running text into discrete words or subword tokens. "
            "Part-of-speech tagging assigns grammatical categories like noun, verb, and adjective to each token. "
            "Named entity recognition detects real-world entities such as persons, locations, and organizations."
        ),
        token_count=65,
        page_start=1,
        page_end=1,
        section_title="Fundamentals of NLP",
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=1,
        text=(
            "Word embeddings represent semantic relationships as dense vectors in high-dimensional continuous vector spaces. "
            "Cosine similarity measures the angular distance between word vectors to quantify semantic relatedness. "
            "The Word2Vec architecture employs skip-gram and continuous bag-of-words objectives to learn distributed representations."
        ),
        token_count=50,
        page_start=2,
        page_end=2,
        section_title="Vector Semantics",
    )
    db.add(chunk_1)
    db.add(chunk_2)
    db.commit()

    token_a = create_access_token(data={"sub": str(user_a.id), "email": user_a.email})
    token_b = create_access_token(data={"sub": str(user_b.id), "email": user_b.email})

    yield {
        "db": db,
        "user_a": user_a,
        "user_b": user_b,
        "doc_id": doc_id,
        "chunks": [chunk_1, chunk_2],
        "token_a": token_a,
        "token_b": token_b,
    }

    try:
        db.delete(doc_a)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()
    except Exception:
        pass
    db.close()


def test_qgen_all_seven_types(qgen_test_setup):
    db = qgen_test_setup["db"]
    chunks = qgen_test_setup["chunks"]
    generator = QuestionGenerator(db)

    types = ["mcq", "true_false", "fill_blank", "short_answer", "conceptual", "flashcard", "long_form"]
    for t in types:
        questions = generator.generate_from_chunks(chunks=chunks, q_type=t, count=2)
        assert len(questions) >= 1
        q = questions[0]
        assert q["type"] == t
        assert q["question"] != ""
        assert q["correct_answer"] != ""
        assert "Page" in q["explanation"]

        if t == "mcq":
            assert len(q["options"]) == 4
            assert q["correct_answer"] in q["options"]
            # All options must be unique
            assert len(set(q["options"])) == 4
        elif t == "true_false":
            assert q["options"] == ["True", "False"]
            assert q["correct_answer"] in ["True", "False"]
        elif t == "fill_blank":
            assert "___________" in q["question"]
            assert len(q["options"]) == 4
            assert q["correct_answer"] in q["options"]


def test_qgen_difficulty_levels(qgen_test_setup):
    db = qgen_test_setup["db"]
    chunks = qgen_test_setup["chunks"]
    generator = QuestionGenerator(db)

    for diff in ["easy", "medium", "hard"]:
        questions = generator.generate_from_chunks(chunks=chunks, q_type="mcq", difficulty=diff, count=2)
        assert len(questions) >= 1
        for q in questions:
            assert q["difficulty"] == diff
            assert q["quality_score"] > 0.8


@pytest.mark.asyncio
async def test_qgen_api_endpoints_and_isolation(qgen_test_setup):
    doc_id = qgen_test_setup["doc_id"]
    token_a = qgen_test_setup["token_a"]
    token_b = qgen_test_setup["token_b"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. User A generates 3 MCQs
        gen_res = await client.post(
            "/api/v1/questions/generate",
            headers=headers_a,
            json={
                "document_id": str(doc_id),
                "type": "mcq",
                "difficulty": "medium",
                "count": 3,
            },
        )
        assert gen_res.status_code == 200
        qs = gen_res.json()
        assert len(qs) == 3
        assert qs[0]["document_id"] == str(doc_id)
        assert len(qs[0]["options"]) == 4

        # 2. User A lists questions
        list_res = await client.get(
            f"/api/v1/questions?document_id={doc_id}",
            headers=headers_a,
        )
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 3

        # 3. Isolation: User B cannot generate questions for User A's document (404)
        cross_res = await client.post(
            "/api/v1/questions/generate",
            headers=headers_b,
            json={
                "document_id": str(doc_id),
                "type": "mcq",
                "difficulty": "medium",
                "count": 2,
            },
        )
        assert cross_res.status_code == 404
