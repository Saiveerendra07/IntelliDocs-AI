import os
import sys
from backend.app.db.session import SessionLocal
from backend.app.db.models.document import Document, DocumentChunk, DocumentPage
from backend.app.documents.pipeline import DocumentPipeline
from backend.app.documents.cleaner import detect_repeated_lines, clean_page_lines
from backend.app.documents.extractors.pdf import PDFExtractor

def reprocess():
    db = SessionLocal()
    pipeline = DocumentPipeline(db)

    docs_to_reprocess = [
        "ch4.pdf",
        "RIP_OSPF.pptx",
        "Unit 4 Transport Layer.pptx"
    ]

    for name in docs_to_reprocess:
        doc = db.query(Document).filter(Document.original_filename.like(f"%{name}%")).first()
        if not doc:
            print(f"[-] Document {name} not found in DB!")
            continue

        file_path = doc.stored_path
        if not os.path.exists(file_path):
            alt_path = os.path.join("backend", doc.stored_path)
            if os.path.exists(alt_path):
                file_path = alt_path

        print(f"\n[*] Reprocessing {name} (ID: {doc.id}, Path: {file_path})...")
        pipeline.process_file(
            document_id=doc.id,
            user_id=doc.user_id,
            file_path=file_path,
            original_filename=doc.original_filename,
        )

        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        print(f"[+] Successfully reprocessed {name}: {chunk_count} clean chunks saved in DB & ChromaDB.")

    # Show Before and After for 3 pages of ch4.pdf
    ch4_doc = db.query(Document).filter(Document.original_filename.like("%ch4.pdf%")).first()
    if ch4_doc:
        print("\n" + "="*70)
        print("BEFORE / AFTER CLEANING VERIFICATION FOR ch4.pdf")
        print("="*70)

        # Raw extraction
        pdf_extractor = PDFExtractor()
        raw_pages = pdf_extractor.extract(ch4_doc.stored_path)
        repeated = detect_repeated_lines(raw_pages, threshold=0.25)

        for p_num in [3, 47, 48]:
            raw_p = next((p for p in raw_pages if p.page_number == p_num), None)
            clean_rec = db.query(DocumentPage).filter(
                DocumentPage.document_id == ch4_doc.id,
                DocumentPage.page_number == p_num
            ).first()

            print(f"\n--- PAGE {p_num} BEFORE (RAW EXTRACTION) ---")
            print(raw_p.text.strip() if raw_p else "N/A")
            print(f"\n--- PAGE {p_num} AFTER (CLEANED EXTRACTION) ---")
            print(clean_rec.text.strip() if clean_rec else "N/A")
            print("-" * 50)

if __name__ == "__main__":
    reprocess()
