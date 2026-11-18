import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models.user import User
from backend.app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()
