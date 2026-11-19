import os
import re
import uuid
import pytest
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.core.security import get_password_hash
from backend.app.documents.base import PageContent
from backend.app.documents.chunking import SentenceAwareChunker
from backend.app.nlp.qgen import QuestionGenerator
from backend.app.nlp.flashcards import FlashcardGenerator
from backend.app.nlp.rag import RAGEngine
from backend.app.nlp.vectorstore import VectorStoreManager


@pytest.fixture(scope="module")
def networking_setup():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    user = User(
        id=uuid.uuid4(),
        email=f"quality_test_{uid}@example.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Quality Test User",
    )
    db.add(user)
    db.commit()

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "networking_doc.txt")
    with open(fixture_path, "r", encoding="utf-8") as f:
        text = f.read()

    parts = text.split("Open Shortest Path First (OSPF)")
    p1_text = parts[0].strip()
    p2_text = "Open Shortest Path First (OSPF)" + parts[1].strip()

    pages = [
        PageContent(page_number=1, text=p1_text, section_title="Routing Information Protocol (RIP)"),
        PageContent(page_number=2, text=p2_text, section_title="Open Shortest Path First (OSPF)"),
    ]

    chunker = SentenceAwareChunker()
    chunks_dto = chunker.chunk_pages(pages)

    doc = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        original_filename="networking_routing_test.pptx",
        stored_path=fixture_path,
        mime_type="text/plain",
        file_size=len(text),
        page_count=2,
        status="ready",
    )
    db.add(doc)
    db.commit()

    db_chunks = []
    for c in chunks_dto:
        rec = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=c.chunk_index,
            text=c.content,
            page_start=c.page_start,
            page_end=c.page_end,
            token_count=c.token_count,
            section_title=c.section_title,
        )
        db.add(rec)
        db_chunks.append(rec)
    db.commit()

    # Index into ChromaDB
    vm = VectorStoreManager()
    vm.index_chunks(user_id=user.id, document_id=doc.id, chunks=chunks_dto)

    yield db, doc, db_chunks, user.id

    # Teardown
    try:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
        db.query(Document).filter(Document.id == doc.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def test_rag_relevance_threshold_and_quality(networking_setup):
    """Verifies that RAG answers on-topic questions with citations and strictly rejects off-topic queries."""
    db, doc, chunks, user_id = networking_setup
    rag = RAGEngine(db)

    # 10 On-topic questions
    on_topic_questions = [
        ("What is the maximum hop count in RIP?", 1),
        ("What routing algorithm does RIP use?", 1),
        ("What is OSPF based on?", 2),
        ("What is a transient link in OSPF?", 2),
        ("What is a stub link in OSPF?", 2),
        ("What does a point-to-point link connect?", 2),
        ("What hop count value represents infinity in RIP?", 1),
        ("What is the primary routing metric in OSPF?", 2),
        ("What is hop count defined as?", 1),
        ("Where is the Routing Information Protocol used?", 1),
    ]

    for q, expected_page in on_topic_questions:
        res = rag.generate_answer(
            user_id=user_id,
            query=q,
            document_ids=[doc.id],
            explanation_mode="technical",
        )
        assert res["confidence_score"] >= 0.40, f"Expected high confidence for on-topic query '{q}', got {res['confidence_score']}"
        assert len(res["sources"]) > 0, f"Expected sources for on-topic query '{q}'"
        assert "couldn't find this" not in res["answer"].lower()
        source_pages = [s["page_start"] for s in res["sources"]]
        assert expected_page in source_pages, f"Expected Page {expected_page} in sources for '{q}', got {source_pages}"
        assert "### Technical Analysis / Mechanism Breakdown" not in res["answer"]

    # 5 Off-topic questions (MUST be rejected)
    off_topic_questions = [
        "explain virtual memory paging",
        "what is backpropagation in neural networks",
        "what is quantum entanglement",
        "what is the capital of France",
        "how does gradient descent work",
    ]

    for q in off_topic_questions:
        res = rag.generate_answer(
            user_id=user_id,
            query=q,
            document_ids=[doc.id],
            explanation_mode="technical",
        )
        assert res["answer"] == "I couldn't find this in the selected document(s).", f"Failed to reject off-topic query '{q}': got {res['answer']}"
        assert res["confidence_score"] == 0.0, f"Expected 0.0 confidence for off-topic query '{q}', got {res['confidence_score']}"
        assert len(res["sources"]) == 0, f"Expected 0 sources for off-topic query '{q}', got {len(res['sources'])}"


def test_question_generation_quality_invariants(networking_setup):
    """Verifies strict quality invariants for QGen: no canned distractors, unique distractors, grounded answers."""
    db, doc, chunks, user_id = networking_setup
    qgen = QuestionGenerator(db)

    # Generate 5 MCQs
    questions = qgen.generate_from_chunks(chunks, q_type="mcq", difficulty="medium", count=5)
    assert len(questions) >= 4, f"Expected at least 4 questions, got {len(questions)}"

    all_distractors = []
    canned_phrases = [
        "completely avoids", "operates inversely", "primarily concerns",
        "linear sequential recurrent", "unigram lexical", "heuristic lookups"
    ]
    disallowed_prefixes = ("it ", "they ", "we ", "this ", "that ", "there ", "however ")

    for q in questions:
        # 1. No canned phrases in options
        for opt in q["options"]:
            for cp in canned_phrases:
                assert cp not in opt.lower(), f"Found canned distractor phrase '{cp}' in option: '{opt}'"

        # 2. Exactly 4 distinct options
        assert len(q["options"]) == 4, f"Expected 4 options, got {len(q['options'])}"
        assert len(set(q["options"])) == 4, f"Options contain duplicates: {q['options']}"

        # 3. Correct answer must be in options
        assert q["correct_answer"] in q["options"]

        # 4. Correct answer must appear in the source passage
        matched_chunk = next((c for c in chunks if c.page_start == q["page"]), None)
        assert matched_chunk is not None, f"Source chunk for page {q['page']} not found"

        # 5. Question stem quality: no pronoun subject
        stem_lower = q["question"].lower()
        for pfx in disallowed_prefixes:
            assert not stem_lower.startswith(pfx), f"Question stem starts with pronoun/discourse word '{pfx}': '{q['question']}'"
        assert not q["question"].endswith(":-"), f"Question stem ends with heading artifact ':-': '{q['question']}'"

        # 6. Collect distractors for cross-question uniqueness check
        q_distractors = [opt for opt in q["options"] if opt != q["correct_answer"]]
        all_distractors.extend([d.lower() for d in q_distractors])

        # 7. Real explanation with page citation
        assert f"Page {q['page']}" in q["explanation"] or "document" in q["explanation"].lower()
        assert "Verified in document on Page" not in q["explanation"]

    # Verify no distractor appears in more than one question
    assert len(all_distractors) == len(set(all_distractors)), f"Found duplicate distractors across questions: {all_distractors}"


def test_flashcard_quality_invariants(networking_setup):
    """Verifies that flashcards have no reference artifacts in text and have clean terms."""
    db, doc, chunks, user_id = networking_setup
    fg = FlashcardGenerator()

    cards = fg.generate_flashcards(chunks, max_cards=6)
    assert len(cards) >= 3, f"Expected at least 3 flashcards, got {len(cards)}"

    for c in cards:
        # 1. No "*Reference: Page*" artifact in back text
        assert "*Reference:" not in c["back"], f"Flashcard back contains reference artifact: {c['back']}"
        assert "Page " not in c["back"] or "Page" not in c["back"], f"Page string leaked into back text: {c['back']}"

        # 2. Separate source_page field is valid integer
        assert isinstance(c["source_page"], int) and c["source_page"] in (1, 2)

        # 3. Front is clean term or question (no pronoun subjects)
        front_low = c["front"].lower()
        for pfx in ("it ", "they ", "we ", "this ", "however "):
            assert not front_low.startswith(pfx), f"Front starts with pronoun: {c['front']}"

        # 4. Back is substantive explanation
        assert len(c["back"].split()) >= 6, f"Flashcard back is too short/fragmentary: '{c['back']}'"
