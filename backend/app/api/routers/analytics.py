import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.services.analytics_service import AnalyticsService
from backend.app.schemas.analytics import (
    AnalyticsOverview,
    ScoreTrendPoint,
    WeakTopicItem,
    ActivityItem,
)

router = APIRouter(prefix="/analytics", tags=["Learning Analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def get_overview(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = AnalyticsService(db)
    return service.get_overview(user_id)


@router.get("/progress", response_model=List[ScoreTrendPoint])
@router.get("/trends", response_model=List[ScoreTrendPoint])
def get_progress_trends(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = AnalyticsService(db)
    return service.get_score_trends(user_id)


@router.get("/weak-topics", response_model=List[WeakTopicItem])
def get_weak_topics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = AnalyticsService(db)
    return service.get_weak_topics(user_id)


@router.get("/activity", response_model=List[ActivityItem])
def get_activity(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(current_user["id"]))
    service = AnalyticsService(db)
    return service.get_recent_activities(user_id)
