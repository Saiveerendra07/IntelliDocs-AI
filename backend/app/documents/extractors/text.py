import csv
import io
import os
from typing import List, Optional
import chardet
from backend.app.documents.base import BaseExtractor, PageContent
from backend.app.core.logging import logger


def detect_and_read_text(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    detected = chardet.detect(raw_bytes)
    encoding = detected.get("encoding") or "utf-8"

    try:
        return raw_bytes.decode(encoding)
    except Exception:
        try:
            return raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            return raw_bytes.decode("latin-1", errors="replace")


class TextExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")

        raw_text = detect_and_read_text(file_path).strip()
        if not raw_text:
            return [PageContent(page_number=1, text="[Empty Text Document]", ocr_applied=False)]

        page_size = 3000
        pages = []
        lines = raw_text.splitlines()
        first_title = None
        for line in lines:
            if line.strip():
                first_title = line.strip()[:80]
                break

        if len(raw_text) <= page_size:
            pages.append(PageContent(
                page_number=1,
                text=raw_text,
                ocr_applied=False,
                section_title=first_title,
                tables_json=None,
            ))
        else:
            total_pages = (len(raw_text) + page_size - 1) // page_size
            for idx in range(total_pages):
                chunk = raw_text[idx * page_size : (idx + 1) * page_size]
                chunk_lines = [l.strip() for l in chunk.splitlines() if l.strip()]
                chunk_title = chunk_lines[0][:80] if chunk_lines else first_title
                pages.append(PageContent(
                    page_number=idx + 1,
                    text=chunk,
                    ocr_applied=False,
                    section_title=chunk_title,
                    tables_json=None,
                ))

        return pages


class MarkdownExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Markdown file not found at {file_path}")

        raw_text = detect_and_read_text(file_path).strip()
        if not raw_text:
            return [PageContent(page_number=1, text="[Empty Markdown Document]", ocr_applied=False)]

        # Extract top-level heading if available
        first_heading = None
        for line in raw_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("#"):
                first_heading = line_str.lstrip("#").strip()
                break

        page_size = 3000
        pages = []
        if len(raw_text) <= page_size:
            pages.append(PageContent(
                page_number=1,
                text=raw_text,
                ocr_applied=False,
                section_title=first_heading,
                tables_json=None,
            ))
        else:
            total_pages = (len(raw_text) + page_size - 1) // page_size
            for idx in range(total_pages):
                chunk = raw_text[idx * page_size : (idx + 1) * page_size]
                chunk_heading = first_heading
                for line in chunk.splitlines():
                    if line.strip().startswith("#"):
                        chunk_heading = line.strip().lstrip("#").strip()
                        break
                pages.append(PageContent(
                    page_number=idx + 1,
                    text=chunk,
                    ocr_applied=False,
                    section_title=chunk_heading,
                    tables_json=None,
                ))

        return pages


class CSVExtractor(BaseExtractor):
    def extract(self, file_path: str) -> List[PageContent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found at {file_path}")

        raw_text = detect_and_read_text(file_path)
        reader = csv.reader(io.StringIO(raw_text))
        rows = list(reader)

        if not rows:
            return [PageContent(page_number=1, text="[Empty CSV Document]", ocr_applied=False)]

        header = rows[0]
        data_rows = rows[1:]

        # Create structured markdown table representation
        table_lines = [" | ".join(header)]
        table_lines.append(" | ".join(["---"] * len(header)))
        for r in data_rows[:100]:  # limit to top 100 rows per table preview
            table_lines.append(" | ".join(r))

        rendered_text = f"CSV Dataset Summary: {len(rows)} rows, {len(header)} columns.\n\n"
        rendered_text += "Columns: " + ", ".join(header) + "\n\n"
        rendered_text += "[Table Data]:\n" + "\n".join(table_lines)

        return [PageContent(
            page_number=1,
            text=rendered_text,
            ocr_applied=False,
            section_title=f"CSV Data ({len(rows)} rows)",
            tables_json=[rows[:100]],
        )]
