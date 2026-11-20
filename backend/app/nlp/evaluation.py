from typing import Dict, Any, List, Optional, Set
from rouge_score import rouge_scorer


def compute_rouge_scores(hypothesis: str, reference: str) -> Dict[str, Dict[str, float]]:
    """
    Computes standard ROUGE metrics (ROUGE-1, ROUGE-2, ROUGE-L)
    between a generated summary (hypothesis) and reference text.
    Returns: precision, recall, fmeasure for each metric.
    """
    if not hypothesis or not reference:
        return {
            "rouge1": {"precision": 0.0, "recall": 0.0, "fmeasure": 0.0},
            "rouge2": {"precision": 0.0, "recall": 0.0, "fmeasure": 0.0},
            "rougeL": {"precision": 0.0, "recall": 0.0, "fmeasure": 0.0},
        }

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = scorer.score(reference, hypothesis)

    return {
        "rouge1": {
            "precision": round(scores["rouge1"].precision, 4),
            "recall": round(scores["rouge1"].recall, 4),
            "fmeasure": round(scores["rouge1"].fmeasure, 4),
        },
        "rouge2": {
            "precision": round(scores["rouge2"].precision, 4),
            "recall": round(scores["rouge2"].recall, 4),
            "fmeasure": round(scores["rouge2"].fmeasure, 4),
        },
        "rougeL": {
            "precision": round(scores["rougeL"].precision, 4),
            "recall": round(scores["rougeL"].recall, 4),
            "fmeasure": round(scores["rougeL"].fmeasure, 4),
        },
    }


def compare_extractive_abstractive(
    source_text: str,
    extractive_summary: str,
    abstractive_summary: str,
) -> Dict[str, Any]:
    """
    Generates comparative analysis between extractive and abstractive summaries:
    - ROUGE against source text
    - Cross-agreement ROUGE between extractive and abstractive
    - Compression ratio and token length statistics
    """
    source_words = len(source_text.split())
    ext_words = len(extractive_summary.split())
    abs_words = len(abstractive_summary.split())

    ext_rouge = compute_rouge_scores(extractive_summary, source_text)
    abs_rouge = compute_rouge_scores(abstractive_summary, source_text)
    cross_rouge = compute_rouge_scores(abstractive_summary, extractive_summary)

    return {
        "extractive": {
            "word_count": ext_words,
            "compression_ratio": round(ext_words / max(1, source_words), 3),
            "rouge": ext_rouge,
        },
        "abstractive": {
            "word_count": abs_words,
            "compression_ratio": round(abs_words / max(1, source_words), 3),
            "rouge": abs_rouge,
        },
        "cross_agreement": {
            "rouge": cross_rouge,
        },
    }


def normalize_text_for_comparison(text: str) -> str:
    """Normalizes string for comparison: lowercase, strip punctuation, extra whitespace."""
    import re
    if not text:
        return ""
    t = text.lower().strip()
    # Strip leading option notation like "a.", "b)", "1."
    t = re.sub(r"^[a-d1-4][\.\)]\s*", "", t)
    # Strip articles
    t = re.sub(r"\b(a|an|the)\b", " ", t)
    # Strip non-alphanumeric except spaces
    t = re.sub(r"[^\w\s]", " ", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def evaluate_quiz_answer(
    question_type: str,
    user_answer: Optional[str],
    correct_answer: str,
    options: Optional[List[str]] = None,
    question_text: Optional[str] = None,
    explanation: Optional[str] = None,
    accepted_answers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Authoritative server-side answer evaluation across question types:
    - MCQ: exact/normalized option match
    - True/False: binary boolean match
    - Fill-in-the-blank: normalized, trimmed matching tolerant of minor typos and accepted synonyms
    - Short/Long answer: embedding similarity + keyword coverage with automated feedback
    """
    import difflib
    import re

    if not user_answer or not user_answer.strip():
        return {
            "is_correct": False,
            "score": 0.0,
            "feedback": "No answer provided.",
            "key_points_covered": [],
            "key_points_missed": [correct_answer] if correct_answer else [],
        }

    user_clean = normalize_text_for_comparison(user_answer)
    target_clean = normalize_text_for_comparison(correct_answer)
    q_type = (question_type or "mcq").lower()

    # 1. True / False
    if q_type in ("true_false", "boolean"):
        u_bool = user_clean in ("true", "t", "yes", "1", "correct")
        t_bool = target_clean in ("true", "t", "yes", "1", "correct")
        is_corr = (u_bool == t_bool)
        return {
            "is_correct": is_corr,
            "score": 1.0 if is_corr else 0.0,
            "feedback": "Correct boolean evaluation." if is_corr else f"Expected {correct_answer}.",
            "key_points_covered": [correct_answer] if is_corr else [],
            "key_points_missed": [] if is_corr else [correct_answer],
        }

    # 2. Fill-in-the-blank
    if q_type in ("fill_blank", "fill_in_blank"):
        # Check direct or variant match
        accepted_variants = [target_clean]
        if accepted_answers:
            for variant in accepted_answers:
                clean_v = normalize_text_for_comparison(variant)
                if clean_v and clean_v not in accepted_variants:
                    accepted_variants.append(clean_v)

        for part in re.split(r"[/|;,]", correct_answer.lower()):
            clean_part = normalize_text_for_comparison(part)
            if clean_part and clean_part not in accepted_variants:
                accepted_variants.append(clean_part)

        # Exact match with any variant
        if user_clean in accepted_variants:
            return {
                "is_correct": True,
                "score": 1.0,
                "feedback": "Exact match.",
                "key_points_covered": [correct_answer],
                "key_points_missed": [],
            }

        # Typo tolerance via SequenceMatcher ratio
        best_ratio = max(
            difflib.SequenceMatcher(None, user_clean, variant).ratio()
            for variant in accepted_variants
        )
        if best_ratio >= 0.82 or (len(user_clean) >= 4 and user_clean in target_clean):
            return {
                "is_correct": True,
                "score": 1.0,
                "feedback": f"Accepted with minor spelling variation (match score: {round(best_ratio * 100)}%).",
                "key_points_covered": [correct_answer],
                "key_points_missed": [],
            }

        return {
            "is_correct": False,
            "score": 0.0,
            "feedback": f"Incorrect. Expected: {correct_answer}",
            "key_points_covered": [],
            "key_points_missed": [correct_answer],
        }

    # 3. Short Answer & Long Answer
    if q_type in ("short_answer", "long_answer", "conceptual", "application"):
        # Keyword extraction from reference
        ref_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", target_clean))
        stop_words = {"this", "that", "with", "from", "have", "more", "also", "into", "some", "such"}
        key_terms = [w for w in ref_words if w not in stop_words]

        user_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", user_clean))
        covered_terms = [t for t in key_terms if t in user_words]
        missed_terms = [t for t in key_terms if t not in user_words]
        keyword_coverage = len(covered_terms) / max(1, len(key_terms))

        # Semantic similarity via MiniLM if available
        sim_score = keyword_coverage
        try:
            from backend.app.nlp.model_manager import get_model_manager
            embedder = get_model_manager().get_embedding_model()
            if embedder:
                import numpy as np
                emb_u = embedder.encode(user_answer, normalize_embeddings=True)
                emb_t = embedder.encode(correct_answer, normalize_embeddings=True)
                sim_score = float(np.dot(emb_u, emb_t))
        except Exception:
            pass

        final_score = round(max(sim_score, 0.70 * sim_score + 0.30 * keyword_coverage), 2)
        is_corr = final_score >= 0.40

        feedback = (
            f"Automatic estimate: {round(final_score * 100)}% conceptual alignment. "
            f"Key concepts covered: {', '.join(covered_terms[:3]) or 'none'}. "
            f"Points to improve: {', '.join(missed_terms[:3]) or 'none'}."
        )

        return {
            "is_correct": is_corr,
            "score": final_score,
            "feedback": feedback,
            "key_points_covered": covered_terms[:5],
            "key_points_missed": missed_terms[:5],
        }

    # 4. Standard Multiple Choice (MCQ)
    is_corr = (user_clean == target_clean)
    if not is_corr and options:
        # Check if user passed letter "A", "B", etc.
        user_raw = user_answer.strip().upper()
        if len(user_raw) == 1 and user_raw in "ABCD":
            idx = ord(user_raw) - ord("A")
            if 0 <= idx < len(options):
                selected_opt = normalize_text_for_comparison(options[idx])
                is_corr = (selected_opt == target_clean)

    return {
        "is_correct": is_corr,
        "score": 1.0 if is_corr else 0.0,
        "feedback": "Correct selection." if is_corr else f"Incorrect selection. Expected: {correct_answer}",
        "key_points_covered": [correct_answer] if is_corr else [],
        "key_points_missed": [] if is_corr else [correct_answer],
    }
