import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.db.session import get_db
from backend.app.core.deps import get_current_user
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.db.models.quiz import (
    GeneratedQuestion,
    Quiz,
    QuizQuestion,
    QuizAttempt,
    QuizResponse,
)
from backend.app.nlp.qgen import QuestionGenerator
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

router = APIRouter(tags=["Questions & Quizzes"])

# Backward-compatible references for pending milestone modules
_QUESTIONS_STORE = {}
_QUIZZES_STORE = {}
_ATTEMPTS_STORE = {}


@router.post("/questions/generate", response_model=List[GeneratedQuestionOut])
def generate_questions(
    req: QuestionGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))

    # 1. Fetch document and ensure user ownership
    doc = db.execute(
        select(Document).where(Document.id == req.document_id, Document.user_id == user_id)
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 2. Fetch chunks
    chunks = db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == req.document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    ).scalars().all()

    if not chunks:
        # If document has no chunks yet, create synthetic default chunk from document path or empty text
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_index=0,
                text=f"Core concepts and foundational principles for {doc.original_filename}.",
                token_count=10,
                page_start=1,
                page_end=1,
                section_title="Introduction",
            )
        ]

    # 3. Generate questions using NLP QGen
    qgen = QuestionGenerator(db)
    generated_raw = qgen.generate_from_chunks(
        chunks=chunks,
        q_type=req.type,
        difficulty=req.difficulty,
        count=req.count,
        topic=req.topic,
    )

    # 4. Save to PostgreSQL GeneratedQuestion table
    out_records = []
    for q_item in generated_raw:
        q_id = uuid.uuid4()
        c_id = q_item.get("source_chunk_id")
        if isinstance(c_id, str):
            try:
                c_id = uuid.UUID(c_id)
            except Exception:
                c_id = None

        db_q = GeneratedQuestion(
            id=q_id,
            user_id=user_id,
            document_id=req.document_id,
            type=q_item["type"],
            difficulty=q_item["difficulty"],
            topic=q_item.get("topic") or "General Review",
            question=q_item["question"],
            options=q_item.get("options") or [],
            correct_answer=q_item["correct_answer"],
            explanation=q_item.get("explanation"),
            source_chunk_id=c_id,
            page=q_item.get("page", 1),
            quality_score=q_item.get("quality_score", 0.92),
        )
        db.add(db_q)
        out_records.append(db_q)

    db.commit()
    for rec in out_records:
        db.refresh(rec)

    return out_records


@router.get("/questions", response_model=List[GeneratedQuestionOut])
def list_questions(
    document_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    stmt = select(GeneratedQuestion).where(GeneratedQuestion.user_id == user_id)
    if document_id:
        stmt = stmt.where(GeneratedQuestion.document_id == document_id)
    stmt = stmt.order_by(desc(GeneratedQuestion.created_at))
    questions = db.execute(stmt).scalars().all()
    return questions


@router.post("/quizzes", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def create_quiz(
    req: QuizCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == req.document_id, Document.user_id == user_id)
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    quiz_id = uuid.uuid4()
    quiz = Quiz(
        id=quiz_id,
        user_id=user_id,
        document_id=req.document_id,
        title=req.title,
        time_limit_seconds=req.time_limit_seconds,
        config={},
    )
    db.add(quiz)

    # Attach questions
    questions_out = []
    for pos, q_id in enumerate(req.question_ids):
        gen_q = db.execute(
            select(GeneratedQuestion).where(GeneratedQuestion.id == q_id, GeneratedQuestion.user_id == user_id)
        ).scalar_one_or_none()
        if gen_q:
            qq = QuizQuestion(
                id=uuid.uuid4(),
                quiz_id=quiz_id,
                generated_question_id=gen_q.id,
                position=pos + 1,
            )
            db.add(qq)
            questions_out.append(QuizQuestionOut(
                id=gen_q.id,
                position=pos + 1,
                question=gen_q.question,
                options=gen_q.options or [],
                type=gen_q.type,
                difficulty=gen_q.difficulty,
            ))

    db.commit()
    db.refresh(quiz)

    return QuizOut(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        time_limit_seconds=quiz.time_limit_seconds,
        questions=questions_out,
        created_at=quiz.created_at,
    )


@router.get("/quizzes", response_model=List[QuizOut])
def list_quizzes(
    document_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    stmt = select(Quiz).where(Quiz.user_id == user_id)
    if document_id:
        stmt = stmt.where(Quiz.document_id == document_id)
    stmt = stmt.order_by(desc(Quiz.created_at))
    quizzes = db.execute(stmt).scalars().all()

    result = []
    for q in quizzes:
        qqs = db.execute(
            select(QuizQuestion, GeneratedQuestion)
            .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
            .where(QuizQuestion.quiz_id == q.id)
            .order_by(QuizQuestion.position.asc())
        ).all()

        q_list = [
            QuizQuestionOut(
                id=gq.id,
                position=qq.position,
                question=gq.question,
                options=gq.options or [],
                type=gq.type,
                difficulty=gq.difficulty,
            )
            for qq, gq in qqs
        ]
        result.append(QuizOut(
            id=q.id,
            document_id=q.document_id,
            title=q.title,
            time_limit_seconds=q.time_limit_seconds,
            questions=q_list,
            created_at=q.created_at,
        ))
    return result


@router.post("/quizzes/{id}/attempts", response_model=QuizAttemptStartResponse)
def start_quiz_attempt(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    quiz = db.execute(
        select(Quiz).where(Quiz.id == id, Quiz.user_id == user_id)
    ).scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    attempt = QuizAttempt(
        id=uuid.uuid4(),
        quiz_id=id,
        user_id=user_id,
        status="in_progress",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return QuizAttemptStartResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        started_at=attempt.started_at,
    )


@router.post("/attempts/{id}/submit", response_model=QuizResultResponse)
def submit_quiz_attempt(
    id: uuid.UUID,
    req: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    attempt = db.execute(
        select(QuizAttempt).where(QuizAttempt.id == id, QuizAttempt.user_id == user_id)
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found.")

    # Fetch quiz and questions
    quiz = db.execute(select(Quiz).where(Quiz.id == attempt.quiz_id)).scalar_one_or_none()
    qqs = db.execute(
        select(QuizQuestion, GeneratedQuestion)
        .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
        .where(QuizQuestion.quiz_id == attempt.quiz_id)
    ).all()

    # Map question_id to (QuizQuestion, GeneratedQuestion)
    q_map = {str(gq.id): (qq, gq) for qq, gq in qqs}

    correct_count = 0
    total_count = len(req.responses)
    detailed_results = []
    topic_scores = {}

    for resp in req.responses:
        q_entry = q_map.get(str(resp.quiz_question_id))
        if not q_entry:
            continue
        qq, gq = q_entry
        is_correct = (
            resp.selected_answer is not None
            and resp.selected_answer.strip().lower() == gq.correct_answer.strip().lower()
        )
        if is_correct:
            correct_count += 1

        # Track topic performance
        topic = gq.topic or "General"
        if topic not in topic_scores:
            topic_scores[topic] = {"correct": 0, "total": 0}
        topic_scores[topic]["total"] += 1
        if is_correct:
            topic_scores[topic]["correct"] += 1

        db_resp = QuizResponse(
            id=uuid.uuid4(),
            attempt_id=attempt.id,
            quiz_question_id=qq.id,
            selected_answer=resp.selected_answer,
            is_correct=is_correct,
            marked_for_review=resp.marked_for_review,
        )
        db.add(db_resp)

        detailed_results.append(QuizQuestionResult(
            quiz_question_id=gq.id,
            question_text=gq.question,
            selected_answer=resp.selected_answer,
            correct_answer=gq.correct_answer,
            is_correct=is_correct,
            explanation=gq.explanation,
            source_page=gq.page,
        ))

    accuracy = round((correct_count / max(1, total_count)) * 100, 2)
    attempt.status = "completed"
    attempt.score = float(correct_count)
    attempt.total = total_count
    attempt.accuracy = accuracy
    attempt.time_taken_seconds = req.time_taken_seconds
    attempt.submitted_at = datetime.now(timezone.utc)

    db.commit()

    # Maintain backward compatibility for analytics stub
    _ATTEMPTS_STORE[attempt.id] = {
        "id": attempt.id,
        "user_id": user_id,
        "accuracy": accuracy,
    }

    weak_topics = [
        RecommendationItem(topic=t, accuracy=round((v["correct"] / v["total"]) * 100, 1))
        for t, v in topic_scores.items()
        if (v["correct"] / v["total"]) < 0.6
    ]

    return QuizResultResponse(
        attempt_id=attempt.id,
        quiz_id=attempt.quiz_id,
        score=correct_count,
        total=total_count,
        accuracy=accuracy,
        time_taken_seconds=req.time_taken_seconds,
        questions=detailed_results,
        weak_topics=weak_topics,
    )
