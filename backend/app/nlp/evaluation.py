from typing import Dict, Any, List
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
