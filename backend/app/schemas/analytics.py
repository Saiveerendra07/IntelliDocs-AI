from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TopicPerformanceItem(BaseModel):
    topic: str
    accuracy: float
    attempts: int


class AnalyticsOverview(BaseModel):
    documents_count: int = 0
    total_pages: int = 0
    questions_asked: int = 0
    quizzes_completed: int = 0
    average_score: float = 0.0
    topics_count: int = 0
    topics_mastered_percent: float = 0.0
    flashcards_count: int = 0
    flashcards_reviewed: int = 0
    study_streak_days: int = 1
    topic_performance: List[TopicPerformanceItem] = []


class ScoreTrendPoint(BaseModel):
    date: str
    score: float


class WeakTopicItem(BaseModel):
    topic: str
    attempts: int
    accuracy: float


class ActivityItem(BaseModel):
    type: str
    message: str
    created_at: str
    ref_id: Optional[str] = None
