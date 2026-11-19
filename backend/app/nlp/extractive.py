import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.preprocessing import NLPPreprocessor


class FrequencySummarizer:
    def __init__(self):
        self.preprocessor = NLPPreprocessor()

    def summarize(self, text: str, num_sentences: int = 5) -> Tuple[str, List[str]]:
        sentences = split_into_sentences(text)
        if len(sentences) <= num_sentences:
            return text, sentences

        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        stopwords = self.preprocessor.stop_words
        content_words = [w for w in words if w not in stopwords]

        if not content_words:
            return " ".join(sentences[:num_sentences]), sentences[:num_sentences]

        counts = Counter(content_words)
        max_freq = max(counts.values())
        norm_freq = {w: c / max_freq for w, c in counts.items()}

        scores = []
        for idx, s in enumerate(sentences):
            s_words = re.findall(r"\b[a-zA-Z]{3,}\b", s.lower())
            if not s_words:
                scores.append((0.0, idx))
                continue

            score = sum(norm_freq.get(w, 0.0) for w in s_words) / (math.sqrt(len(s_words)) + 1e-5)
            # Positional bias: lead sentences receive a slight boost
            if idx == 0:
                score *= 1.25
            elif idx < 3:
                score *= 1.10

            scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        top_indices = sorted([idx for _, idx in scores[:num_sentences]])
        selected_sentences = [sentences[i] for i in top_indices]

        return " ".join(selected_sentences), selected_sentences


class TFIDFSummarizer:
    def summarize(self, text: str, num_sentences: int = 5) -> Tuple[str, List[str]]:
        sentences = split_into_sentences(text)
        if len(sentences) <= num_sentences:
            return text, sentences

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(sentences)
            # Score each sentence by the sum of its TF-IDF token weights normalized by length
            scores = []
            for idx in range(len(sentences)):
                row = tfidf_matrix.getrow(idx)
                if row.nnz == 0:
                    scores.append((0.0, idx))
                else:
                    score = row.sum() / math.sqrt(row.nnz)
                    if idx == 0:
                        score *= 1.25
                    scores.append((score, idx))

            scores.sort(key=lambda x: x[0], reverse=True)
            top_indices = sorted([idx for _, idx in scores[:num_sentences]])
            selected_sentences = [sentences[i] for i in top_indices]
            return " ".join(selected_sentences), selected_sentences

        except Exception:
            # Fallback to Frequency if TFIDF fails on sparse short text
            freq_summ = FrequencySummarizer()
            return freq_summ.summarize(text, num_sentences)


class TextRankSummarizer:
    """
    Genuine TextRank extractive summarization algorithm implemented from scratch:
    - Builds a complete sentence graph with cosine similarity on TF-IDF vectors
    - Runs PageRank power iteration with damping factor d=0.85
    - Extracts top ranked sentences preserving natural document order
    """
    def __init__(self, damping: float = 0.85, max_iter: int = 100, tol: float = 1e-4):
        self.damping = damping
        self.max_iter = max_iter
        self.tol = tol

    def summarize(self, text: str, num_sentences: int = 5) -> Tuple[str, List[str]]:
        sentences = split_into_sentences(text)
        n = len(sentences)
        if n <= num_sentences:
            return text, sentences

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform(sentences).toarray()

            # Compute pairwise cosine similarity matrix
            norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
            norms[norms == 0] = 1e-10
            normalized_tfidf = tfidf / norms
            sim_matrix = np.dot(normalized_tfidf, normalized_tfidf.T)
            np.fill_diagonal(sim_matrix, 0.0)

            # Eliminate negative values
            sim_matrix[sim_matrix < 0] = 0.0

            # Degree normalization for stochastic transition matrix
            row_sums = sim_matrix.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1e-10
            transition_matrix = sim_matrix / row_sums

            # PageRank power iteration
            scores = np.ones(n) / n
            for _ in range(self.max_iter):
                prev_scores = np.copy(scores)
                scores = (1 - self.damping) / n + self.damping * np.dot(transition_matrix.T, prev_scores)
                if np.sum(np.abs(scores - prev_scores)) < self.tol:
                    break

            ranked_indices = np.argsort(scores)[::-1]
            top_indices = sorted(ranked_indices[:num_sentences])
            selected_sentences = [sentences[i] for i in top_indices]

            return " ".join(selected_sentences), selected_sentences

        except Exception:
            freq_summ = FrequencySummarizer()
            return freq_summ.summarize(text, num_sentences)


def extract_definitions(text: str) -> List[Dict[str, str]]:
    """
    Extracts key term definitions matching academic explanation patterns.
    """
    patterns = [
        r"([A-Z][a-zA-Z\s]{2,30})\s+is\s+defined\s+as\s+([^.]+)\.",
        r"([A-Z][a-zA-Z\s]{2,30})\s+refers\s+to\s+([^.]+)\.",
        r"([A-Z][a-zA-Z\s]{2,30})\s+is\s+a\s+subfield\s+of\s+([^.]+)\.",
        r"([A-Z][a-zA-Z\s]{2,30})\s+is\s+(?:a|an)\s+([^.]+(?:technique|mechanism|architecture|framework|method|model)[^.]*)\.",
    ]

    definitions = []
    for pat in patterns:
        matches = re.findall(pat, text, flags=re.IGNORECASE)
        for term, meaning in matches:
            clean_term = term.strip().title()
            clean_meaning = meaning.strip()
            if len(clean_term) > 2 and len(clean_meaning) > 5:
                definitions.append({"term": clean_term, "definition": clean_meaning})

    # Deduplicate by term
    seen = set()
    deduped = []
    for d in definitions:
        if d["term"].lower() not in seen:
            seen.add(d["term"].lower())
            deduped.append(d)

    return deduped[:10]


def extract_key_points(sentences: List[str]) -> List[str]:
    """Formats key takeaway bullet points from selected sentences."""
    points = []
    for s in sentences:
        clean = s.strip()
        if len(clean) > 20:
            points.append(clean)
    return points[:8]
