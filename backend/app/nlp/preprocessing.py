import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, SnowballStemmer, WordNetLemmatizer
import spacy

from backend.app.core.logging import logger

# Lazy singleton for spaCy model
_SPACY_NLP = None


def get_spacy_nlp():
    global _SPACY_NLP
    if _SPACY_NLP is None:
        try:
            _SPACY_NLP = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"Could not load spacy en_core_web_sm: {e}. Falling back to blank English.")
            _SPACY_NLP = spacy.blank("en")
    return _SPACY_NLP


def count_syllables_word(word: str) -> int:
    """Heuristic syllable counter for English words."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    # Remove non-alpha
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 1
    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    if word.endswith("e") and not word.endswith("le") and count > 1:
        count -= 1
    return max(1, count)


def compute_readability_metrics(text: str, words: List[str], sentences_count: int) -> Dict[str, Any]:
    """
    Computes standard academic readability formulas:
    - Flesch Reading Ease
    - Flesch-Kincaid Grade Level
    - Gunning Fog Index
    - Coleman-Liau Index
    - Automated Readability Index (ARI)
    - Type-Token Ratio (TTR)
    """
    word_count = len(words)
    if word_count == 0:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_reading_ease_label": "N/A",
            "flesch_kincaid_grade": 0.0,
            "gunning_fog": 0.0,
            "coleman_liau": 0.0,
            "automated_readability_index": 0.0,
            "type_token_ratio": 0.0,
            "average_sentence_length": 0.0,
        }

    sentences_count = max(1, sentences_count)
    syllable_counts = [count_syllables_word(w) for w in words]
    total_syllables = sum(syllable_counts)
    complex_words = sum(1 for s in syllable_counts if s >= 3)
    letters_count = sum(len(w) for w in words)

    asl = word_count / sentences_count
    asw = total_syllables / word_count

    # 1. Flesch Reading Ease: 206.835 - (1.015 * ASL) - (84.6 * ASW)
    fre = 206.835 - (1.015 * asl) - (84.6 * asw)
    fre = max(0.0, min(100.0, round(fre, 2)))

    if fre >= 90:
        fre_label = "Very Easy (5th grade)"
    elif fre >= 80:
        fre_label = "Easy (6th grade)"
    elif fre >= 70:
        fre_label = "Fairly Easy (7th grade)"
    elif fre >= 60:
        fre_label = "Standard (8th-9th grade)"
    elif fre >= 50:
        fre_label = "Fairly Difficult (10th-12th grade)"
    elif fre >= 30:
        fre_label = "Difficult (College)"
    else:
        fre_label = "Very Difficult (Post-Graduate / Technical)"

    # 2. Flesch-Kincaid Grade Level: (0.39 * ASL) + (11.8 * ASW) - 15.59
    fkgl = (0.39 * asl) + (11.8 * asw) - 15.59
    fkgl = max(0.0, round(fkgl, 2))

    # 3. Gunning Fog: 0.4 * (ASL + 100 * (complex_words / word_count))
    gunning_fog = 0.4 * (asl + 100 * (complex_words / word_count))
    gunning_fog = max(0.0, round(gunning_fog, 2))

    # 4. Coleman-Liau: 0.0588 * L - 0.296 * S - 15.8 (L = letters per 100 words, S = sentences per 100 words)
    L = (letters_count / word_count) * 100
    S = (sentences_count / word_count) * 100
    coleman_liau = (0.0588 * L) - (0.296 * S) - 15.8
    coleman_liau = max(0.0, round(coleman_liau, 2))

    # 5. Automated Readability Index (ARI): 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43
    ari = (4.71 * (letters_count / word_count)) + (0.5 * asl) - 21.43
    ari = max(0.0, round(ari, 2))

    # 6. Type-Token Ratio (TTR)
    unique_words = len(set(w.lower() for w in words))
    ttr = round(unique_words / word_count, 4)

    return {
        "flesch_reading_ease": fre,
        "flesch_reading_ease_label": fre_label,
        "flesch_kincaid_grade": fkgl,
        "gunning_fog": gunning_fog,
        "coleman_liau": coleman_liau,
        "automated_readability_index": ari,
        "type_token_ratio": ttr,
        "average_sentence_length": round(asl, 2),
    }


class NLPPreprocessor:
    def __init__(self):
        self.nlp = get_spacy_nlp()
        self.porter = PorterStemmer()
        self.snowball = SnowballStemmer("english")
        self.lemmatizer = WordNetLemmatizer()

        try:
            self.stop_words = set(stopwords.words("english"))
        except Exception:
            self.stop_words = {
                "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
                "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
                "by", "can", "did", "do", "does", "doing", "don", "down", "during", "each", "few", "for",
                "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
                "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
                "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
                "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she",
                "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
                "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
                "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
                "why", "with", "you", "your", "yours", "yourself", "yourselves"
            }

    def clean_text(self, text: str) -> str:
        """Normalizes whitespace and removes unprintable control characters."""
        cleaned = re.sub(r"\s+", " ", text)
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", cleaned)
        return cleaned.strip()

    def process_full(self, text: str) -> Dict[str, Any]:
        """
        Runs comprehensive linguistic analysis on text using spaCy and NLTK.
        Produces token statistics, stems, lemmas, POS tags, NER, n-grams, and readability.
        """
        cleaned = self.clean_text(text)
        doc = self.nlp(cleaned[:100000])  # limit single pass to 100k chars for fast responsiveness

        raw_tokens = []
        filtered_tokens = []
        porter_stems = []
        snowball_stems = []
        lemmatized_tokens = []
        pos_tokens = []
        words_for_readability = []

        for token in doc:
            raw_tokens.append(token.text)
            if token.is_alpha:
                words_for_readability.append(token.text.lower())
                if token.lower_ not in self.stop_words and len(token.text) > 1:
                    filtered_tokens.append(token.text)
                    porter_stems.append(self.porter.stem(token.text))
                    snowball_stems.append(self.snowball.stem(token.text))
                    lemmatized_tokens.append(token.lemma_)

            pos_tokens.append({
                "text": token.text,
                "pos": token.pos_,
                "tag": token.tag_,
                "lemma": token.lemma_,
            })

        # Named Entities
        entities = []
        entity_counts = Counter()
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
            })
            entity_counts[ent.label_] += 1

        # N-grams (Unigrams, Bigrams, Trigrams)
        lower_filtered = [t.lower() for t in filtered_tokens]
        unigrams = Counter(lower_filtered).most_common(50)
        bigrams_raw = list(zip(lower_filtered[:-1], lower_filtered[1:])) if len(lower_filtered) > 1 else []
        bigrams = Counter([" ".join(bg) for bg in bigrams_raw]).most_common(50)
        trigrams_raw = list(zip(lower_filtered[:-2], lower_filtered[1:-1], lower_filtered[2:])) if len(lower_filtered) > 2 else []
        trigrams = Counter([" ".join(tg) for tg in trigrams_raw]).most_common(50)

        # Word frequency
        freq_list = [{"word": word, "count": count} for word, count in unigrams]

        # Readability
        sentences_count = len(list(doc.sents)) if doc.has_annotation("SENT_START") else max(1, len(re.split(r"[.!?]+", cleaned)))
        readability = compute_readability_metrics(cleaned, words_for_readability, sentences_count)

        # Overview statistics
        stats = {
            "total_tokens": len(raw_tokens),
            "unique_tokens": len(set(t.lower() for t in raw_tokens)),
            "content_tokens": len(filtered_tokens),
            "sentences_count": sentences_count,
            "entities_count": len(entities),
        }

        return {
            "sample_original": text[:500],
            "sample_cleaned": cleaned[:500],
            "stats": stats,
            "tokens": raw_tokens[:200],
            "filtered_tokens": filtered_tokens[:200],
            "porter_stems": porter_stems[:200],
            "snowball_stems": snowball_stems[:200],
            "lemmatized_sample": lemmatized_tokens[:200],
            "pos_tokens": pos_tokens[:300],
            "entities": entities,
            "entity_counts": dict(entity_counts),
            "unigrams": [{"phrase": u[0], "count": u[1]} for u in unigrams],
            "bigrams": [{"phrase": b[0], "count": b[1]} for b in bigrams],
            "trigrams": [{"phrase": t[0], "count": t[1]} for t in trigrams],
            "frequencies": freq_list,
            "readability": readability,
        }
