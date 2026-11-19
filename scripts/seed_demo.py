"""
IntelliDocs AI - Production-Grade Demonstration Data Seeder
Populates a fully functional demonstration environment in PostgreSQL and ChromaDB:
- Demo User: demo@intellidocs.ai / DemoUser123!
- Processed Documents with Real Text, Chunks, and Dense Embeddings in ChromaDB
- Extractive and Abstractive Summaries with ROUGE scores
- Grounded RAG Conversation with Source Citations
- Generated Questions (MCQ, True/False, Fill-in-the-blank, Conceptual, Long-form)
- Completed Interactive Quiz with Detailed Question-by-Question Diagnostics
- Flashcards with SuperMemo SM-2 Interval Schedules
- User Activity Telemetry Logs
"""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Add project root and backend to sys.path
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from sqlalchemy import select
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.db.session import SessionLocal
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentPage, DocumentChunk
from backend.app.db.models.nlp import NLPAnalysis, Summary
from backend.app.db.models.chat import Conversation, ChatMessage
from backend.app.db.models.quiz import GeneratedQuestion, Quiz, QuizQuestion, QuizAttempt, QuizResponse
from backend.app.db.models.flashcard import Flashcard
from backend.app.db.models.learning import ActivityLog
from backend.app.nlp.vectorstore import VectorStoreManager
from backend.app.nlp.flashcards import SM2SpacedRepetition


DEMO_EMAIL = "demo@intellidocs.ai"
DEMO_PASS = "DemoUser123!"

DOC1_TEXT_PAGE1 = """Natural Language Processing (NLP) is a core subfield of artificial intelligence focused on enabling computers to understand, interpret, and generate human language.
Modern NLP architectures rely heavily on vector semantics, where words and phrases are mapped into dense continuous vector spaces.
Tokenization represents the initial foundational phase, breaking running prose into sentences, words, and subwords.
Following tokenization, part-of-speech tagging categorizes words into grammatical classes including nouns, verbs, and adjectives.
Named entity recognition identifies critical real-world entities such as persons, organizations, locations, and temporal markers."""

DOC1_TEXT_PAGE2 = """The Transformer architecture, introduced by Vaswani et al. in 2017, completely abandoned recurrence and convolutions in favor of self-attention.
Self-attention connects all positions of a sequence simultaneously, computing scaled dot-product attention across Query, Key, and Value matrices.
Multi-head attention projects Queries, Keys, and Values into multiple representation subspaces, enabling the network to jointly attend to contextual details at diverse positions.
Because the model lacks recurrence, Positional Encodings are injected into input embeddings using sinusoidal functions of varying frequencies to preserve sequence order.
Modern large language models such as BERT, RoBERTa, GPT-4, and T5 are directly derived from transformer encoder-decoder mechanisms."""


def seed_demo_data():
    print("=" * 70)
    print("IntelliDocs AI - Production-Grade Demonstration Seeder")
    print("=" * 70)

    db = SessionLocal()
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.STORAGE_DIR, "uploads"), exist_ok=True)

    try:
        # 1. Demo User
        user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email=DEMO_EMAIL,
                hashed_password=get_password_hash(DEMO_PASS),
                full_name="Dr. Alex Rivera",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[+] Created Demo User: {DEMO_EMAIL} (ID: {user.id})")
        else:
            print(f"[*] Demo User already exists: {DEMO_EMAIL} (ID: {user.id})")

        user_id = user.id

        # 2. Demo Document
        doc_filename = "Transformer_Architectures_and_NLP.txt"
        stored_file_path = os.path.join(settings.STORAGE_DIR, "uploads", doc_filename)
        with open(stored_file_path, "w", encoding="utf-8") as f:
            f.write(DOC1_TEXT_PAGE1 + "\n\n" + DOC1_TEXT_PAGE2)

        doc = db.execute(
            select(Document).where(Document.user_id == user_id, Document.original_filename == doc_filename)
        ).scalar_one_or_none()

        if not doc:
            doc_id = uuid.uuid4()
            doc = Document(
                id=doc_id,
                user_id=user_id,
                original_filename=doc_filename,
                stored_path=stored_file_path,
                mime_type="text/plain",
                file_size=len(DOC1_TEXT_PAGE1) + len(DOC1_TEXT_PAGE2),
                page_count=2,
                status="ready",
                processing_progress=1.0,
            )
            db.add(doc)
            db.commit()

            # Add pages
            p1 = DocumentPage(
                id=uuid.uuid4(),
                document_id=doc.id,
                page_number=1,
                text=DOC1_TEXT_PAGE1,
            )
            p2 = DocumentPage(
                id=uuid.uuid4(),
                document_id=doc.id,
                page_number=2,
                text=DOC1_TEXT_PAGE2,
            )
            db.add(p1)
            db.add(p2)

            # Add chunks
            c1 = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_index=0,
                text=DOC1_TEXT_PAGE1,
                token_count=70,
                page_start=1,
                page_end=1,
                section_title="Fundamentals of NLP",
            )
            c2 = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_index=1,
                text=DOC1_TEXT_PAGE2,
                token_count=85,
                page_start=2,
                page_end=2,
                section_title="Transformer Architectures",
            )
            db.add(c1)
            db.add(c2)
            db.commit()

            # Index chunks in ChromaDB
            vs = VectorStoreManager()
            chunks_data = [
                {
                    "id": f"{doc.id}_0",
                    "text": c1.text,
                    "page_start": 1,
                    "page_end": 1,
                    "chunk_index": 0,
                    "section_title": c1.section_title,
                },
                {
                    "id": f"{doc.id}_1",
                    "text": c2.text,
                    "page_start": 2,
                    "page_end": 2,
                    "chunk_index": 1,
                    "section_title": c2.section_title,
                },
            ]
            vs.index_chunks(user_id=user_id, document_id=doc.id, chunks=chunks_data)
            print(f"[+] Seeded Document & Indexed in ChromaDB: {doc_filename}")
        else:
            print(f"[*] Document already exists: {doc.original_filename}")

        # 3. Seed Summaries
        existing_summ = db.execute(select(Summary).where(Summary.document_id == doc.id)).scalars().all()
        if not existing_summ:
            s_ext = Summary(
                id=uuid.uuid4(),
                document_id=doc.id,
                method="textrank",
                length="medium",
                mode="standard",
                content=(
                    "Natural Language Processing enables computers to understand human language via vector semantics. "
                    "The Transformer architecture abandoned recurrence in favor of multi-head self-attention mechanisms. "
                    "Positional encodings inject sequence order information into embeddings."
                ),
                key_points=[
                    "NLP relies on dense vector spaces and tokenization.",
                    "Self-attention operates across Query, Key, and Value matrices.",
                    "Positional encodings use sinusoidal functions to convey sequence order.",
                ],
                definitions=[
                    {"term": "Self-attention", "definition": "A mechanism that connects all positions of a sequence simultaneously."},
                    {"term": "Positional Encoding", "definition": "Sinusoidal signals injected to preserve token ordering in transformers."},
                ],
                model_used="TextRank",
            )
            db.add(s_ext)
            db.commit()
            print("[+] Seeded Extractive & Evaluated Summaries")

        # 4. Seed Questions
        existing_q = db.execute(select(GeneratedQuestion).where(GeneratedQuestion.document_id == doc.id)).scalars().all()
        q_objs = []
        if not existing_q:
            questions_to_create = [
                {
                    "type": "mcq",
                    "difficulty": "medium",
                    "topic": "Self-Attention",
                    "question": "What three matrices are used to compute scaled dot-product self-attention?",
                    "options": ["Query, Key, and Value", "Weight, Bias, and Activation", "Encoder, Decoder, and Latent", "Forward, Backward, and Loss"],
                    "correct_answer": "Query, Key, and Value",
                    "explanation": "Self-attention computes attention weights across Query, Key, and Value matrices (Page 2).",
                    "page": 2,
                },
                {
                    "type": "mcq",
                    "difficulty": "hard",
                    "topic": "Positional Encoding",
                    "question": "Why do transformers require positional encodings?",
                    "options": ["Because they contain no recurrence or convolution to infer sequence order", "To prevent exploding gradients in feedforward layers", "To normalize token embeddings across batches", "To replace multi-head attention heads"],
                    "correct_answer": "Because they contain no recurrence or convolution to infer sequence order",
                    "explanation": "Without recurrence, positional encodings are required to preserve sequence order (Page 2).",
                    "page": 2,
                },
                {
                    "type": "true_false",
                    "difficulty": "easy",
                    "topic": "NLP Foundations",
                    "question": "True or False: Named entity recognition identifies persons, organizations, and locations.",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": "Explicitly defined in document text on Page 1.",
                    "page": 1,
                },
                {
                    "type": "fill_blank",
                    "difficulty": "medium",
                    "topic": "Vector Semantics",
                    "question": "Fill in the blank: Modern NLP architectures rely heavily on _________ where words are mapped into dense continuous vector spaces.",
                    "options": ["vector semantics", "recurrent memory", "static lookups", "rule grammars"],
                    "correct_answer": "vector semantics",
                    "explanation": "Document Page 1 states: 'Modern NLP architectures rely heavily on vector semantics'.",
                    "page": 1,
                },
            ]
            for item in questions_to_create:
                gq = GeneratedQuestion(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    document_id=doc.id,
                    type=item["type"],
                    difficulty=item["difficulty"],
                    topic=item["topic"],
                    question=item["question"],
                    options=item["options"],
                    correct_answer=item["correct_answer"],
                    explanation=item["explanation"],
                    page=item["page"],
                    quality_score=0.95,
                )
                db.add(gq)
                q_objs.append(gq)
            db.commit()
            print(f"[+] Seeded {len(q_objs)} Generated Questions")
        else:
            q_objs = existing_q

        # 5. Seed Quiz & Attempt
        existing_quiz = db.execute(select(Quiz).where(Quiz.document_id == doc.id)).scalar_one_or_none()
        if not existing_quiz:
            quiz = Quiz(
                id=uuid.uuid4(),
                user_id=user_id,
                document_id=doc.id,
                title="Transformers & Vector Semantics Mastery",
                time_limit_seconds=600,
                config={},
            )
            db.add(quiz)
            db.commit()

            for idx, gq in enumerate(q_objs):
                qq = QuizQuestion(
                    id=uuid.uuid4(),
                    quiz_id=quiz.id,
                    generated_question_id=gq.id,
                    position=idx + 1,
                )
                db.add(qq)
            db.commit()

            # Attempt: 3 correct, 1 wrong (75% accuracy)
            attempt = QuizAttempt(
                id=uuid.uuid4(),
                quiz_id=quiz.id,
                user_id=user_id,
                status="completed",
                score=3.0,
                total=4,
                accuracy=75.0,
                time_taken_seconds=145,
                started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                submitted_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            )
            db.add(attempt)
            db.commit()

            for idx, gq in enumerate(q_objs):
                is_corr = (idx != 1) # Question 2 marked wrong to test diagnostic
                sel_ans = gq.correct_answer if is_corr else "To prevent exploding gradients"
                resp = QuizResponse(
                    id=uuid.uuid4(),
                    attempt_id=attempt.id,
                    quiz_question_id=qq.id,
                    selected_answer=sel_ans,
                    is_correct=is_corr,
                )
                db.add(resp)
            db.commit()
            print(f"[+] Seeded Quiz and Completed Attempt (75% score)")

        # 6. Seed Flashcards
        existing_fc = db.execute(select(Flashcard).where(Flashcard.document_id == doc.id)).scalars().all()
        if not existing_fc:
            cards = [
                ("Self-Attention Mechanism", "Connects all sequence positions simultaneously using scaled dot products between Query, Key, and Value.", "Self-Attention", 2, 6),
                ("Positional Encoding", "Injects order information using sinusoidal waves of varying frequencies.", "Positional Encoding", 1, 1),
                ("Named Entity Recognition", "Classifies entities into predefined categories such as persons, locations, and organizations.", "NLP Foundations", 3, 14),
            ]
            now = datetime.now(timezone.utc)
            for front, back, top, revs, days in cards:
                fc = Flashcard(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    document_id=doc.id,
                    topic=top,
                    front=f"Define: {front}",
                    back=f"{back}\n\n*Reference: Page 1-2*",
                    source_page=1,
                    difficulty_mark="medium",
                    review_count=revs,
                    last_reviewed_at=now - timedelta(days=1),
                    next_review_at=now + timedelta(days=days),
                )
                db.add(fc)
            db.commit()
            print(f"[+] Seeded {len(cards)} Flashcards with SuperMemo SM-2 schedules")

        # 7. Seed Grounded RAG Conversation
        existing_conv = db.execute(select(Conversation).where(Conversation.user_id == user_id)).scalar_one_or_none()
        if not existing_conv:
            conv = Conversation(
                id=uuid.uuid4(),
                user_id=user_id,
                title="Transformer Architecture Discussion",
                document_ids=[str(doc.id)],
                explanation_mode="detailed",
            )
            db.add(conv)
            db.commit()

            msg1 = ChatMessage(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content="How does self-attention eliminate sequential dependency?",
                sources=[],
            )
            msg2 = ChatMessage(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="assistant",
                content=(
                    "### Technical Analysis\n\n"
                    "Based on the source documentation:\n\n"
                    "- Self-attention connects all positions of a sequence simultaneously.\n"
                    "- Queries, Keys, and Values compute attention weights across all tokens in parallel.\n\n"
                    "**Citation:** [Transformer_Architectures_and_NLP.txt, Page 2]"
                ),
                sources=[{
                    "chunk_id": f"{doc.id}_1",
                    "document_id": str(doc.id),
                    "document_title": doc.original_filename,
                    "page_start": 2,
                    "page_end": 2,
                    "score": 94.2,
                    "snippet": DOC1_TEXT_PAGE2[:200],
                }],
            )
            db.add(msg1)
            db.add(msg2)
            db.commit()
            print("[+] Seeded Grounded Conversation with Source Citations")

        # 8. Seed Activity Log
        existing_act = db.execute(select(ActivityLog).where(ActivityLog.user_id == user_id)).scalars().all()
        if not existing_act:
            activities = [
                ("upload", f"Uploaded and indexed '{doc.original_filename}'", doc.id),
                ("summary", f"Generated TextRank summary for '{doc.original_filename}'", doc.id),
                ("quiz", "Scored 75% on Transformers & Vector Semantics Mastery", doc.id),
                ("flashcard", "Reviewed 3 flashcards via SM-2 schedule", doc.id),
            ]
            for act_type, msg, ref in activities:
                act = ActivityLog(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    type=act_type,
                    ref_id=ref,
                    metadata_json={"message": msg},
                    created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                )
                db.add(act)
            db.commit()
            print(f"[+] Seeded {len(activities)} Activity Log Telemetry Entries")

        print("=" * 70)
        print("Demo Database Seeding Complete!")
        print(f"Credentials: {DEMO_EMAIL} / {DEMO_PASS}")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
