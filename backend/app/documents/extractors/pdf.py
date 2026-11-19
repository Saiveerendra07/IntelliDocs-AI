import os
import shutil
from typing import List, Optional
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from backend.app.documents.base import BaseExtractor, PageContent
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Set Tesseract executable path if configured
if settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


class PDFExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at {file_path}")

        doc = fitz.open(file_path)
        pages_content = []

        # Check if tesseract binary is available on the system
        tesseract_available = bool(
            (settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD))
            or shutil.which("tesseract")
        )

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            raw_text = page.get_text("text").strip()
            ocr_applied = False
            tables_data = []

            # 1. Table extraction
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    for tab in tables.tables:
                        tab_data = tab.extract()
                        if tab_data:
                            tables_data.append(tab_data)
                            # Append table as markdown-like text
                            table_str = "\n".join([" | ".join([str(c or "") for c in row]) for row in tab_data])
                            raw_text += f"\n\n[Table Data]:\n{table_str}\n"
            except Exception as e:
                logger.debug(f"Table extraction skipped on page {page_num}: {e}")

            # 2. Scanned Page Detection
            # If text length is very low (< 50 chars) and page has images, route to OCR
            image_list = page.get_images()
            is_scanned = len(raw_text) < 50 and len(image_list) > 0

            if is_scanned and tesseract_available:
                try:
                    # Render page at 250 DPI for clean OCR
                    pix = page.get_pixmap(dpi=250)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img)
                    if len(ocr_text.strip()) > len(raw_text):
                        raw_text = ocr_text.strip()
                        ocr_applied = True
                except Exception as e:
                    logger.warning(f"OCR failed on page {page_num} of {file_path}: {e}")

            # Section title heuristic from first line if prominent
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            section_title = None
            for l in lines:
                if not any(re.search(pat, l, re.I) for pat in ("silberschatz", "korth", "sudarshan", "copyright", "©", "db-book")):
                    section_title = l[:80]
                    break

            pages_content.append(PageContent(
                page_number=page_num,
                text=raw_text or "[Empty Page]",
                ocr_applied=ocr_applied,
                section_title=section_title,
                tables_json=tables_data if tables_data else None,
            ))

        doc.close()
        return pages_content
