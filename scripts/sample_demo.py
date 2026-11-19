import sys
from backend.app.db.session import SessionLocal
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.qgen import QuestionGenerator
from backend.app.nlp.flashcards import FlashcardGenerator
from backend.app.nlp.rag import RAGEngine

def run_demo():
    db = SessionLocal()
    doc = db.query(Document).filter(Document.original_filename.like('%RIP_OSPF%')).first()
    if not doc:
        print("Document not found!")
        return
    print(f"Target Document: {doc.original_filename} (ID: {doc.id}, Pages: {doc.page_count})")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index).all()
    chunk_dicts = [{'id': str(c.id), 'text': c.text, 'page_start': c.page_start, 'page_end': c.page_end} for c in chunks]
    print(f"Total chunks indexed: {len(chunk_dicts)}")

    # 1. 5 Sample Questions
    qgen = QuestionGenerator()
    questions = qgen.generate_from_chunks(chunk_dicts, count=5, difficulty='medium', q_type='mcq')
    print("\n" + "="*70)
    print("SAMPLE 1: 5 GENERATED QUESTIONS (MCQ)")
    print("="*70)
    for i, q in enumerate(questions[:5], 1):
        print(f"\nQuestion {i} (Source Page: {q.get('page')}):")
        print(f"  Stem: {q['question']}")
        print("  Options:")
        for opt in q['options']:
            marker = " [CORRECT]" if opt == q['correct_answer'] else ""
            print(f"    * {opt}{marker}")
        print(f"  Explanation: {q['explanation']}")

    # 2. 5 Sample Flashcards
    fc_gen = FlashcardGenerator()
    cards = fc_gen.generate_flashcards(chunk_dicts, max_cards=5)
    print("\n" + "="*70)
    print("SAMPLE 2: 5 GENERATED FLASHCARDS")
    print("="*70)
    for i, card in enumerate(cards[:5], 1):
        print(f"\nCard {i} (Source Page: {card.get('source_page')}):")
        print(f"  Front: {card['front']}")
        print(f"  Back:  {card['back']}")

    # 3. 3 RAG Chat Answers
    rag = RAGEngine(db=db)
    queries = [
        "What is the maximum hop count in RIP and what happens at 16?",
        "What is a transient link in OSPF?",
        "explain virtual memory paging"
    ]
    print("\n" + "="*70)
    print("SAMPLE 3: 3 RAG CHAT ANSWERS (INCLUDING OFF-TOPIC)")
    print("="*70)
    for query in queries:
        res = rag.generate_answer(
            user_id=doc.user_id,
            query=query,
            document_ids=[doc.id],
            explanation_mode="technical",
            top_k=3
        )
        print(f"\nUser Query: \"{query}\"")
        print(f"Confidence Score: {res['confidence_score']:.2f}")
        print(f"Sources: {res['sources']}")
        print(f"Answer:\n{res['answer']}")

if __name__ == "__main__":
    run_demo()
