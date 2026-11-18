from fastapi import APIRouter
from backend.app.api.routers import (
    auth,
    users,
    documents,
    nlp,
    summaries,
    search,
    chat,
    quizzes,
    flashcards,
    analytics,
    system,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(nlp.router)
api_router.include_router(summaries.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(quizzes.router)
api_router.include_router(flashcards.router)
api_router.include_router(analytics.router)
api_router.include_router(system.router)
