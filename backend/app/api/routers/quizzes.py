import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.schemas.quiz import (
    QuestionGenerateRequest,
    GeneratedQuestionOut,
    QuizCreateRequest,
    QuizOut,
    QuizQuestionOut,
    QuizAttemptStartResponse,
    QuizSubmitRequest,
    QuizResultResponse,
    QuizQuestionResult,
    RecommendationItem,
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE, _PAGES_STORE

router = APIRouter(tags=["Questions & Quizzes"])

_QUESTIONS_STORE = {}
_QUIZZES_STORE = {}
_ATTEMPTS_STORE = {}


@router.post("/questions/generate", response_model=List[GeneratedQuestionOut])
async def generate_questions(req: QuestionGenerateRequest, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(req.document_id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    questions = []
    for i in range(req.count):
        qid = uuid.uuid4()
        record = {
            "id": qid,
            "document_id": req.document_id,
            "type": req.type,
            "difficulty": req.difficulty,
            "topic": req.topic or "Foundational Concepts",
            "question": f"Which statement best characterizes concept #{i + 1} in {doc['original_filename']}?",
            "options": [
                f"Option A: Standard definition of concept #{i + 1}",
                f"Option B: Distractor variant #{i + 1} with inverted logic",
                f"Option C: Irrelevant entity distractor",
                f"Option D: Secondary mechanism without prerequisite",
            ] if req.type == "mcq" else None,
            "correct_answer": f"Option A: Standard definition of concept #{i + 1}" if req.type == "mcq" else "True",
            "explanation": f"Concept #{i + 1} is verified on Page 1 from primary document text.",
            "page": 1,
            "quality_score": 0.94,
        }
        _QUESTIONS_STORE[qid] = record
        questions.append(record)

    return [GeneratedQuestionOut(**q) for q in questions]


@router.get("/questions", response_model=List[GeneratedQuestionOut])
async def list_questions(
    document_id: Optional[uuid.UUID] = None,
    current_user: dict = Depends(get_current_user),
):
    questions = list(_QUESTIONS_STORE.values())
    if document_id:
        questions = [q for q in questions if str(q["document_id"]) == str(document_id)]
    return [GeneratedQuestionOut(**q) for q in questions]


@router.post("/quizzes", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(req: QuizCreateRequest, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(req.document_id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    quiz_id = uuid.uuid4()
    questions_list = []
    for pos, q_id in enumerate(req.question_ids):
        q = _QUESTIONS_STORE.get(q_id)
        if q:
            questions_list.append(QuizQuestionOut(
                id=q_id,
                position=pos + 1,
                question=q["question"],
                options=q.get("options") or [],
                type=q["type"],
                difficulty=q["difficulty"],
            ))

    quiz_record = {
        "id": quiz_id,
        "user_id": current_user["id"],
        "document_id": req.document_id,
        "title": req.title,
        "time_limit_seconds": req.time_limit_seconds,
        "questions": questions_list,
        "created_at": datetime.now(timezone.utc),
    }
    _QUIZZES_STORE[quiz_id] = quiz_record

    return QuizOut(**quiz_record)


@router.get("/quizzes/{id}", response_model=QuizOut)
async def get_quiz(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    quiz = _QUIZZES_STORE.get(id)
    if not quiz or str(quiz["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Quiz not found.")
    return QuizOut(**quiz)


@router.post("/quizzes/{id}/attempts", response_model=QuizAttemptStartResponse)
async def start_quiz_attempt(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    quiz = _QUIZZES_STORE.get(id)
    if not quiz or str(quiz["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Quiz not found.")

    attempt_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    attempt_record = {
        "id": attempt_id,
        "quiz_id": id,
        "user_id": current_user["id"],
        "started_at": now,
        "submitted_at": None,
        "score": 0,
        "total": len(quiz["questions"]),
        "accuracy": 0.0,
        "time_taken_seconds": 0,
        "status": "in_progress",
        "responses": [],
    }
    _ATTEMPTS_STORE[attempt_id] = attempt_record

    return QuizAttemptStartResponse(
        id=attempt_id,
        quiz_id=id,
        started_at=now,
    )


@router.post("/attempts/{id}/submit", response_model=QuizResultResponse)
async def submit_quiz_attempt(
    id: uuid.UUID,
    req: QuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    attempt = _ATTEMPTS_STORE.get(id)
    if not attempt or str(attempt["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Attempt not found.")

    quiz = _QUIZZES_STORE.get(attempt["quiz_id"])
    now = datetime.now(timezone.utc)

    correct_count = 0
    question_results = []
    for resp in req.responses:
        q = _QUESTIONS_STORE.get(resp.quiz_question_id)
        if not q:
            continue

        is_correct = resp.selected_answer == q["correct_answer"]
        if is_correct:
            correct_count += 1

        question_results.append(QuizQuestionResult(
            quiz_question_id=resp.quiz_question_id,
            question_text=q["question"],
            selected_answer=resp.selected_answer,
            correct_answer=q["correct_answer"],
            is_correct=is_correct,
            explanation=q.get("explanation"),
            source_page=q.get("page"),
        ))

    total = max(len(req.responses), 1)
    accuracy = (correct_count / total) * 100

    attempt["submitted_at"] = now
    attempt["score"] = correct_count
    attempt["total"] = total
    attempt["accuracy"] = accuracy
    attempt["time_taken_seconds"] = req.time_taken_seconds
    attempt["status"] = "completed"
    attempt["responses"] = question_results

    recommendations = []
    if accuracy < 60:
        recommendations.append(RecommendationItem(
            topic="Foundational Concepts",
            accuracy=accuracy,
        ))

    return QuizResultResponse(
        attempt_id=id,
        quiz_id=attempt["quiz_id"],
        score=correct_count,
        total=total,
        accuracy=accuracy,
        time_taken_seconds=req.time_taken_seconds,
        recommendations=recommendations,
        responses=question_results,
    )


@router.get("/attempts/{id}/results", response_model=QuizResultResponse)
async def get_attempt_results(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    attempt = _ATTEMPTS_STORE.get(id)
    if not attempt or str(attempt["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Attempt not found.")

    recommendations = []
    if attempt["accuracy"] < 60:
        recommendations.append(RecommendationItem(
            topic="Foundational Concepts",
            accuracy=attempt["accuracy"],
        ))

    return QuizResultResponse(
        attempt_id=id,
        quiz_id=attempt["quiz_id"],
        score=attempt["score"],
        total=attempt["total"],
        accuracy=attempt["accuracy"],
        time_taken_seconds=attempt["time_taken_seconds"],
        recommendations=recommendations,
        responses=attempt["responses"],
    )
