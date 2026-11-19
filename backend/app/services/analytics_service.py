import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from backend.app.db.models.document import Document
from backend.app.db.models.chat import ChatMessage, Conversation
from backend.app.db.models.quiz import QuizAttempt, QuizResponse, QuizQuestion, GeneratedQuestion
from backend.app.db.models.flashcard import Flashcard
from backend.app.db.models.learning import ActivityLog, LearningProgress
from backend.app.schemas.analytics import (
    AnalyticsOverview,
    TopicPerformanceItem,
    ScoreTrendPoint,
    WeakTopicItem,
    ActivityItem,
)


class AnalyticsService:
    """
    Analytics & Learning Telemetry Service:
    - Pure computation strictly from database entities.
    - Zero fake or hardcoded metrics.
    - Strict multi-tenant isolation by user_id.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_overview(self, user_id: uuid.UUID) -> AnalyticsOverview:
        # 1. Documents & Page Count
        docs = self.db.execute(
            select(Document).where(Document.user_id == user_id)
        ).scalars().all()
        doc_count = len(docs)
        total_pages = sum([d.page_count or 1 for d in docs])

        # 2. Questions Asked (user chat messages)
        questions_asked = self.db.execute(
            select(func.count(ChatMessage.id))
            .join(Conversation, ChatMessage.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id, ChatMessage.role == "user")
        ).scalar() or 0

        # 3. Quizzes & Accuracy
        attempts = self.db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.status == "completed")
            .order_by(QuizAttempt.submitted_at.asc())
        ).scalars().all()

        quizzes_completed = len(attempts)
        avg_score = round(sum([a.accuracy for a in attempts]) / len(attempts), 1) if attempts else 0.0

        # 4. Topic-Level Performance Breakdown
        # Query all responses for completed attempts
        responses = self.db.execute(
            select(QuizResponse.is_correct, GeneratedQuestion.topic)
            .join(QuizAttempt, QuizResponse.attempt_id == QuizAttempt.id)
            .join(QuizQuestion, QuizResponse.quiz_question_id == QuizQuestion.id)
            .join(GeneratedQuestion, QuizQuestion.generated_question_id == GeneratedQuestion.id)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.status == "completed")
        ).all()

        topic_stats = defaultdict(lambda: {"total": 0, "correct": 0})
        for is_corr, topic in responses:
            t_name = topic or "General Concepts"
            topic_stats[t_name]["total"] += 1
            if is_corr:
                topic_stats[t_name]["correct"] += 1

        topic_perf_list = []
        mastered_count = 0
        for t_name, stats in topic_stats.items():
            acc = round((stats["correct"] / max(1, stats["total"])) * 100, 1)
            topic_perf_list.append(TopicPerformanceItem(
                topic=t_name,
                accuracy=acc,
                attempts=stats["total"],
            ))
            if acc >= 80.0:
                mastered_count += 1

        topic_count = len(topic_perf_list)
        topics_mastered_pct = (
            round((mastered_count / max(1, topic_count)) * 100, 1) if topic_count > 0 else 0.0
        )

        # 5. Flashcards
        cards = self.db.execute(
            select(Flashcard).where(Flashcard.user_id == user_id)
        ).scalars().all()
        flashcards_count = len(cards)
        flashcards_reviewed = sum([c.review_count for c in cards])

        # 6. Study Streak Calculation
        activity_dates = set()
        for a in attempts:
            if a.submitted_at:
                activity_dates.add(a.submitted_at.date())

        logs = self.db.execute(
            select(ActivityLog.created_at).where(ActivityLog.user_id == user_id)
        ).scalars().all()
        for l in logs:
            if l:
                activity_dates.add(l.date())

        # If user has any document or activity, baseline streak is at least 1
        streak = 1 if (activity_dates or doc_count > 0) else 0
        if activity_dates:
            sorted_dates = sorted(list(activity_dates), reverse=True)
            today = datetime.now(timezone.utc).date()
            if sorted_dates[0] in (today, today - timedelta(days=1)):
                current_streak = 1
                curr = sorted_dates[0]
                for prev in sorted_dates[1:]:
                    if curr - prev == timedelta(days=1):
                        current_streak += 1
                        curr = prev
                    else:
                        break
                streak = max(streak, current_streak)

        return AnalyticsOverview(
            documents_count=doc_count,
            total_pages=total_pages,
            questions_asked=questions_asked,
            quizzes_completed=quizzes_completed,
            average_score=avg_score,
            topics_count=topic_count,
            topics_mastered_percent=topics_mastered_pct,
            flashcards_count=flashcards_count,
            flashcards_reviewed=flashcards_reviewed,
            study_streak_days=streak,
            topic_performance=topic_perf_list,
        )

    def get_score_trends(self, user_id: uuid.UUID) -> List[ScoreTrendPoint]:
        attempts = self.db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.status == "completed")
            .order_by(QuizAttempt.submitted_at.asc())
        ).scalars().all()

        points = []
        for a in attempts:
            d_str = a.submitted_at.strftime("%b %d") if a.submitted_at else "Recent"
            points.append(ScoreTrendPoint(date=d_str, score=round(a.accuracy, 1)))
        return points

    def get_weak_topics(self, user_id: uuid.UUID) -> List[WeakTopicItem]:
        overview = self.get_overview(user_id)
        weak = [
            WeakTopicItem(topic=t.topic, attempts=t.attempts, accuracy=t.accuracy)
            for t in overview.topic_performance
            if t.accuracy < 60.0
        ]
        return weak

    def get_recent_activities(self, user_id: uuid.UUID, limit: int = 10) -> List[ActivityItem]:
        logs = self.db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
        ).scalars().all()

        out = []
        for l in logs:
            out.append(ActivityItem(
                type=l.type,
                message=l.metadata_json.get("message", f"Activity recorded: {l.type}"),
                created_at=l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ref_id=str(l.ref_id) if l.ref_id else None,
            ))
        return out
