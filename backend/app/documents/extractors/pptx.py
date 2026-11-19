import os
from typing import List
from pptx import Presentation
from backend.app.documents.base import BaseExtractor, PageContent
from backend.app.core.logging import logger


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

            # Extract title if present
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_title = slide.shapes.title.text.strip()

            # Iterate over shapes
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            slide_text_blocks.append(text)

                if shape.has_table:
                    table_rows = []
                    for row in shape.table.rows:
                        table_rows.append([cell.text.strip() for cell in row.cells])
                    if table_rows:
                        tables_data.append(table_rows)
                        table_str = "\n".join([" | ".join(r) for r in table_rows])
                        slide_text_blocks.append(f"\n[Table Data]:\n{table_str}\n")

            # Extract speaker notes if present
            try:
                if slide.has_notes_slide and slide.notes_slide:
                    notes_frame = slide.notes_slide.notes_text_frame
                    if notes_frame and notes_frame.text.strip():
                        notes_text = notes_frame.text.strip()
                        slide_text_blocks.append(f"\n[Speaker Notes]:\n{notes_text}")
            except Exception as e:
                logger.debug(f"Failed to extract speaker notes on slide {slide_num}: {e}")

            full_slide_text = "\n\n".join(slide_text_blocks).strip() or f"[Slide {slide_num} Empty]"

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
