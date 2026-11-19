import os
from typing import Dict, Type
from backend.app.documents.base import BaseExtractor
from backend.app.documents.extractors.pdf import PDFExtractor
from backend.app.documents.extractors.docx import DOCXExtractor
from backend.app.documents.extractors.pptx import PPTXExtractor
from backend.app.documents.extractors.text import TextExtractor, MarkdownExtractor, CSVExtractor
from backend.app.documents.extractors.image import ImageExtractor


EXTRACTOR_REGISTRY: Dict[str, Type[BaseExtractor]] = {
    ".pdf": PDFExtractor,
    ".docx": DOCXExtractor,
    ".doc": DOCXExtractor,
    ".pptx": PPTXExtractor,
    ".ppt": PPTXExtractor,
    ".txt": TextExtractor,
    ".md": MarkdownExtractor,
    ".markdown": MarkdownExtractor,
    ".csv": CSVExtractor,
    ".png": ImageExtractor,
    ".jpg": ImageExtractor,
    ".jpeg": ImageExtractor,
    ".tiff": ImageExtractor,
    ".tif": ImageExtractor,
    ".bmp": ImageExtractor,
    ".webp": ImageExtractor,
}


def get_extractor_for_file(file_path_or_name: str) -> BaseExtractor:
    _, ext = os.path.splitext(file_path_or_name.lower())
    extractor_cls = EXTRACTOR_REGISTRY.get(ext)
    if not extractor_cls:
        raise ValueError(f"Unsupported file extension '{ext}' for document processing.")
    return extractor_cls()
