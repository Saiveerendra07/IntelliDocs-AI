import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document
from backend.app.db.models.quiz import GeneratedQuestion
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.nlp.evaluation import evaluate_quiz_answer, normalize_text_for_comparison


def test_normalize_text_for_comparison():
    assert normalize_text_for_comparison("  Routing Information Protocol! ") == "routing information protocol"
    assert normalize_text_for_comparison("The Link-State Routing") == "link state routing"
    assert normalize_text_for_comparison("A standard TCP connection") == "standard tcp connection"


def test_evaluate_mcq():
    # Exact match
    res = evaluate_quiz_answer(
        question_type="mcq",
        user_answer="Link state routing",
        correct_answer="Link state routing",
        options=["Distance vector routing", "Link state routing", "Path vector routing", "Flooding"],
    )
    assert res["is_correct"] is True
    assert res["score"] == 1.0

    # Letter index match (B -> Link state routing)
    res_b = evaluate_quiz_answer(
        question_type="mcq",
        user_answer="B",
        correct_answer="Link state routing",
        options=["Distance vector routing", "Link state routing", "Path vector routing", "Flooding"],
    )
    assert res_b["is_correct"] is True
    assert res_b["score"] == 1.0

    # Wrong answer
    res_wrong = evaluate_quiz_answer(
        question_type="mcq",
        user_answer="Distance vector routing",
        correct_answer="Link state routing",
        options=["Distance vector routing", "Link state routing", "Path vector routing", "Flooding"],
    )
    assert res_wrong["is_correct"] is False
    assert res_wrong["score"] == 0.0


def test_evaluate_true_false():
    # True correct
    res = evaluate_quiz_answer(
        question_type="true_false",
        user_answer="True",
        correct_answer="True",
    )
    assert res["is_correct"] is True
    assert res["score"] == 1.0

    # False correct
    res_f = evaluate_quiz_answer(
        question_type="true_false",
        user_answer="False",
        correct_answer="False",
    )
    assert res_f["is_correct"] is True
    assert res_f["score"] == 1.0

    # Incorrect boolean
    res_bad = evaluate_quiz_answer(
        question_type="true_false",
        user_answer="True",
        correct_answer="False",
    )
    assert res_bad["is_correct"] is False
    assert res_bad["score"] == 0.0


def test_evaluate_fill_blank():
    # Exact match
    res_exact = evaluate_quiz_answer(
        question_type="fill_blank",
        user_answer="distance vector",
        correct_answer="distance vector",
    )
    assert res_exact["is_correct"] is True
    assert res_exact["score"] == 1.0

    # Minor typo (Levenshtein ratio >= 0.82)
    res_typo = evaluate_quiz_answer(
        question_type="fill_blank",
        user_answer="distence vecter",  # minor typo
        correct_answer="distance vector",
    )
    assert res_typo["is_correct"] is True
    assert res_typo["score"] == 1.0

    # Synonym / accepted variants (e.g. "RIP" vs "Routing Information Protocol")
    res_synonym = evaluate_quiz_answer(
        question_type="fill_blank",
        user_answer="RIP",
        correct_answer="Routing Information Protocol",
        accepted_answers=["RIP", "routing information protocol"],
    )
    assert res_synonym["is_correct"] is True
    assert res_synonym["score"] == 1.0

    # Completely wrong answer
    res_wrong = evaluate_quiz_answer(
        question_type="fill_blank",
        user_answer="virtual memory paging",
        correct_answer="distance vector",
    )
    assert res_wrong["is_correct"] is False
    assert res_wrong["score"] == 0.0


def test_evaluate_short_answer():
    model_ans = "A right outer join preserves all tuples from the right relation and pads unmatched left attributes with nulls."
    user_good = "It retains all rows from the right table while padding missing left values with null."

    res_good = evaluate_quiz_answer(
        question_type="short_answer",
        user_answer=user_good,
        correct_answer=model_ans,
    )
    assert res_good["score"] >= 0.40
    assert res_good["is_correct"] is True
    assert "feedback" in res_good
    assert isinstance(res_good.get("key_points_covered"), list)

    user_bad = "It performs matrix multiplication and gradient descent."
    res_bad = evaluate_quiz_answer(
        question_type="short_answer",
        user_answer=user_bad,
        correct_answer=model_ans,
    )
    assert res_bad["score"] < 0.35
    assert res_bad["is_correct"] is False


@pytest.fixture(scope="module")
def interactive_quiz_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user = User(
        id=uuid.uuid4(),
        email=f"interactive_user_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Interactive User",
    )
    db.add(user)
    db.commit()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        original_filename="ch4_sql.pdf",
        stored_path="backend/storage/uploads/ch4_sql.pdf",
        mime_type="application/pdf",
        file_size=4096,
        status="ready",
        page_count=10,
    )
    db.add(doc)

    # 1. MCQ
    q_mcq = GeneratedQuestion(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc_id,
        type="mcq",
        difficulty="medium",
        topic="Outer Joins",
        question="What is preserved in a right outer join?",
        options=["All right tuples", "All left tuples", "Only matching tuples", "No tuples"],
        correct_answer="All right tuples",
        explanation="Right outer join preserves all tuples from the right relation (Page 3).",
        page=3,
        quality_score=0.95,
    )
    # 2. True / False
    q_tf = GeneratedQuestion(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc_id,
        type="true_false",
        difficulty="easy",
        topic="Views",
        question="True or False: A view in SQL is a virtual relation defined by a query.",
        options=["True", "False"],
        correct_answer="True",
        explanation="Views are virtual relations created by create view (Page 5).",
        page=5,
        quality_score=0.95,
    )
    # 3. Fill in the blank
    q_fib = GeneratedQuestion(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc_id,
        type="fill_blank",
        difficulty="medium",
        topic="Authorization",
        question="Fill in the blank: The ___ statement is used to allocate privileges in SQL.",
        options=[],
        correct_answer="GRANT",
        explanation="The GRANT statement confers authorization permissions (Page 8).",
        page=8,
        quality_score=0.95,
    )
    db.add_all([q_mcq, q_tf, q_fib])
    db.commit()

    token = create_access_token(data={"sub": str(user.id), "email": user.email})

    yield {
        "db": db,
        "user": user,
        "doc_id": doc_id,
        "q_mcq": q_mcq,
        "q_tf": q_tf,
        "q_fib": q_fib,
        "token": token,
    }

    try:
        db.delete(doc)
        db.delete(user)
        db.commit()
    except Exception:
        pass
    db.close()


@pytest.mark.asyncio
async def test_single_question_response_flow(interactive_quiz_setup):
    setup = interactive_quiz_setup
    token = setup["token"]
    headers = {"Authorization": f"Bearer {token}"}
    q_mcq = setup["q_mcq"]
    q_tf = setup["q_tf"]
    q_fib = setup["q_fib"]
    doc_id = setup["doc_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Quiz
        create_res = await client.post(
            "/api/v1/quizzes",
            headers=headers,
            json={
                "document_id": str(doc_id),
                "title": "Interactive SQL Quiz",
                "question_ids": [str(q_mcq.id), str(q_tf.id), str(q_fib.id)],
                "time_limit_seconds": 600,
            },
        )
        assert create_res.status_code == 201
        quiz_id = create_res.json()["id"]

        # Ensure correct_answer is masked in quiz details
        detail_res = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
        assert detail_res.status_code == 200
        for q in detail_res.json()["questions"]:
            assert q.get("correct_answer") is None
            assert q.get("explanation") is None

        # Start attempt
        start_res = await client.post(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers)
        assert start_res.status_code == 200
        attempt_id = start_res.json()["id"]

        # Respond to Question 1 (MCQ) - Correct
        r1 = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            headers=headers,
            json={
                "quiz_question_id": str(q_mcq.id),
                "user_answer": "All right tuples",
                "time_taken_seconds": 15,
            },
        )
        assert r1.status_code == 200
        r1_data = r1.json()
        assert r1_data["is_correct"] is True
        assert r1_data["score"] == 1.0
        assert r1_data["correct_answer"] == "All right tuples"
        assert "Page 3" in r1_data["explanation"]

        # Respond to Question 2 (True/False) - Correct
        r2 = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            headers=headers,
            json={
                "quiz_question_id": str(q_tf.id),
                "user_answer": "True",
                "time_taken_seconds": 10,
            },
        )
        assert r2.status_code == 200
        assert r2.json()["is_correct"] is True

        # Respond to Question 3 (Fill in blank) - Correct with case-insensitivity
        r3 = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            headers=headers,
            json={
                "quiz_question_id": str(q_fib.id),
                "user_answer": "grant",
                "time_taken_seconds": 12,
            },
        )
        assert r3.status_code == 200
        assert r3.json()["is_correct"] is True

        # Submit attempt without re-sending responses
        sub_res = await client.post(
            f"/api/v1/attempts/{attempt_id}/submit",
            headers=headers,
            json={"time_taken_seconds": 37},
        )
        assert sub_res.status_code == 200
        sub_data = sub_res.json()
        assert sub_data["score"] == 3
        assert sub_data["total"] == 3
        assert sub_data["accuracy"] == 100.0
        assert len(sub_data["topic_performance"]) >= 3
