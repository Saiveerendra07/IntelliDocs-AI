import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.nlp.preprocessing import NLPPreprocessor


class RAKEKeywordExtractor:
    """
    Rapid Automatic Keyword Extraction (RAKE) algorithm implemented from scratch:
    1. Splits text into candidate phrases using stop words and phrase delimiters.
    2. Builds a word co-occurrence graph within candidate phrases.
    3. Calculates word degree deg(w) and word frequency freq(w).
    4. Computes word score = deg(w) / freq(w).
    5. Scores candidate phrase as sum of member word scores.
    """
    def __init__(self):
        self.preprocessor = NLPPreprocessor()
        self.stop_words = self.preprocessor.stop_words

    def _split_sentences_into_phrases(self, text: str) -> List[List[str]]:
        # Split on sentence terminators and punctuation
        raw_phrases = re.split(r"[.!?,;:()\[\]{}\"\n]+", text.lower())
        candidate_phrases = []

        for p in raw_phrases:
            words = [w.strip() for w in re.findall(r"\b[a-zA-Z]{2,}\b", p) if w.strip()]
            current_phrase = []
            for w in words:
                if w in self.stop_words:
                    if current_phrase:
                        candidate_phrases.append(current_phrase)
                        current_phrase = []
                else:
                    current_phrase.append(w)
            if current_phrase:
                candidate_phrases.append(current_phrase)

        return candidate_phrases

    def extract_keywords(self, text: str, top_n: int = 15) -> List[Tuple[str, float]]:
        phrases = self._split_sentences_into_phrases(text)
        if not phrases:
            return []

        word_frequency = Counter()
        word_degree = Counter()

        for phrase in phrases:
            phrase_length = len(phrase)
            degree = phrase_length - 1
            for word in phrase:
                word_frequency[word] += 1
                word_degree[word] += degree

        for word in word_frequency:
            word_degree[word] += word_frequency[word]

        word_score = {}
        for word in word_frequency:
            word_score[word] = word_degree[word] / (word_frequency[word] + 1e-5)

        phrase_scores = {}
        for phrase in phrases:
            phrase_str = " ".join(phrase)
            if len(phrase) > 4:  # Skip excessively long phrases
                continue
            score = sum(word_score[word] for word in phrase)
            phrase_scores[phrase_str] = max(phrase_scores.get(phrase_str, 0.0), score)

        sorted_phrases = sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_phrases[:top_n]


class TextRankKeywordExtractor:
    """
    TextRank keyword extraction implemented from scratch:
    - Builds an undirected word co-occurrence graph within sliding window W=3
    - Applies PageRank power iteration
    - Extracts high-scoring lexical tokens and collates adjacent keyword sequences
    """
    def __init__(self, window_size: int = 3, damping: float = 0.85, max_iter: int = 50):
        self.window_size = window_size
        self.damping = damping
        self.max_iter = max_iter
        self.preprocessor = NLPPreprocessor()

    def extract_keywords(self, text: str, top_n: int = 15) -> List[Tuple[str, float]]:
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]
        words = [w for w in words if w not in self.preprocessor.stop_words]

        if not words:
            return []

        unique_words = sorted(list(set(words)))
        word_to_id = {w: i for i, w in enumerate(unique_words)}
        n = len(unique_words)

        if n <= 1:
            return [(words[0], 1.0)] if words else []

        # Build co-occurrence matrix
        cooc = np.zeros((n, n), dtype=np.float32)
        for i in range(len(words)):
            for j in range(i + 1, min(i + self.window_size, len(words))):
                id1 = word_to_id[words[i]]
                id2 = word_to_id[words[j]]
                if id1 != id2:
                    cooc[id1, id2] += 1.0
                    cooc[id2, id1] += 1.0

        # Degree normalize
        row_sums = cooc.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1e-10
        transition = cooc / row_sums

        scores = np.ones(n, dtype=np.float32) / n
        for _ in range(self.max_iter):
            prev = np.copy(scores)
            scores = (1 - self.damping) / n + self.damping * np.dot(transition.T, prev)
            if np.sum(np.abs(scores - prev)) < 1e-4:
                break

        ranked_indices = np.argsort(scores)[::-1]
        results = [(unique_words[i], float(scores[i])) for i in ranked_indices[:top_n]]
        return results


class TFIDFKeywordExtractor:
    def extract_keywords(self, text: str, top_n: int = 15) -> List[Tuple[str, float]]:
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
        if not sentences:
            sentences = [text]

        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=200,
            )
            tfidf = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            scores = np.asarray(tfidf.mean(axis=0)).flatten()
            ranked_indices = np.argsort(scores)[::-1]

            return [(feature_names[i], float(scores[i])) for i in ranked_indices[:top_n]]
        except Exception:
            words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]
            counts = Counter(words).most_common(top_n)
            return [(w, float(c)) for w, c in counts]


class HybridKeywordExtractor:
    """
    Ensemble Keyword Extractor combining RAKE, TextRank, and TF-IDF:
    - Normalizes scores to [0, 1]
    - Blends multi-algorithmic weights
    - Filters and deduplicates terms
    """
    def __init__(self):
        self.rake = RAKEKeywordExtractor()
        self.textrank = TextRankKeywordExtractor()
        self.tfidf = TFIDFKeywordExtractor()

    def extract(self, text: str, top_n: int = 15) -> List[Dict[str, Any]]:
        rake_items = self.rake.extract_keywords(text, top_n=top_n * 2)
        tr_items = self.textrank.extract_keywords(text, top_n=top_n * 2)
        tfidf_items = self.tfidf.extract_keywords(text, top_n=top_n * 2)

        def normalize(items):
            if not items:
                return {}
            max_val = max(s for _, s in items) if items else 1.0
            max_val = max_val if max_val > 0 else 1.0
            return {term.lower(): score / max_val for term, score in items}

        norm_rake = normalize(rake_items)
        norm_tr = normalize(tr_items)
        norm_tfidf = normalize(tfidf_items)

        all_terms = set(norm_rake.keys()) | set(norm_tr.keys()) | set(norm_tfidf.keys())
        blended = []

        for term in all_terms:
            s_rake = norm_rake.get(term, 0.0)
            s_tr = norm_tr.get(term, 0.0)
            s_tfidf = norm_tfidf.get(term, 0.0)

            # Combined weighted score
            final_score = (0.40 * s_rake) + (0.35 * s_tr) + (0.25 * s_tfidf)
            method = "Hybrid (RAKE+TextRank+TFIDF)"
            if s_rake > 0.7 and s_tr < 0.3:
                method = "RAKE"
            elif s_tr > 0.7 and s_rake < 0.3:
                method = "TextRank"
            elif s_tfidf > 0.7 and s_rake < 0.3:
                method = "TF-IDF"

            blended.append({
                "term": term.title(),
                "score": round(final_score, 3),
                "method": method,
            })

        blended.sort(key=lambda x: x["score"], reverse=True)
        return blended[:top_n]
