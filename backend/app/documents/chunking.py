import re
from typing import List, Optional
from pydantic import BaseModel
from backend.app.documents.base import PageContent


class DocumentChunk(BaseModel):
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    section_title: Optional[str] = None
    token_count: int


def split_into_sentences(text: str) -> List[str]:
    """
    Splits text into coherent sentences and statements.
    Handles bullet lists, slide text without trailing periods, and unicode arrows.
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

    # Process line-by-line to respect bullet points and list items
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    results = []

    for line in lines:
        # Strip leading bullet indicators (*, -, •, numbers like 1.)
        cleaned_line = re.sub(r"^[\*\-\•\d+\.]\s*", "", line).strip()
        if not cleaned_line:
            continue

        # If line has multiple internal sentences with periods
        try:
            import nltk
            sub_sents = nltk.tokenize.sent_tokenize(cleaned_line)
            for s in sub_sents:
                s_strip = s.strip()
                if s_strip:
                    results.append(s_strip)
        except Exception:
            # Fallback regex
            sentence_end_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')
            raw = sentence_end_pattern.split(cleaned_line)
            for r in raw:
                r_strip = r.strip()
                if r_strip:
                    results.append(r_strip)

    if not results:
        results = [text.strip()]

    return results


class SentenceAwareChunker:
    def __init__(self, target_words: int = 250, overlap_words: int = 40):
        self.target_words = target_words
        self.overlap_words = overlap_words

    def chunk_pages(self, pages: List[PageContent]) -> List[DocumentChunk]:
        """
        Chunks a sequence of PageContent into coherent units.
        For slide-based or short-page documents, keeps slide units coherent.
        For continuous multi-page documents, maintains target_words with overlap.
        """
        if not pages:
            return []

        # Check if document has slide-like or short-page structure
        content_pages = [p for p in pages if len(p.text.split()) >= 10 and not p.text.startswith("[Slide")]
        avg_words_per_page = (
            sum(len(p.text.split()) for p in content_pages) / max(1, len(content_pages))
            if content_pages else 0
        )
        is_slide_structure = len(pages) > 3 and avg_words_per_page < 160

        if is_slide_structure:
            return self._chunk_slides(pages)
        else:
            return self._chunk_continuous(pages)

    def _chunk_slides(self, pages: List[PageContent]) -> List[DocumentChunk]:
        """Preserves individual slides or tightly coupled slide pairs as chunks."""
        chunks: List[DocumentChunk] = []
        chunk_idx = 0
        pending_title = None

        for page in pages:
            text = page.text.strip()
            word_count = len(text.split())

            # Ignore empty slides
            if not text or text.startswith("[Slide") or word_count < 3:
                continue

            # If slide has very few words (< 15 words) and might be a title slide
            if word_count < 15:
                pending_title = page.section_title or text
                continue

            # Slide has meaningful content
            active_section = page.section_title or pending_title
            content_text = text
            if pending_title and pending_title not in content_text:
                content_text = f"{pending_title}\n\n{text}"
            pending_title = None

            token_count = len(content_text.split())
            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=content_text,
                page_start=page.page_number,
                page_end=page.page_number,
                section_title=active_section,
                token_count=token_count,
            ))
            chunk_idx += 1

        return chunks

    def _chunk_continuous(self, pages: List[PageContent]) -> List[DocumentChunk]:
        """Continuous sentence-aware sliding window chunking."""
        sentence_records = []
        for page in pages:
            sentences = split_into_sentences(page.text)
            for s in sentences:
                if s.strip():
                    sentence_records.append({
                        "sentence": s.strip(),
                        "page_number": page.page_number,
                        "section_title": page.section_title,
                        "word_count": len(s.split()),
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
            j = i

            while j < n:
                rec = sentence_records[j]

                # Do not cross section boundaries if current chunk already has meaningful content
                if (
                    rec["section_title"]
                    and active_section
                    and rec["section_title"] != active_section
                    and current_words >= 35
                ):
                    break

                current_sentences.append(rec["sentence"])
                current_words += rec["word_count"]
                page_end = rec["page_number"]
                if not active_section and rec["section_title"]:
                    active_section = rec["section_title"]

                j += 1
                if current_words >= self.target_words:
                    break

            chunk_text = " ".join(current_sentences)
            token_count = len(chunk_text.split())

            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=chunk_text,
                page_start=page_start,
                page_end=page_end,
                section_title=active_section,
                token_count=token_count,
            ))
            chunk_idx += 1

            if j >= n:
                break

            overlap_accum = 0
            step_back = 0
            while (j - 1 - step_back) > i and overlap_accum < self.overlap_words:
                overlap_accum += sentence_records[j - 1 - step_back]["word_count"]
                step_back += 1

            if (j - step_back) > i:
                i = j - step_back
            else:
                i = j

        return chunks
