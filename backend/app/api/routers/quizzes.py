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
from backend.app.services.quiz_service import QuizService
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
    service = QuizService(db)
    try:
        quiz = service.create_quiz(user_id=user_id, req=req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    qqs = db.execute(
        select(QuizQuestion, GeneratedQuestion)
        .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
        .where(QuizQuestion.quiz_id == quiz.id)
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

    return QuizOut(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        time_limit_seconds=quiz.time_limit_seconds,
        questions=q_list,
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


@router.get("/quizzes/{id}", response_model=QuizOut)
def get_quiz(
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

    qqs = db.execute(
        select(QuizQuestion, GeneratedQuestion)
        .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
        .where(QuizQuestion.quiz_id == quiz.id)
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

    return QuizOut(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        time_limit_seconds=quiz.time_limit_seconds,
        questions=q_list,
        created_at=quiz.created_at,
    )


@router.post("/quizzes/{id}/attempts", response_model=QuizAttemptStartResponse)
def start_quiz_attempt(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = QuizService(db)
    try:
        attempt = service.start_attempt(user_id=user_id, quiz_id=id)
        return QuizAttemptStartResponse(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            started_at=attempt.started_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/attempts/{id}/submit", response_model=QuizResultResponse)
def submit_quiz_attempt(
    id: uuid.UUID,
    req: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = QuizService(db)
    try:
        result = service.submit_attempt(user_id=user_id, attempt_id=id, req=req)

        # Maintain backward compatibility for analytics stub
        _ATTEMPTS_STORE[id] = {
            "id": id,
            "user_id": user_id,
            "accuracy": result["accuracy"],
        }

        return QuizResultResponse(
            attempt_id=result["attempt_id"],
            quiz_id=result["quiz_id"],
            score=result["score"],
            total=result["total"],
            accuracy=result["accuracy"],
            time_taken_seconds=result["time_taken_seconds"],
            responses=[QuizQuestionResult(**q) for q in result["questions"]],
            recommendations=[RecommendationItem(**w) for w in result["weak_topics"]],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/attempts/{id}", response_model=QuizResultResponse)
def get_attempt_review(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = QuizService(db)
    try:
        result = service.get_attempt_review(user_id=user_id, attempt_id=id)
        return QuizResultResponse(
            attempt_id=result["attempt_id"],
            quiz_id=result["quiz_id"],
            score=result["score"],
            total=result["total"],
            accuracy=result["accuracy"],
            time_taken_seconds=result["time_taken_seconds"],
            responses=[QuizQuestionResult(**q) for q in result["questions"]],
            recommendations=[RecommendationItem(**w) for w in result["weak_topics"]],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
