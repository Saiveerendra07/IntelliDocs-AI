import uuid
import os
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.app.db.base import Base
from backend.app.db.models import (
    User,
    Document,
    DocumentPage,
    DocumentChunk,
    Summary,
    GeneratedQuestion,
    Quiz,
    QuizQuestion,
    Flashcard,
    LearningProgress,
    ActivityLog,
)
from backend.app.repositories.consistency import check_document_consistency, purge_document_cascade


@pytest.fixture
def db_session():
    # In-memory SQLite with foreign keys enabled
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Enable foreign keys in SQLite
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_schema_creation_and_insertion(db_session):
    user = User(
        email="student@univ.edu",
        hashed_password="hashed_pw_test",
        full_name="Student Test",
        theme="light",
        preferences={"default_provider": "local"},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "student@univ.edu"

    # Insert Document
    doc = Document(
        user_id=user.id,
        original_filename="test_os.pdf",
        stored_path="backend/storage/uploads/test_os.pdf",
        mime_type="application/pdf",
        file_size=1024,
        page_count=2,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert doc.id is not None
    assert doc.user_id == user.id

    # Insert Pages and Chunks
    page = DocumentPage(document_id=doc.id, page_number=1, text="Operating Systems Page 1")
    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        text="Virtual memory allows executing processes that are not completely in memory.",
        page_start=1,
        page_end=1,
        token_count=12,
        chroma_id="chroma_uuid_1",
    )
    db_session.add_all([page, chunk])
    db_session.commit()

    # Query back
    queried_pages = db_session.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id)).scalars().all()
    assert len(queried_pages) == 1
    assert queried_pages[0].text == "Operating Systems Page 1"


def test_document_deletion_cascades(db_session):
    """
    Verifies that deleting a document automatically cascades and deletes:
    - document_pages
    - document_chunks
    - summaries
    - generated_questions
    - quizzes
    - flashcards
    """
    user = User(
        email="cascade_tester@univ.edu",
        hashed_password="pw",
        full_name="Cascade Tester",
    )
    db_session.add(user)
    db_session.commit()

    doc = Document(
        user_id=user.id,
        original_filename="cascade_doc.pdf",
        stored_path="test_path.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    page = DocumentPage(document_id=doc.id, page_number=1, text="Page content")
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, text="Chunk content", page_start=1, page_end=1, token_count=2)
    summary = Summary(document_id=doc.id, method="textrank", length="medium", content="Summary content", key_points=[], definitions=[])
    gq = GeneratedQuestion(
        user_id=user.id,
        document_id=doc.id,
        type="mcq",
        difficulty="easy",
        question="What is X?",
        correct_answer="X is Y",
    )
    quiz = Quiz(user_id=user.id, document_id=doc.id, title="Test Quiz", time_limit_seconds=300)
    card = Flashcard(user_id=user.id, document_id=doc.id, front="Concept", back="Definition")

    db_session.add_all([page, chunk, summary, gq, quiz, card])
    db_session.commit()

    # Verify all records exist before delete
    assert db_session.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id)).scalar_one_or_none() is not None
    assert db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).scalar_one_or_none() is not None
    assert db_session.execute(select(Summary).where(Summary.document_id == doc.id)).scalar_one_or_none() is not None
    assert db_session.execute(select(GeneratedQuestion).where(GeneratedQuestion.document_id == doc.id)).scalar_one_or_none() is not None
    assert db_session.execute(select(Quiz).where(Quiz.document_id == doc.id)).scalar_one_or_none() is not None
    assert db_session.execute(select(Flashcard).where(Flashcard.document_id == doc.id)).scalar_one_or_none() is not None

    # Delete Document
    db_session.delete(doc)
    db_session.commit()

    # Verify all dependent records are deleted by cascade
    assert db_session.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id)).scalar_one_or_none() is None
    assert db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).scalar_one_or_none() is None
    assert db_session.execute(select(Summary).where(Summary.document_id == doc.id)).scalar_one_or_none() is None
    assert db_session.execute(select(GeneratedQuestion).where(GeneratedQuestion.document_id == doc.id)).scalar_one_or_none() is None
    assert db_session.execute(select(Quiz).where(Quiz.document_id == doc.id)).scalar_one_or_none() is None
    assert db_session.execute(select(Flashcard).where(Flashcard.document_id == doc.id)).scalar_one_or_none() is None


def test_consistency_check_and_purge(db_session, tmp_path):
    user = User(email="consistency@univ.edu", hashed_password="pw", full_name="Consistency User")
    db_session.add(user)
    db_session.commit()

    test_file = tmp_path / "consistency_test.pdf"
    test_file.write_text("sample content")

    doc = Document(
        user_id=user.id,
        original_filename="consistency_test.pdf",
        stored_path=str(test_file),
        mime_type="application/pdf",
        file_size=len("sample content"),
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    page = DocumentPage(document_id=doc.id, page_number=1, text="Page 1")
    db_session.add(page)
    db_session.commit()

    # Check consistency
    report = check_document_consistency(db_session, doc.id)
    assert report["exists"] is True
    assert report["consistent"] is True
    assert report["file_exists"] is True
    assert report["pages_count"] == 1

    # Purge document cascade
    purged = purge_document_cascade(db_session, doc.id)
    assert purged is True
    assert not os.path.exists(str(test_file))
    assert db_session.execute(select(Document).where(Document.id == doc.id)).scalar_one_or_none() is None
