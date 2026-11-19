import os
import fitz
from PIL import Image, ImageDraw, ImageFont
import pytest
from backend.app.documents.extractors.image import ImageExtractor
from backend.app.documents.extractors.pdf import PDFExtractor


def test_tesseract_image_ocr(tmp_path):
    # 1. Create a clean image with rendered text
    img_path = str(tmp_path / "test_ocr_receipt.png")
    img = Image.new("RGB", (600, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw plain clear text
    draw.text((30, 80), "Natural Language Processing OCR Test 2026", fill=(0, 0, 0))
    img.save(img_path)

    extractor = ImageExtractor()
    pages = extractor.extract(img_path)

    assert len(pages) == 1
    assert pages[0].ocr_applied is True
    assert "Natural Language Processing" in pages[0].text
    assert "OCR Test" in pages[0].text


def test_tesseract_scanned_pdf_ocr(tmp_path):
    # 1. Create an image containing text
    img_path = str(tmp_path / "scanned_page.png")
    img = Image.new("RGB", (800, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 100), "Scanned Document Page: Transformers and Attention Mechanisms", fill=(0, 0, 0))
    img.save(img_path)

    # 2. Embed this image into a PDF without adding any digital text layer (simulating a pure scan)
    pdf_path = str(tmp_path / "scanned_doc.pdf")
    doc = fitz.open()
    page = doc.new_page(width=800, height=300)
    page.insert_image(page.rect, filename=img_path)
    doc.save(pdf_path)
    doc.close()

    # 3. Extract using PDFExtractor which must detect that text length is 0 and trigger Tesseract OCR
    extractor = PDFExtractor()
    pages = extractor.extract(pdf_path)

    assert len(pages) == 1
    assert pages[0].ocr_applied is True
    assert "Transformers" in pages[0].text or "Attention" in pages[0].text
