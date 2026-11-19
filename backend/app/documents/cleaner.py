import re
from collections import Counter
from typing import List, Set, Tuple, Dict, Any, Optional
from backend.app.documents.base import PageContent


# Regex patterns for watermarks, footers, headers, and slide numbering
COPYRIGHT_PATTERNS = [
    re.compile(r"^(?:©|copyright|\(c\)|all rights reserved).*", re.IGNORECASE),
    re.compile(r".*silberschatz,\s*korth\s*and\s*sudarshan.*", re.IGNORECASE),
    re.compile(r".*database\s+system\s+concepts.*(?:edition|ed\.).*", re.IGNORECASE),
    re.compile(r".*see\s+www\.db-book\.com.*", re.IGNORECASE),
    re.compile(r".*www\.db-book\.com.*", re.IGNORECASE),
]

SLIDE_NUMBER_PATTERNS = [
    re.compile(r"^\d+\.\d+$"),  # e.g. 4.2, 4.47, 10.15
    re.compile(r"^(?:slide|page)\s*\d+(?:\s*(?:of|\/|\-)\s*\d+)?$", re.IGNORECASE),
    re.compile(r"^\d+$"),  # standalone integer line
]

TERMINAL_PATTERNS = [
    re.compile(r"^(?:end\s+of\s+chapter|end\s+of\s+unit|end\s+of\s+module|end\s+of\s+slide\s+set).*", re.IGNORECASE),
    re.compile(r"^(?:thank\s+you|any\s+questions\s*\??|q\s*&\s*a\s*\??)$", re.IGNORECASE),
]

SQL_STATEMENT_PATTERNS = [
    re.compile(r"^\s*(?:create\s+(?:table|view|index|domain|schema|type|trigger|function))\b", re.IGNORECASE),
    re.compile(r"^\s*(?:select\s+.*from|select\s+\*)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:insert\s+into|update\s+.*set|delete\s+from)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:grant\s+.*to|revoke\s+.*from)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:alter\s+table|drop\s+(?:table|view|index))\b", re.IGNORECASE),
    re.compile(r"^\s*(?:with\s+.*as\s*\()\b", re.IGNORECASE),
]

SQL_KEYWORDS = {
    "select", "from", "where", "insert", "into", "update", "delete", "create",
    "table", "view", "index", "grant", "revoke", "alter", "drop", "join",
    "left", "right", "outer", "inner", "natural", "group", "by", "having",
    "order", "union", "intersect", "except", "values", "distinct", "check",
    "primary", "foreign", "key", "references", "cascade", "on"
}


def normalize_line_for_comparison(line: str) -> str:
    """Normalizes line text for frequency counting across pages."""
    text = line.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_repeated_lines(pages: List[PageContent], threshold: float = 0.25) -> Set[str]:
    """
    Identifies recurring header/footer lines that appear on more than
    threshold (default 25%) of pages across the document.
    """
    if len(pages) < 4:
        return set()

    total_pages = len(pages)
    line_counts = Counter()

    for page in pages:
        seen_on_this_page = set()
        for raw_line in page.text.splitlines():
            clean = raw_line.strip()
            if len(clean) > 2:
                norm = normalize_line_for_comparison(clean)
                if norm and norm not in seen_on_this_page:
                    seen_on_this_page.add(norm)
                    line_counts[norm] += 1

    repeated = set()
    for norm, count in line_counts.items():
        if (count / total_pages) >= threshold:
            # Protect common generic words if very short
            if len(norm.split()) > 1 or len(norm) > 10:
                repeated.add(norm)

    return repeated


def is_sql_or_code(text: str) -> bool:
    """Determines whether a block or sentence is SQL syntax or code."""
    text_strip = text.strip()
    for pat in SQL_STATEMENT_PATTERNS:
        if pat.search(text_strip):
            return True

    # Check keyword density in short blocks
    words = [w.lower().strip() for w in re.split(r"[^\w]", text_strip) if w.strip()]
    if len(words) >= 3:
        sql_word_count = sum(1 for w in words if w in SQL_KEYWORDS)
        if sql_word_count / len(words) >= 0.45:
            return True

    return False


def clean_page_lines(
    raw_text: str,
    repeated_lines: Set[str],
) -> Tuple[str, Optional[str], List[str], List[str]]:
    """
    Cleans lines of a single page:
    - Removes repeated headers/footers
    - Removes copyright, author, and book watermark lines
    - Removes slide numbering lines
    - Identifies slide title
    - Separates prose sentences from SQL/code examples
    Returns: (cleaned_text, slide_title, prose_sentences, code_blocks)
    """
    lines = raw_text.splitlines()
    cleaned_lines = []
    code_lines = []
    in_code_block = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue

        norm = normalize_line_for_comparison(line_strip)
        if norm in repeated_lines:
            continue

        # Check copyright / author / watermark patterns
        if any(pat.match(line_strip) for pat in COPYRIGHT_PATTERNS):
            continue

        # Check slide numbering patterns
        if any(pat.match(line_strip) for pat in SLIDE_NUMBER_PATTERNS):
            continue

        # Check terminal patterns
        if any(pat.match(line_strip) for pat in TERMINAL_PATTERNS):
            continue

        # Clean bullet glyphs
        l_bullet = re.sub(r"^[•\*\-\uf0a7\uf0b7\uf0e0]\s*", "", line_strip).strip()
        if not l_bullet:
            continue

        # Check if line begins a SQL block
        if is_sql_or_code(l_bullet) or l_bullet.startswith("(") or l_bullet.endswith(";"):
            code_lines.append(l_bullet)
        else:
            cleaned_lines.append(l_bullet)

    if not cleaned_lines and not code_lines:
        return "", None, [], []

    # Identify slide title: first non-code line if short and prominent
    slide_title = None
    if cleaned_lines:
        first_line = cleaned_lines[0]
        if len(first_line.split()) <= 8 and not first_line.endswith("."):
            slide_title = first_line
            # Keep as title, prose follows
            prose_candidates = cleaned_lines[1:]
        else:
            prose_candidates = cleaned_lines
    else:
        prose_candidates = []

    # Reassemble wrapped bullet lines into full coherent sentences
    prose_sentences = []
    current_clause = []
    for line in prose_candidates:
        if current_clause and (
            len(current_clause[-1]) < 35
            or current_clause[-1].endswith(":")
            or current_clause[-1].endswith(";-")
            or current_clause[-1].endswith(",")
        ):
            current_clause.append(line)
        elif current_clause and re.match(r"^[A-Z]", line) and current_clause[-1].endswith("."):
            prose_sentences.append(" ".join(current_clause))
            current_clause = [line]
        else:
            current_clause.append(line)

    if current_clause:
        prose_sentences.append(" ".join(current_clause))

    # Form formatted page text
    parts = []
    if slide_title:
        parts.append(slide_title)
    if prose_sentences:
        parts.append("\n\n".join(prose_sentences))
    if code_lines:
        parts.append("[Code/SQL Example]:\n" + "\n".join(code_lines))

    cleaned_full_text = "\n\n".join(parts)
    return cleaned_full_text, slide_title, prose_sentences, code_lines


def is_low_information_slide(
    slide_title: Optional[str],
    prose_sentences: List[str],
    code_lines: List[str],
    page_number: int,
    total_pages: int,
) -> bool:
    """
    Detects low-information slides (Title slide, Table of Contents, End of Chapter,
    or nearly blank slides) that must not generate questions or flashcards.
    """
    total_words = sum(len(s.split()) for s in prose_sentences) + sum(len(c.split()) for c in code_lines)

    # Page 1 title slide heuristic
    if page_number == 1 and total_words < 30:
        return True

    # Last page "End of Chapter" / "Questions?" heuristic
    if page_number >= total_pages - 1 and total_words < 25:
        return True

    # Table of contents / Outline slide
    title_lower = (slide_title or "").lower()
    if any(toc in title_lower for toc in ("table of contents", "outline", "topics", "chapter overview")):
        if len(prose_sentences) > 0 and all(len(s.split()) <= 6 for s in prose_sentences):
            return True

    # Bare slides with almost no words
    if total_words < 12 and not code_lines:
        return True

    return False
