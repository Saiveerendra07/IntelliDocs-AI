import json
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from backend.app.db.session import SessionLocal
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.nlp.qgen import QuestionGenerator

def main():
    db = SessionLocal()
    qgen = QuestionGenerator(db)

    # Fetch chunks for RIP_OSPF.pptx, ch4.pdf, Unit 4 Transport Layer.pptx
    docs = {
        "rip_ospf": db.query(Document).filter(Document.original_filename == "RIP_OSPF.pptx").first(),
        "ch4_sql": db.query(Document).filter(Document.original_filename == "ch4.pdf").first(),
        "transport": db.query(Document).filter(Document.original_filename == "Unit 4 Transport Layer.pptx").first(),
    }

    doc_chunks = {}
    for key, d in docs.items():
        if d:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == d.id).order_by(DocumentChunk.chunk_index).all()
            doc_chunks[key] = chunks
            print(f"Loaded {len(chunks)} chunks for {d.original_filename}")

    results = {
        "mcq": [],
        "true_false": [],
        "fill_blank": [],
        "short_answer": []
    }

    # Generate 10 questions of each type distributed across documents
    types = ["mcq", "true_false", "fill_blank", "short_answer"]
    
    for q_type in types:
        for doc_key, chunks in doc_chunks.items():
            if len(results[q_type]) >= 10:
                break
            needed = 10 - len(results[q_type])
            count = min(4, needed)
            d_obj = docs[doc_key]
            generated = qgen.generate_from_chunks(
                chunks=chunks,
                q_type=q_type,
                difficulty="medium",
                count=count,
                doc_filename=d_obj.original_filename
            )
            for item in generated:
                item["source_document"] = d_obj.original_filename
                results[q_type].append(item)
                if len(results[q_type]) >= 10:
                    break

    db.close()

    output_path = "docs/generated_samples.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nGenerated total {sum(len(v) for v in results.values())} questions saved to {output_path}:")
    for q_type, q_list in results.items():
        print(f" - {q_type.upper()}: {len(q_list)} items")

if __name__ == "__main__":
    main()
