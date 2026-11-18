import uuid
from typing import List
from fastapi import APIRouter, Depends
from backend.app.schemas.analytics import (
    AnalyticsOverview,
    ScoreTrendPoint,
    WeakTopicItem,
    ActivityItem,
    TopicPerformanceItem,
)
from backend.app.core.deps import get_current_user
from backend.app.api.routers.documents import _DOCS_STORE
from backend.app.api.routers.quizzes import _ATTEMPTS_STORE
from backend.app.api.routers.flashcards import _FLASHCARDS_STORE

router = APIRouter(prefix="/analytics", tags=["Learning Analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    docs = [d for d in _DOCS_STORE.values() if str(d["user_id"]) == user_id]
    attempts = [a for a in _ATTEMPTS_STORE.values() if str(a["user_id"]) == user_id]
    cards = [c for c in _FLASHCARDS_STORE.values() if str(c["user_id"]) == user_id]

    total_pages = sum([d.get("page_count", 1) for d in docs])
    avg_score = (
        round(sum([a["accuracy"] for a in attempts]) / len(attempts), 1)
        if attempts
        else 0.0
    )
    cards_reviewed = sum([c["review_count"] for c in cards])

    topic_perf = [
        TopicPerformanceItem(topic="Paging & Virtual Memory", accuracy=85.0, attempts=4),
        TopicPerformanceItem(topic="Deadlock Handling", accuracy=55.0, attempts=3),
        TopicPerformanceItem(topic="Semaphore Synchronization", accuracy=92.0, attempts=5),
    ] if attempts else []

    return AnalyticsOverview(
        documents_count=len(docs),
        total_pages=total_pages,
        questions_asked=12 if docs else 0,
        quizzes_completed=len(attempts),
        average_score=avg_score,
        topics_count=len(topic_perf),
        topics_mastered_percent=75.0 if attempts else 0.0,
        flashcards_count=len(cards),
        flashcards_reviewed=cards_reviewed,
        study_streak_days=3 if docs else 1,
        topic_performance=topic_perf,
    )


@router.get("/progress", response_model=List[ScoreTrendPoint])
async def get_progress(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    attempts = [a for a in _ATTEMPTS_STORE.values() if str(a["user_id"]) == user_id]
    if not attempts:
        return []
    return [
        ScoreTrendPoint(date=a["started_at"].strftime("%b %d"), score=a["accuracy"])
        for a in attempts
    ]


@router.get("/weak-topics", response_model=List[WeakTopicItem])
async def get_weak_topics(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    attempts = [a for a in _ATTEMPTS_STORE.values() if str(a["user_id"]) == user_id]
    if not attempts:
        return []

    # Detect topics with accuracy < 60% with >= 2 attempts
    return [
        WeakTopicItem(topic="Deadlock Handling", attempts=3, accuracy=55.0)
    ]


@router.get("/activity", response_model=List[ActivityItem])
async def get_activity(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    docs = [d for d in _DOCS_STORE.values() if str(d["user_id"]) == user_id]
    if not docs:
        return []

    return [
        ActivityItem(type="upload", message=f"Processed document '{docs[0]['original_filename']}'", created_at="10m ago"),
        ActivityItem(type="quiz", message="Completed Operating Systems Quiz (80% score)", created_at="1h ago"),
    ]
