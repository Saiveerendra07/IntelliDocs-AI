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
    Splits text into sentences. Attempts NLTK sent_tokenize,
    falling back to regular expressions if NLTK data is unavailable.
    """
    try:
        import nltk
        sentences = nltk.tokenize.sent_tokenize(text)
        if sentences:
            return sentences
    except Exception:
        pass

    # Regex-based fallback for sentence splitting
    sentence_end_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')
    raw_sentences = sentence_end_pattern.split(text.strip())
    cleaned = [s.strip() for s in raw_sentences if s.strip()]
    return cleaned if cleaned else [text.strip()]


class SentenceAwareChunker:
    def __init__(self, target_words: int = 250, overlap_words: int = 40):
        self.target_words = target_words
        self.overlap_words = overlap_words

    def chunk_pages(self, pages: List[PageContent]) -> List[DocumentChunk]:
        """
        Chunks a sequence of PageContent into overlapping chunks of target_words.
        Maintains start and end page tracking and section titles.
        """
        # Flatten page items into sentence records with page metadata
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

            # Calculate overlap backwards from j
            overlap_accum = 0
            step_back = 0
            while (j - 1 - step_back) > i and overlap_accum < self.overlap_words:
                overlap_accum += sentence_records[j - 1 - step_back]["word_count"]
                step_back += 1

            # Advance i
            if (j - step_back) > i:
                i = j - step_back
            else:
                i = j

        return chunks
