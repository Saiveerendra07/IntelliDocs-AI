import os
import re
from typing import List
from pptx import Presentation
from backend.app.documents.base import BaseExtractor, PageContent
from backend.app.core.logging import logger


def clean_pptx_text(text: str) -> str:
    """Cleans presentation text, normalizes unicode arrows and bullet symbols."""
    if not text:
        return ""
    # Normalize unicode symbols often found in PowerPoint bullets
    text = text.replace("\uf0e0", "->").replace("\uf0a7", "*").replace("\uf0b7", "*")
    text = text.replace("\u2022", "*").replace("\u2013", "-").replace("\u2014", "-")
    # Clean redundant whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


class PPTXExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PPTX file not found at {file_path}")

        prs = Presentation(file_path)
        pages = []

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            slide_text_blocks = []
            slide_title = None
            tables_data = []

            # 1. Extract slide title if present
            title_shape = None
            try:
                if slide.shapes.title and slide.shapes.title.text.strip():
                    slide_title = clean_pptx_text(slide.shapes.title.text)
                    title_shape = slide.shapes.title
                    slide_text_blocks.append(slide_title)
            except Exception as e:
                logger.debug(f"Slide {slide_num} title check: {e}")

            # 2. Extract text frames (excluding title shape to prevent duplicate headers)
            for shape in slide.shapes:
                if shape == title_shape:
                    continue

                if shape.has_text_frame:
                    shape_paragraphs = []
                    for paragraph in shape.text_frame.paragraphs:
                        text = clean_pptx_text(paragraph.text)
                        if text:
                            # Avoid appending if exact match with slide title
                            if slide_title and text.lower() == slide_title.lower():
                                continue
                            shape_paragraphs.append(text)
                    if shape_paragraphs:
                        slide_text_blocks.append("\n".join(shape_paragraphs))

                if shape.has_table:
                    table_rows = []
                    for row in shape.table.rows:
                        row_vals = [clean_pptx_text(cell.text) for cell in row.cells]
                        if any(row_vals):
                            table_rows.append(row_vals)
                    if table_rows:
                        tables_data.append(table_rows)
                        table_str = "\n".join([" | ".join(r) for r in table_rows])
                        slide_text_blocks.append(f"\n[Table Data]:\n{table_str}\n")

            # 3. Extract speaker notes if present
            try:
                if slide.has_notes_slide and slide.notes_slide:
                    notes_frame = slide.notes_slide.notes_text_frame
                    if notes_frame and notes_frame.text.strip():
                        notes_text = clean_pptx_text(notes_frame.text)
                        if notes_text:
                            slide_text_blocks.append(f"\n[Speaker Notes]:\n{notes_text}")
            except Exception as e:
                logger.debug(f"Failed to extract speaker notes on slide {slide_num}: {e}")

            full_slide_text = "\n\n".join(slide_text_blocks).strip()
            if not full_slide_text:
                full_slide_text = f"[Slide {slide_num} Empty]"

            pages.append(PageContent(
                page_number=slide_num,
                text=full_slide_text,
                ocr_applied=False,
                section_title=slide_title,
                tables_json=tables_data if tables_data else None,
            ))

        if not pages:
            pages.append(PageContent(
                page_number=1,
                text="[Empty Presentation]",
                ocr_applied=False,
                section_title=None,
                tables_json=None,
            ))

        return pages
