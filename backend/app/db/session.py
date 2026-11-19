import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base


def _initialize_engine():
    db_url = settings.DATABASE_URL
    engine = None

    if db_url.startswith("postgresql"):
        try:
            temp_engine = create_engine(
                db_url,
                connect_args={"connect_timeout": 2},
                pool_pre_ping=True,
                echo=False,
            )
            with temp_engine.connect() as conn:
                pass
            engine = temp_engine
            logger.info("Connected successfully to PostgreSQL database.")
        except Exception as e:
            logger.warning(
                f"PostgreSQL connection/auth failed ({e}). Falling back to local zero-config SQLite."
            )
            os.makedirs(settings.STORAGE_DIR, exist_ok=True)
            sqlite_path = os.path.abspath(os.path.join(settings.STORAGE_DIR, "intellidocs.db"))
            db_url = f"sqlite:///{sqlite_path}"

    if engine is None:
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
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

    return engine


engine = _initialize_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
