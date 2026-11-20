import uuid
import pytest
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.core.security import get_password_hash
from backend.app.nlp.qgen import QuestionGenerator


@pytest.fixture(scope="module")
def sample_networking_chunks():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"qgen_qual_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="QGen Quality User",
    )
    db.add(user)
    db.commit()

    doc = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        original_filename="RIP_OSPF.pptx",
        stored_path="backend/storage/uploads/RIP_OSPF.pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size=8192,
        status="ready",
        page_count=2,
    )
    db.add(doc)

    c1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        text=(
            "Routing Information Protocol (RIP) is an intradomain routing protocol based on distance vector routing. "
            "In RIP, the routing metric used is hop count, which measures the number of links traversed to reach a destination. "
            "The maximum hop count allowed in RIP is 15. A hop count of 16 is defined as infinity, meaning the destination network is unreachable."
        ),
        token_count=65,
        page_start=1,
        page_end=1,
        section_title="Routing Information Protocol",
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=1,
        text=(
            "Open Shortest Path First (OSPF) is an intradomain routing protocol based on link state routing. "
            "In OSPF, a transient link is a network with several routers attached where data can enter through one router and leave through another. "
            "A stub link is a network connected to only one single router, so data packets can only enter or leave through that router."
        ),
        token_count=70,
        page_start=2,
        page_end=2,
        section_title="Open Shortest Path First",
    )
    db.add_all([c1, c2])
    db.commit()

    yield db, [c1, c2]

    try:
        db.delete(doc)
        db.delete(user)
        db.commit()
    except Exception:
        pass
    db.close()


def test_qgen_question_stem_cleanliness(sample_networking_chunks):
    db, chunks = sample_networking_chunks
    qgen = QuestionGenerator(db)

    # 1. Test MCQ stems
    mcqs = qgen.generate_from_chunks(chunks, q_type="mcq", difficulty="medium", count=4)
    assert len(mcqs) >= 2

    forbidden_stem_patterns = [
        "rip_ospf", "ch2.pdf", "ch4.pdf", ".pptx", ".pdf",
        "in introduction, complete the following",
        "complete the following: \"___ and foundational principles"
    ]

    for q in mcqs:
        stem = q["question"]
        stem_lower = stem.lower()
        words = stem.split()

        # Word count >= 6
        assert len(words) >= 6, f"Stem too short (<6 words): '{stem}'"

        # No forbidden patterns
        for pat in forbidden_stem_patterns:
            assert pat not in stem_lower, f"Stem contains forbidden artifact '{pat}': '{stem}'"

        # No pronoun starts
        for pronoun in ("it ", "they ", "we ", "this "):
            assert not stem_lower.startswith(pronoun), f"Stem starts with pronoun '{pronoun}': '{stem}'"

        # Correct answer must not be trivially included in stem
        assert q["correct_answer"].lower() not in stem_lower, f"Answer '{q['correct_answer']}' leaked into stem: '{stem}'"

        # Options must be 4 distinct choices
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4

        # Distractors must NOT contain cross-domain SQL terms
        for opt in q["options"]:
            assert "create trigger" not in opt.lower(), f"Cross-domain SQL distractor found in networking quiz: '{opt}'"
            assert "outer join" not in opt.lower(), f"Cross-domain SQL distractor found in networking quiz: '{opt}'"


def test_qgen_true_false_format(sample_networking_chunks):
    db, chunks = sample_networking_chunks
    qgen = QuestionGenerator(db)

    tf_questions = qgen.generate_from_chunks(chunks, q_type="true_false", difficulty="medium", count=3)
    assert len(tf_questions) >= 1

    for q in tf_questions:
        assert q["type"] == "true_false"
        assert q["options"] == ["True", "False"], f"True/False must have exactly ['True', 'False'], got {q['options']}"
        assert q["correct_answer"] in ["True", "False"]
        assert len(q["question"].split()) >= 6
        assert "True or False:" in q["question"]


def test_qgen_fill_in_the_blank_format(sample_networking_chunks):
    db, chunks = sample_networking_chunks
    qgen = QuestionGenerator(db)

    fib_questions = qgen.generate_from_chunks(chunks, q_type="fill_blank", difficulty="medium", count=3)
    assert len(fib_questions) >= 1

    for q in fib_questions:
        assert q["type"] == "fill_blank"
        assert q["options"] == [], f"Fill-in-the-blank must not have options, got {q['options']}"
        assert "___" in q["question"], f"Fill-in-the-blank question must have blank placeholder '___': '{q['question']}'"
        assert len(q["correct_answer"].strip()) > 0
        assert len(q["question"].split()) >= 6


def test_qgen_short_answer_format(sample_networking_chunks):
    db, chunks = sample_networking_chunks
    qgen = QuestionGenerator(db)

    sa_questions = qgen.generate_from_chunks(chunks, q_type="short_answer", difficulty="medium", count=3)
    assert len(sa_questions) >= 1

    for q in sa_questions:
        assert q["type"] == "short_answer"
        assert q["options"] == []
        assert len(q["correct_answer"].split()) >= 4
        assert len(q["question"].split()) >= 6
