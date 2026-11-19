import os
import shutil
from typing import List
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from backend.app.documents.base import BaseExtractor, PageContent
from backend.app.core.config import settings
from backend.app.core.logging import logger

if settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


class ImageExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found at {file_path}")

        tesseract_available = bool(
            (settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD))
            or shutil.which("tesseract")
        )

        filename = os.path.basename(file_path)
        if not tesseract_available:
            logger.warning(
                f"Tesseract OCR is not installed or configured. Skipping OCR for image {file_path}."
            )
            return [PageContent(
                page_number=1,
                text=f"[Image: {filename}] OCR binary not detected on system. Please install Tesseract OCR to extract text from images.",
                ocr_applied=False,
                section_title=f"Image ({filename})",
            )]

        try:
            with Image.open(file_path) as img:
                # Preprocess image for OCR: convert to grayscale, autothreshold / contrast
                gray = ImageOps.grayscale(img)
                # Apply slight sharpening
                sharpened = gray.filter(ImageFilter.SHARPEN)

                ocr_text = pytesseract.image_to_string(sharpened).strip()

                if not ocr_text:
                    ocr_text = f"[Image: {filename} contained no recognizable text]"

                return [PageContent(
                    page_number=1,
                    text=ocr_text,
                    ocr_applied=True,
                    section_title=f"Image ({filename})",
                )]
        except Exception as e:
            logger.error(f"Failed to perform OCR on image {file_path}: {e}")
            return [PageContent(
                page_number=1,
                text=f"[Image: {filename}] OCR processing failed: {str(e)}",
                ocr_applied=False,
                section_title=f"Image ({filename})",
            )]
