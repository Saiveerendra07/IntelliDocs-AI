import os
from typing import List
import docx
from backend.app.documents.base import BaseExtractor, PageContent


class DOCXExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"DOCX file not found at {file_path}")

        doc = docx.Document(file_path)
        full_text_blocks = []
        current_section = None
        tables_data = []

        # Extract paragraphs and detect headings
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style.name.startswith("Heading"):
                current_section = text
            full_text_blocks.append(text)

        # Extract tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                table_rows.append([cell.text.strip() for cell in row.cells])
            if table_rows:
                tables_data.append(table_rows)
                table_str = "\n".join([" | ".join(r) for r in table_rows])
                full_text_blocks.append(f"\n[Table Data]:\n{table_str}\n")

        full_text = "\n\n".join(full_text_blocks) or "[Empty DOCX Document]"

        # Segment into pseudo-pages of ~3000 chars for consistent referencing
        page_size = 3000
        pages = []
        if len(full_text) <= page_size:
            pages.append(PageContent(
                page_number=1,
                text=full_text,
                ocr_applied=False,
                section_title=current_section,
                tables_json=tables_data if tables_data else None,
            ))
        else:
            total_pages = (len(full_text) + page_size - 1) // page_size
            for idx in range(total_pages):
                chunk = full_text[idx * page_size : (idx + 1) * page_size]
                pages.append(PageContent(
                    page_number=idx + 1,
                    text=chunk,
                    ocr_applied=False,
                    section_title=current_section,
                    tables_json=tables_data if idx == 0 and tables_data else None,
                ))

        return pages
