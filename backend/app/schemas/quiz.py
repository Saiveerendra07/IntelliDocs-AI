import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class QuestionGenerateRequest(BaseModel):
    document_id: uuid.UUID
    type: str = "mcq"         # mcq, true_false, fill_blank, short_answer, etc.
    difficulty: str = "medium" # easy, medium, hard
    count: int = 5
    topic: Optional[str] = None


class GeneratedQuestionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    type: str
    difficulty: str
    topic: Optional[str] = None
    question: str
    options: Optional[List[str]] = []
    correct_answer: str
    explanation: Optional[str] = None
    page: Optional[int] = None
    quality_score: float = 1.0

    class Config:
        from_attributes = True


class QuizCreateRequest(BaseModel):
    document_id: uuid.UUID
    title: str
    question_ids: List[uuid.UUID]
    time_limit_seconds: int = 600


class QuizQuestionOut(BaseModel):
    id: uuid.UUID
    position: int
    question: str
    options: Optional[List[str]] = []
    type: str
    difficulty: str

    class Config:
        from_attributes = True


class QuizOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    time_limit_seconds: int
    questions: List[QuizQuestionOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class QuizAttemptStartResponse(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    started_at: datetime


class QuizResponseInput(BaseModel):
    quiz_question_id: uuid.UUID
    selected_answer: Optional[str] = None
    marked_for_review: bool = False


class QuizSubmitRequest(BaseModel):
    responses: List[QuizResponseInput]
    time_taken_seconds: int


class RecommendationItem(BaseModel):
    topic: str
    accuracy: float


class QuizQuestionResult(BaseModel):
    quiz_question_id: uuid.UUID
    question_text: str
    selected_answer: Optional[str] = None
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None
    source_page: Optional[int] = None


class QuizResultResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    score: int
    total: int
    accuracy: float
    time_taken_seconds: int
    recommendations: List[RecommendationItem] = []
    responses: List[QuizQuestionResult] = []
