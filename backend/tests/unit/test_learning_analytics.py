import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document
from backend.app.db.models.quiz import Quiz, QuizQuestion, QuizAttempt, QuizResponse, GeneratedQuestion
from backend.app.db.models.flashcard import Flashcard
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def analytics_test_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user_a = User(
        id=uuid.uuid4(),
        email=f"ana_user_a_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Analytics User A",
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"ana_user_b_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Analytics User B",
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    # User A has 1 document with 2 pages
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_a.id,
        original_filename="nlp_curriculum.pdf",
        stored_path="backend/storage/uploads/nlp_curriculum.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
        page_count=2,
    )
    db.add(doc)

    # 2 Questions with different topics
    q1 = GeneratedQuestion(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc.id,
        type="mcq",
        difficulty="medium",
        topic="Self-Attention",
        question="What does self-attention compute?",
        options=["Sequence representation", "Gradient norm", "Hidden state decay", "Dropout"],
        correct_answer="Sequence representation",
        explanation="Self-attention computes representation.",
        page=1,
    )
    q2 = GeneratedQuestion(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc.id,
        type="mcq",
        difficulty="hard",
        topic="Positional Encoding",
        question="What injects order information into transformers?",
        options=["Positional encodings", "BatchNorm", "Softmax", "LayerNorm"],
        correct_answer="Positional encodings",
        explanation="Positional encodings provide order.",
        page=2,
    )
    db.add(q1)
    db.add(q2)

    # 1 Quiz
    quiz = Quiz(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc.id,
        title="Attention Mechanism Assessment",
        time_limit_seconds=300,
    )
    db.add(quiz)

    qq1 = QuizQuestion(id=uuid.uuid4(), quiz_id=quiz.id, generated_question_id=q1.id, position=1)
    qq2 = QuizQuestion(id=uuid.uuid4(), quiz_id=quiz.id, generated_question_id=q2.id, position=2)
    db.add(qq1)
    db.add(qq2)

    # 1 Completed Attempt (q1 correct, q2 incorrect)
    attempt = QuizAttempt(
        id=uuid.uuid4(),
        quiz_id=quiz.id,
        user_id=user_a.id,
        status="completed",
        score=1.0,
        total=2,
        accuracy=50.0,
        time_taken_seconds=95,
        started_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(attempt)

    resp1 = QuizResponse(
        id=uuid.uuid4(),
        attempt_id=attempt.id,
        quiz_question_id=qq1.id,
        selected_answer="Sequence representation",
        is_correct=True,
    )
    resp2 = QuizResponse(
        id=uuid.uuid4(),
        attempt_id=attempt.id,
        quiz_question_id=qq2.id,
        selected_answer="LayerNorm",
        is_correct=False,
    )
    db.add(resp1)
    db.add(resp2)

    # 2 Flashcards for User A
    fc1 = Flashcard(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc.id,
        topic="Self-Attention",
        front="What is self-attention?",
        back="An attention mechanism connecting all positions of a sequence.",
        review_count=2,
    )
    fc2 = Flashcard(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc.id,
        topic="Positional Encoding",
        front="What is positional encoding?",
        back="Sinusoidal signals injected into input embeddings.",
        review_count=1,
    )
    db.add(fc1)
    db.add(fc2)
    db.commit()

    token_a = create_access_token(data={"sub": str(user_a.id), "email": user_a.email})
    token_b = create_access_token(data={"sub": str(user_b.id), "email": user_b.email})

    yield {
        "db": db,
        "user_a": user_a,
        "user_b": user_b,
        "doc": doc,
        "token_a": token_a,
        "token_b": token_b,
    }

    try:
        db.delete(doc)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()
    except Exception:
        pass
    db.close()


@pytest.mark.asyncio
async def test_learning_analytics_metrics(analytics_test_setup):
    token_a = analytics_test_setup["token_a"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Overview
        res = await client.get("/api/v1/analytics/overview", headers=headers_a)
        assert res.status_code == 200
        data = res.json()

        assert data["documents_count"] == 1
        assert data["total_pages"] == 2
        assert data["quizzes_completed"] == 1
        assert data["average_score"] == 50.0
        assert data["flashcards_count"] == 2
        assert data["flashcards_reviewed"] == 3
        assert data["study_streak_days"] >= 1
        assert data["topics_count"] == 2

        # Verify topic accuracy: Self-Attention 100%, Positional Encoding 0%
        topic_map = {t["topic"]: t["accuracy"] for t in data["topic_performance"]}
        assert topic_map["Self-Attention"] == 100.0
        assert topic_map["Positional Encoding"] == 0.0

        # 2. Weak topics
        weak_res = await client.get("/api/v1/analytics/weak-topics", headers=headers_a)
        assert weak_res.status_code == 200
        weak_data = weak_res.json()
        assert len(weak_data) == 1
        assert weak_data[0]["topic"] == "Positional Encoding"
        assert weak_data[0]["accuracy"] == 0.0

        # 3. Trends
        trend_res = await client.get("/api/v1/analytics/trends", headers=headers_a)
        assert trend_res.status_code == 200
        trends = trend_res.json()
        assert len(trends) == 1
        assert trends[0]["score"] == 50.0


@pytest.mark.asyncio
async def test_analytics_multi_user_isolation(analytics_test_setup):
    token_b = analytics_test_setup["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/analytics/overview", headers=headers_b)
        assert res.status_code == 200
        data = res.json()

        # User B has zero documents, zero quizzes, zero flashcards
        assert data["documents_count"] == 0
        assert data["quizzes_completed"] == 0
        assert data["average_score"] == 0.0
        assert data["flashcards_count"] == 0
        assert len(data["topic_performance"]) == 0
