import os
import uuid
import pytest
import fitz  # PyMuPDF
import docx
from pptx import Presentation
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models.user import User
from backend.app.db.models.document import Document, DocumentPage, DocumentChunk
from backend.app.documents.extractors.text import TextExtractor, MarkdownExtractor, CSVExtractor
from backend.app.documents.extractors.pdf import PDFExtractor
from backend.app.documents.extractors.docx import DOCXExtractor
from backend.app.documents.extractors.pptx import PPTXExtractor
from backend.app.documents.chunking import SentenceAwareChunker
from backend.app.documents.pipeline import DocumentPipeline
from backend.app.repositories.consistency import check_document_consistency, purge_document_cascade


@pytest.fixture(scope="module")
def test_db_session(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("doc_test_db")
    db_file = tmp_dir / "test_doc.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy user
    test_user = User(
        id=uuid.uuid4(),
        email="docuser@example.com",
        hashed_password="fakehashedpassword",
        full_name="Document Tester",
    )
    session.add(test_user)
    session.commit()

    yield session, test_user
    session.close()


def test_text_and_markdown_extractors():
    txt_path = "backend/tests/fixtures/sample.txt"
    md_path = "backend/tests/fixtures/sample.md"

    txt_extractor = TextExtractor()
    pages_txt = txt_extractor.extract(txt_path)
    assert len(pages_txt) >= 1
    assert "Natural Language Processing" in pages_txt[0].text

    md_extractor = MarkdownExtractor()
    pages_md = md_extractor.extract(md_path)
    assert len(pages_md) >= 1
    assert "Deep Learning in NLP" in pages_md[0].text
    assert pages_md[0].section_title == "Deep Learning in NLP"


def test_csv_extractor():
    csv_path = "backend/tests/fixtures/sample.csv"
    extractor = CSVExtractor()
    pages = extractor.extract(csv_path)

    assert len(pages) == 1
    assert "BERT" in pages[0].text
    assert "FLAN-T5" in pages[0].text
    assert pages[0].tables_json is not None


def test_pdf_extractor(tmp_path):
    pdf_path = str(tmp_path / "test.pdf")
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Natural Language Processing with Deep Learning.\nSection 1: Introduction.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Section 2: Transformer Architectures and Self-Attention mechanisms.")
    doc.save(pdf_path)
    doc.close()

    extractor = PDFExtractor()
    pages = extractor.extract(pdf_path)

    assert len(pages) == 2
    assert "Natural Language Processing" in pages[0].text
    assert "Transformer Architectures" in pages[1].text
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2


def test_docx_extractor(tmp_path):
    docx_path = str(tmp_path / "test.docx")
    doc = docx.Document()
    doc.add_heading("Deep Learning Overview", level=1)
    doc.add_paragraph("Recurrent neural networks and attention mechanisms.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Model"
    table.cell(0, 1).text = "Score"
    table.cell(1, 0).text = "BERT"
    table.cell(1, 1).text = "92.4"
    doc.save(docx_path)

    extractor = DOCXExtractor()
    pages = extractor.extract(docx_path)

    assert len(pages) >= 1
    assert "Deep Learning Overview" in pages[0].text
    assert "BERT" in pages[0].text
    assert pages[0].section_title == "Deep Learning Overview"


def test_pptx_extractor(tmp_path):
    pptx_path = str(tmp_path / "test.pptx")
    prs = Presentation()
    slide_layout = prs.slide_layouts[0]  # title slide
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Introduction to Attention Mechanisms"
    slide.placeholders[1].text = "Scaled dot-product and multi-head attention."
    prs.save(pptx_path)

    extractor = PPTXExtractor()
    pages = extractor.extract(pptx_path)

    assert len(pages) == 1
    assert "Attention Mechanisms" in pages[0].text
    assert pages[0].section_title == "Introduction to Attention Mechanisms"


def test_sentence_aware_chunker():
    from backend.app.documents.base import PageContent
    pages = [
        PageContent(
            page_number=1,
            text="First sentence about natural language processing. " * 30,
            section_title="NLP Section 1",
        ),
        PageContent(
            page_number=2,
            text="Second page discussing neural machine translation. " * 30,
            section_title="NLP Section 2",
        ),
    ]

    chunker = SentenceAwareChunker(target_words=100, overlap_words=20)
    chunks = chunker.chunk_pages(pages)

    assert len(chunks) > 1
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2
    for c in chunks:
        assert c.token_count > 0
        assert c.content.strip() != ""


def test_document_pipeline_end_to_end(test_db_session, tmp_path):
    db, user = test_db_session

    # Create dummy text document to process
    sample_file = tmp_path / "pipeline_test.txt"
    sample_content = (
        "Artificial Intelligence in Higher Education.\n\n"
        "Modern university curriculums integrate intelligent document analysis and RAG engines. "
        "Students benefit from automated question generation, interactive flashcards, and spaced repetition. "
        "Natural language processing bridges textbook content with personalized assessments."
    )
    sample_file.write_text(sample_content, encoding="utf-8")

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        original_filename="pipeline_test.txt",
        stored_path=str(sample_file),
        mime_type="text/plain",
        file_size=len(sample_content),
        status="uploaded",
    )
    db.add(doc)
    db.commit()

    pipeline = DocumentPipeline(db)
    processed_doc = pipeline.process_file(
        document_id=doc.id,
        user_id=user.id,
        file_path=str(sample_file),
        original_filename="pipeline_test.txt",
    )

    assert processed_doc.status == "ready"
    assert processed_doc.page_count >= 1
    assert processed_doc.file_hash is not None

    pages = db.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id)).scalars().all()
    assert len(pages) >= 1
    assert "Artificial Intelligence" in pages[0].text

    chunks = db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).scalars().all()
    assert len(chunks) >= 1
    assert chunks[0].chunk_index == 0

    # Consistency check
    consistency = check_document_consistency(db, doc.id)
    assert consistency["consistent"] is True
    assert consistency["pages_count"] >= 1
    assert consistency["chunks_count"] >= 1

    # Cascade purge check
    purged = purge_document_cascade(db, doc.id)
    assert purged is True
    check_after = check_document_consistency(db, doc.id)
    assert check_after["exists"] is False
