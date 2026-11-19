import re
from typing import List, Optional, Set
from pydantic import BaseModel
from backend.app.documents.base import PageContent
from backend.app.documents.cleaner import (
    detect_repeated_lines,
    clean_page_lines,
    is_sql_or_code,
    is_low_information_slide,
    COPYRIGHT_PATTERNS,
    SLIDE_NUMBER_PATTERNS,
    TERMINAL_PATTERNS,
)


class DocumentChunk(BaseModel):
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    section_title: Optional[str] = None
    token_count: int
    chunk_type: str = "prose"  # prose, code, table, slide
    is_informative: bool = True


def split_into_sentences(text: str, exclude_code: bool = True) -> List[str]:
    """
    Splits text into coherent prose sentences and statements.
    - Filters out repeated headers, footers, copyright, and slide numbering.
    - Excludes SQL syntax and code fragments from prose sentences when exclude_code is True.
    - Handles bullet lists and preserves complete clauses.
    """
    if not text or not text.strip():
        return []

    # Clean unicode symbols and normalize bullet markers
    cleaned_text = (
        text.replace("\uf0e0", "->")
        .replace("\uf0a7", "*")
        .replace("\uf0b7", "*")
        .replace("\u2022", "*")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    results = []

    for line in lines:
        # Check copyright / slide numbering / terminal patterns
        if any(pat.match(line) for pat in COPYRIGHT_PATTERNS):
            continue
        if any(pat.match(line) for pat in SLIDE_NUMBER_PATTERNS):
            continue
        if any(pat.match(line) for pat in TERMINAL_PATTERNS):
            continue

        # Strip leading bullet indicators (*, -, •, numbers like 1.)
        cleaned_line = re.sub(r"^[\*\-\•\d+\.]\s*", "", line).strip()
        if not cleaned_line:
            continue

        # If line is SQL or code and exclude_code is True, skip from prose sentences
        if exclude_code and is_sql_or_code(cleaned_line):
            continue

        # Skip colon headings or fragments ending with :-
        if cleaned_line.endswith(":") or cleaned_line.endswith(":-"):
            continue

        # Sentence tokenization
        try:
            import nltk
            sub_sents = nltk.tokenize.sent_tokenize(cleaned_line)
            for s in sub_sents:
                s_strip = s.strip()
                if s_strip and len(s_strip.split()) >= 4:
                    if not (exclude_code and is_sql_or_code(s_strip)):
                        results.append(s_strip)
        except Exception:
            sentence_end_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')
            raw = sentence_end_pattern.split(cleaned_line)
            for r in raw:
                r_strip = r.strip()
                if r_strip and len(r_strip.split()) >= 4:
                    if not (exclude_code and is_sql_or_code(r_strip)):
                        results.append(r_strip)

    return results


class SentenceAwareChunker:
    def __init__(self, target_words: int = 250, overlap_words: int = 40):
        self.target_words = target_words
        self.overlap_words = overlap_words

    def chunk_pages(self, pages: List[PageContent]) -> List[DocumentChunk]:
        """
        Chunks a sequence of PageContent into coherent units.
        Pre-cleans repeating headers/footers and isolates SQL/code blocks.
        """
        if not pages:
            return []

        # 1. Detect recurring lines across the entire document (>= 25% threshold)
        repeated_lines = detect_repeated_lines(pages, threshold=0.25)

        # 2. Check if document has slide-like or short-page structure
        content_pages = [p for p in pages if len(p.text.split()) >= 10 and not p.text.startswith("[Slide")]
        avg_words_per_page = (
            sum(len(p.text.split()) for p in content_pages) / max(1, len(content_pages))
            if content_pages else 0
        )
        is_slide_structure = len(pages) > 3 and avg_words_per_page < 160

        if is_slide_structure:
            return self._chunk_slides(pages, repeated_lines)
        else:
            return self._chunk_continuous(pages, repeated_lines)

    def _chunk_slides(self, pages: List[PageContent], repeated_lines: Set[str]) -> List[DocumentChunk]:
        """Preserves individual cleaned slides as distinct chunks with attached titles."""
        chunks: List[DocumentChunk] = []
        chunk_idx = 0
        total_pages = len(pages)

        for page in pages:
            raw_text = page.text.strip()
            if not raw_text or raw_text.startswith("[Slide"):
                continue

            cleaned_full_text, slide_title, prose_sents, code_lines = clean_page_lines(
                raw_text, repeated_lines
            )

            if not cleaned_full_text.strip():
                continue

            # Determine whether slide is low information (title slide, TOC, etc.)
            low_info = is_low_information_slide(
                slide_title=slide_title,
                prose_sentences=prose_sents,
                code_lines=code_lines,
                page_number=page.page_number,
                total_pages=total_pages,
            )

            # Determine chunk type
            if code_lines and len(prose_sents) <= 1:
                chunk_type = "code"
            elif any(kw in (slide_title or "").lower() for kw in ("syntax", "command", "schema", "query", "example")):
                chunk_type = "code" if code_lines else "slide"
            else:
                chunk_type = "slide"

            active_section = slide_title or page.section_title or f"Page {page.page_number}"
            if any(re.search(pat, active_section, re.I) for pat in ("silberschatz", "korth", "sudarshan", "copyright", "©", "db-book")):
                active_section = f"Page {page.page_number}"
            token_count = len(cleaned_full_text.split())

            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=cleaned_full_text,
                page_start=page.page_number,
                page_end=page.page_number,
                section_title=active_section,
                token_count=token_count,
                chunk_type=chunk_type,
                is_informative=not low_info,
            ))
            chunk_idx += 1

        return chunks

    def _chunk_continuous(self, pages: List[PageContent], repeated_lines: Set[str]) -> List[DocumentChunk]:
        """Continuous sentence-aware sliding window chunking on cleaned text."""
        sentence_records = []
        for page in pages:
            cleaned_full_text, slide_title, prose_sents, code_lines = clean_page_lines(
                page.text, repeated_lines
            )
            for s in prose_sents:
                sentence_records.append({
                    "sentence": s,
                    "page_number": page.page_number,
                    "section_title": slide_title or page.section_title,
                    "word_count": len(s.split()),
                    "is_code": False,
                })
            for c in code_lines:
                sentence_records.append({
                    "sentence": c,
                    "page_number": page.page_number,
                    "section_title": slide_title or page.section_title,
                    "word_count": len(c.split()),
                    "is_code": True,
                })

        if not sentence_records:
            return []

        chunks: List[DocumentChunk] = []
        chunk_idx = 0
        i = 0
        n = len(sentence_records)

        while i < n:
            current_sentences = []
            current_words = 0
            page_start = sentence_records[i]["page_number"]
            page_end = page_start
            active_section = sentence_records[i]["section_title"]
            has_code = False

            while i < n and (current_words + sentence_records[i]["word_count"] <= self.target_words or not current_sentences):
                # Don't merge across completely different sections
                if active_section and sentence_records[i]["section_title"] and active_section != sentence_records[i]["section_title"] and current_words >= 60:
                    break

                rec = sentence_records[i]
                current_sentences.append(rec["sentence"])
                current_words += rec["word_count"]
                page_end = rec["page_number"]
                if rec["is_code"]:
                    has_code = True
                i += 1

            chunk_content = "\n\n".join(current_sentences)
            token_count = len(chunk_content.split())

            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=chunk_content,
                page_start=page_start,
                page_end=page_end,
                section_title=active_section or f"Pages {page_start}-{page_end}",
                token_count=token_count,
                chunk_type="code" if has_code and current_words < 100 else "prose",
                is_informative=True,
            ))
            chunk_idx += 1

            # Backtrack for overlap
            if i < n and self.overlap_words > 0:
                words_back = 0
                step_back = 0
                while i - 1 - step_back >= 0 and words_back + sentence_records[i - 1 - step_back]["word_count"] <= self.overlap_words:
                    words_back += sentence_records[i - 1 - step_back]["word_count"]
                    step_back += 1
                i = max(0, i - step_back)

        return chunks
