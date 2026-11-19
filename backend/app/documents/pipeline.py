import hashlib
import os
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.models.document import Document, DocumentPage, DocumentChunk
from backend.app.documents.base import PageContent
from backend.app.documents.chunking import SentenceAwareChunker, DocumentChunk as ChunkDTO
from backend.app.documents.extractors.registry import get_extractor_for_file


def calculate_sha256(file_path: str) -> str:
    """Calculates SHA256 hash of a file for deduplication and integrity check."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class DocumentPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.chunker = SentenceAwareChunker(target_words=250, overlap_words=40)

    def process_file(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        file_path: str,
        original_filename: str,
    ) -> Document:
        """
        Executes the extraction, OCR (if applicable), and chunking pipeline.
        Updates document records in the database.
        """
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id
        ).first()

        if not doc:
            raise ValueError(f"Document {document_id} for user {user_id} not found.")

        try:
            doc.status = "extracting"
            doc.processing_progress = 0.2
            self.db.commit()

            # 1. Compute file hash
            if not doc.file_hash:
                doc.file_hash = calculate_sha256(file_path)

            # 2. Extract content using the appropriate extractor
            extractor = get_extractor_for_file(file_path)
            pages_content: List[PageContent] = extractor.extract(file_path)

            if not pages_content:
                raise ValueError("No content could be extracted from document.")

            doc.page_count = len(pages_content)
            doc.is_scanned = any(p.ocr_applied for p in pages_content)
            doc.processing_progress = 0.5
            self.db.commit()

            # 3. Clean pages and save DocumentPage records
            from backend.app.documents.cleaner import detect_repeated_lines, clean_page_lines
            repeated_lines = detect_repeated_lines(pages_content, threshold=0.25)

            # Clear previous pages/chunks if reprocessing
            self.db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
            self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

            for p in pages_content:
                cleaned_text, title, prose, code = clean_page_lines(p.text, repeated_lines)
                page_rec = DocumentPage(
                    document_id=doc.id,
                    page_number=p.page_number,
                    text=cleaned_text or p.text,
                    ocr_applied=p.ocr_applied,
                    tables_json=p.tables_json,
                )
                self.db.add(page_rec)

            doc.status = "processing"
            doc.processing_progress = 0.7
            self.db.commit()

            # 4. Generate chunks
            chunks_dto: List[ChunkDTO] = self.chunker.chunk_pages(pages_content)

            for c in chunks_dto:
                chunk_rec = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=c.chunk_index,
                    text=c.content,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    token_count=c.token_count,
                    section_title=c.section_title,
                )
                self.db.add(chunk_rec)

            # 5. Index chunks into Vector Store (ChromaDB)
            try:
                from backend.app.nlp.vectorstore import VectorStoreManager
                vm = VectorStoreManager()
                vm.index_chunks(user_id=user_id, document_id=doc.id, chunks=chunks_dto)
            except Exception as e_vec:
                logger.warning(f"Vector indexing skipped/failed for {doc.id}: {e_vec}")

            # 6. Mark document as ready
            doc.status = "ready"
            doc.processing_progress = 1.0
            doc.error_message = None
            self.db.commit()
            self.db.refresh(doc)

            logger.info(
                f"Successfully processed document {doc.id} ({doc.original_filename}): "
                f"{len(pages_content)} pages, {len(chunks_dto)} chunks."
            )
            return doc

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            doc.status = "failed"
            doc.error_message = str(e)
            doc.processing_progress = 0.0
            self.db.commit()
            raise
