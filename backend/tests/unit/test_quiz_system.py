import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.db.models.quiz import GeneratedQuestion
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def quiz_test_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user_a = User(
        id=uuid.uuid4(),
        email=f"quiz_user_a_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Quiz User A",
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"quiz_user_b_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Quiz User B",
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user_a.id,
        original_filename="machine_learning.pdf",
        stored_path="backend/storage/uploads/machine_learning.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
        page_count=2,
    )
    db.add(doc)

    q1_id = uuid.uuid4()
    q1 = GeneratedQuestion(
        id=q1_id,
        user_id=user_a.id,
        document_id=doc_id,
        type="mcq",
        difficulty="medium",
        topic="Gradient Descent",
        question="What is the learning rate in gradient descent?",
        options=["Step size parameter", "Number of layers", "Batch size", "Loss function"],
        correct_answer="Step size parameter",
        explanation="The learning rate determines the step size at each iteration (Page 1).",
        page=1,
        quality_score=0.95,
    )

    q2_id = uuid.uuid4()
    q2 = GeneratedQuestion(
        id=q2_id,
        user_id=user_a.id,
        document_id=doc_id,
        type="mcq",
        difficulty="hard",
        topic="Backpropagation",
        question="Which rule is fundamentally used in backpropagation?",
        options=["Chain rule of calculus", "Product rule only", "L'Hopital rule", "Power rule"],
        correct_answer="Chain rule of calculus",
        explanation="Backpropagation repeatedly applies the chain rule to compute gradients (Page 2).",
        page=2,
        quality_score=0.96,
    )
    db.add(q1)
    db.add(q2)
    db.commit()

    token_a = create_access_token(data={"sub": str(user_a.id), "email": user_a.email})
    token_b = create_access_token(data={"sub": str(user_b.id), "email": user_b.email})

    yield {
        "db": db,
        "user_a": user_a,
        "user_b": user_b,
        "doc_id": doc_id,
        "q1_id": q1_id,
        "q2_id": q2_id,
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
async def test_quiz_lifecycle_and_evaluation(quiz_test_setup):
    doc_id = quiz_test_setup["doc_id"]
    q1_id = quiz_test_setup["q1_id"]
    q2_id = quiz_test_setup["q2_id"]
    token_a = quiz_test_setup["token_a"]
    token_b = quiz_test_setup["token_b"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. User A creates a Quiz
        create_res = await client.post(
            "/api/v1/quizzes",
            headers=headers_a,
            json={
                "document_id": str(doc_id),
                "title": "Deep Learning Fundamentals Quiz",
                "question_ids": [str(q1_id), str(q2_id)],
                "time_limit_seconds": 600,
            },
        )
        assert create_res.status_code == 201
        quiz_data = create_res.json()
        quiz_id = quiz_data["id"]
        assert len(quiz_data["questions"]) == 2
        assert quiz_data["questions"][0]["position"] == 1
        assert quiz_data["questions"][1]["position"] == 2

        # 2. User A retrieves quiz details
        get_res = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers_a)
        assert get_res.status_code == 200
        assert get_res.json()["title"] == "Deep Learning Fundamentals Quiz"

        # 3. User A starts an attempt
        start_res = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers_a)
        assert start_res.status_code == 200
        attempt_id = start_res.json()["id"]

        # 4. User A submits responses (1 correct on Gradient Descent, 1 incorrect on Backpropagation)
        submit_res = await client.post(
            f"/api/v1/attempts/{attempt_id}/submit",
            headers=headers_a,
            json={
                "responses": [
                    {
                        "quiz_question_id": str(q1_id),
                        "selected_answer": "Step size parameter",
                        "marked_for_review": False,
                    },
                    {
                        "quiz_question_id": str(q2_id),
                        "selected_answer": "Product rule only",  # Wrong answer
                        "marked_for_review": True,
                    },
                ],
                "time_taken_seconds": 120,
            },
        )
        assert submit_res.status_code == 200
        res_data = submit_res.json()
        assert res_data["score"] == 1
        assert res_data["total"] == 2
        assert res_data["accuracy"] == 50.0
        assert res_data["time_taken_seconds"] == 120
        assert len(res_data["responses"]) == 2
        assert res_data["responses"][0]["is_correct"] is True
        assert res_data["responses"][1]["is_correct"] is False
        assert "chain rule" in res_data["responses"][1]["explanation"].lower()

        # Weak topics diagnostic (<60% accuracy on Backpropagation)
        assert len(res_data["recommendations"]) >= 1
        assert res_data["recommendations"][0]["topic"] == "Backpropagation"
        assert res_data["recommendations"][0]["accuracy"] == 0.0

        # 5. User A reviews attempt
        review_res = await client.get(f"/api/v1/attempts/{attempt_id}", headers=headers_a)
        assert review_res.status_code == 200
        review_data = review_res.json()
        assert review_data["score"] == 1
        assert review_data["accuracy"] == 50.0

        # 6. Multi-tenant isolation: User B cannot start attempt or view User A's quiz/attempt
        cross_start = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers_b)
        assert cross_start.status_code == 404

        cross_review = await client.get(f"/api/v1/attempts/{attempt_id}", headers=headers_b)
        assert cross_review.status_code == 404
