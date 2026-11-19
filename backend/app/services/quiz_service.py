import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.db.models.quiz import (
    Quiz,
    QuizQuestion,
    QuizAttempt,
    QuizResponse,
    GeneratedQuestion,
)
from backend.app.db.models.document import Document
from backend.app.schemas.quiz import (
    QuizCreateRequest,
    QuizSubmitRequest,
    QuizOut,
    QuizQuestionOut,
    QuizResultResponse,
    QuizQuestionResult,
    RecommendationItem,
)


class QuizService:
    """
    Core Domain Service for Interactive Quiz System:
    - Quiz creation with question ordering
    - Timed quiz attempt lifecycle
    - Submission validation, accurate scoring, and detailed explanation retrieval
    - Weak topic diagnostic identification (<60% mastery threshold)
    """
    def __init__(self, db: Session):
        self.db = db

    def create_quiz(self, user_id: uuid.UUID, req: QuizCreateRequest) -> Quiz:
        doc = self.db.execute(
            select(Document).where(Document.id == req.document_id, Document.user_id == user_id)
        ).scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {req.document_id} not found.")

        quiz_id = uuid.uuid4()
        quiz = Quiz(
            id=quiz_id,
            user_id=user_id,
            document_id=req.document_id,
            title=req.title,
            time_limit_seconds=req.time_limit_seconds,
            config={},
        )
        self.db.add(quiz)

        for pos, q_id in enumerate(req.question_ids):
            gen_q = self.db.execute(
                select(GeneratedQuestion).where(
                    GeneratedQuestion.id == q_id,
                    GeneratedQuestion.user_id == user_id,
                )
            ).scalar_one_or_none()
            if gen_q:
                qq = QuizQuestion(
                    id=uuid.uuid4(),
                    quiz_id=quiz_id,
                    generated_question_id=gen_q.id,
                    position=pos + 1,
                )
                self.db.add(qq)

        self.db.commit()
        self.db.refresh(quiz)
        return quiz

    def start_attempt(self, user_id: uuid.UUID, quiz_id: uuid.UUID) -> QuizAttempt:
        quiz = self.db.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        ).scalar_one_or_none()
        if not quiz:
            raise ValueError(f"Quiz {quiz_id} not found.")

        attempt = QuizAttempt(
            id=uuid.uuid4(),
            quiz_id=quiz_id,
            user_id=user_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def submit_attempt(
        self,
        user_id: uuid.UUID,
        attempt_id: uuid.UUID,
        req: QuizSubmitRequest,
    ) -> Dict[str, Any]:
        attempt = self.db.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user_id)
        ).scalar_one_or_none()
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found.")

        quiz = self.db.execute(select(Quiz).where(Quiz.id == attempt.quiz_id)).scalar_one_or_none()
        qqs = self.db.execute(
            select(QuizQuestion, GeneratedQuestion)
            .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
            .where(QuizQuestion.quiz_id == attempt.quiz_id)
            .order_by(QuizQuestion.position.asc())
        ).all()

        q_map = {str(gq.id): (qq, gq) for qq, gq in qqs}
        # Also map by QuizQuestion.id
        qq_id_map = {str(qq.id): (qq, gq) for qq, gq in qqs}

        correct_count = 0
        total_count = len(req.responses)
        detailed_results = []
        topic_scores = {}

        for resp in req.responses:
            # lookup by quiz_question_id or generated_question_id
            pair = q_map.get(str(resp.quiz_question_id)) or qq_id_map.get(str(resp.quiz_question_id))
            if not pair:
                continue
            qq, gq = pair

            is_correct = False
            if resp.selected_answer is not None:
                user_clean = resp.selected_answer.strip().lower()
                target_clean = gq.correct_answer.strip().lower()
                is_correct = (user_clean == target_clean)

            if is_correct:
                correct_count += 1

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
            self.db.add(db_resp)

            detailed_results.append({
                "quiz_question_id": gq.id,
                "question_text": gq.question,
                "selected_answer": resp.selected_answer,
                "correct_answer": gq.correct_answer,
                "is_correct": is_correct,
                "explanation": gq.explanation,
                "source_page": gq.page,
            })

        accuracy = round((correct_count / max(1, total_count)) * 100, 2)
        attempt.status = "completed"
        attempt.score = float(correct_count)
        attempt.total = total_count
        attempt.accuracy = accuracy
        attempt.time_taken_seconds = req.time_taken_seconds
        attempt.submitted_at = datetime.now(timezone.utc)
        self.db.commit()

        weak_topics = [
            {"topic": t, "accuracy": round((v["correct"] / v["total"]) * 100, 1)}
            for t, v in topic_scores.items()
            if (v["correct"] / v["total"]) < 0.6
        ]

        return {
            "attempt_id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "score": correct_count,
            "total": total_count,
            "accuracy": accuracy,
            "time_taken_seconds": req.time_taken_seconds,
            "questions": detailed_results,
            "weak_topics": weak_topics,
        }

    def get_attempt_review(self, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Dict[str, Any]:
        attempt = self.db.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user_id)
        ).scalar_one_or_none()
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found.")

        responses = self.db.execute(
            select(QuizResponse, QuizQuestion, GeneratedQuestion)
            .join(QuizQuestion, QuizResponse.quiz_question_id == QuizQuestion.id)
            .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
            .where(QuizResponse.attempt_id == attempt_id)
            .order_by(QuizQuestion.position.asc())
        ).all()

        questions_detail = []
        topic_scores = {}
        for qr, qq, gq in responses:
            topic = gq.topic or "General"
            if topic not in topic_scores:
                topic_scores[topic] = {"correct": 0, "total": 0}
            topic_scores[topic]["total"] += 1
            if qr.is_correct:
                topic_scores[topic]["correct"] += 1

            questions_detail.append({
                "quiz_question_id": gq.id,
                "question_text": gq.question,
                "selected_answer": qr.selected_answer,
                "correct_answer": gq.correct_answer,
                "is_correct": qr.is_correct,
                "explanation": gq.explanation,
                "source_page": gq.page,
            })

        weak_topics = [
            {"topic": t, "accuracy": round((v["correct"] / v["total"]) * 100, 1)}
            for t, v in topic_scores.items()
            if (v["correct"] / v["total"]) < 0.6
        ]

        return {
            "attempt_id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "score": int(attempt.score),
            "total": attempt.total,
            "accuracy": attempt.accuracy,
            "time_taken_seconds": attempt.time_taken_seconds,
            "questions": questions_detail,
            "weak_topics": weak_topics,
        }
