import os
import socket
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base


def is_postgres_available(host: str = "localhost", port: int = 5432, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


db_url = settings.DATABASE_URL
if db_url.startswith("postgresql"):
    if not is_postgres_available():
        os.makedirs(settings.STORAGE_DIR, exist_ok=True)
        sqlite_path = os.path.abspath(os.path.join(settings.STORAGE_DIR, "intellidocs.db"))
        db_url = f"sqlite:///{sqlite_path}"
        logger.info(f"PostgreSQL not reachable. Zero-config fallback to SQLite: {db_url}")

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

if db_url.startswith("sqlite"):
    import backend.app.db.models.user
    import backend.app.db.models.document
    import backend.app.db.models.nlp
    import backend.app.db.models.chat
    import backend.app.db.models.quiz
    import backend.app.db.models.flashcard
    import backend.app.db.models.learning
    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
