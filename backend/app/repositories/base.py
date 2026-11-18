import uuid
from typing import Any, Generic, List, Optional, Type, TypeVar
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from backend.app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: uuid.UUID) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user(self, id: uuid.UUID, user_id: uuid.UUID) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id, self.model.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_user(self, user_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model).where(self.model.user_id == user_id).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, **kwargs) -> ModelType:
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.commit()
