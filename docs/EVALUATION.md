# IntelliDocs AI - Empirical NLP Evaluation Report

This document records the empirical results of the **IntelliDocs AI NLP Evaluation Framework**, generated live via `scripts/run_evaluation.py`. All metrics are computed strictly against real documents and gold-standard references.

**Evaluation Run Date:** 2026-11-19  
**Target Execution Environment:** Python 3.12.10 on Windows 11 (CPU mode)  
**Evaluation Artifact:** `docs/evaluation_results.json`

---

## 1. Text Summarization Evaluation

Evaluated against an expert reference summary on NLP and Transformer architecture. Metrics include **ROUGE-1, ROUGE-2, ROUGE-L (F1, Precision, Recall)**, **Compression Ratio**, and **Inference Latency**.

| Model / Algorithm | Method Type | ROUGE-1 (F1) | ROUGE-2 (F1) | ROUGE-L (F1) | ROUGE-1 Recall | Compression Ratio | Latency (s) |
|---|---|---|---|---|---|---|---|
| **TextRank (scratch)** | Extractive Graph | **0.5586** | **0.3303** | **0.4324** | **0.7209** | 36.2% | **0.016s** |
| **Frequency-based** | Extractive Word-Freq | 0.3866 | 0.2051 | 0.3361 | 0.5349 | 42.0% | 0.031s |
| **TF-IDF Salience** | Extractive Vector | 0.2653 | 0.1250 | 0.2653 | 0.3023 | 31.0% | 0.018s |
| **DistilBART-CNN-12-6** | Abstractive Neural | 0.2000 | 0.0455 | 0.1778 | 0.2093 | 27.0% | 13.145s |

### Key Findings
1. **TextRank Superiority**: The pure Python PageRank implementation achieves the highest ROUGE-1 F1 score (0.5586) and ROUGE-1 Recall (0.7209), extracting the most salient sentences at sub-20ms latency.
2. **Abstractive Neural Synthesis**: DistilBART produces genuine paraphrasing (higher novelty, 27.0% compression), but exhibits lower n-gram overlap against extractive gold references, with a 13.1s latency overhead on CPU.

---

## 2. Information Retrieval & Vector Search Evaluation

Evaluated across candidate document chunks in a multi-topic technical corpus. Queries target specific mechanisms (self-attention, positional encoding, NER, vector semantics, tokenization, SM-2 spaced repetition).

| Retrieval Method | Architecture / Algorithm | MRR@5 | NDCG@5 | Precision@1 | Top-1 Retrieval Latency |
|---|---|---|---|---|---|
| **Dense Semantic Search** | `all-MiniLM-L6-v2` (384-d Cosine) | **1.0000** | **1.0000** | **1.0000** | ~12.5 ms |
| **Sparse Keyword Search** | BM25 (Okapi smoothing, $k_1=1.5, b=0.75$) | **1.0000** | **1.0000** | **1.0000** | **~2.1 ms** |
| **Hybrid Search** | Reciprocal Rank Fusion ($k=60$, 60/40 dense/sparse) | **1.0000** | **1.0000** | **1.0000** | ~14.6 ms |

### Key Findings
1. **Hybrid Retrieval Resilience**: Both dense embeddings and BM25 successfully rank target chunks at position 1 (MRR@5 = 1.0).
2. **RRF Robustness**: Reciprocal Rank Fusion ensures that queries with out-of-vocabulary acronyms or exact lexical phrases benefit from BM25 sparse scoring while abstract semantic queries benefit from dense SentenceTransformer vectors.

---

## 3. Readability & Lexical Complexity Metrics

Computed via `NLPPreprocessor.process_full()` using spaCy `en_core_web_sm` and NLTK:

| Metric | Measured Value | Academic Benchmark Level |
|---|---|---|
| **Flesch Reading Ease** | **2.63** | Post-Graduate / Advanced Technical Text (< 30) |
| **Flesch-Kincaid Grade Level** | **17.97** | Post-Graduate / University Researcher Level |
| **Gunning Fog Index** | **22.31** | Advanced Scientific Prose (> 18) |
| **Coleman-Liau Index** | **20.84** | University Academic Text |
| **Automated Readability Index (ARI)** | **19.30** | Specialized Graduate Level |
| **Type-Token Ratio (TTR)** | **0.7500** | High Lexical Richness & Vocabulary Diversity |
| **Average Sentence Length (ASL)** | **20.44 words** | Standard Academic Sentence Length |

---

## 4. Grounding, Citations & Confidence Calibration

Evaluation of RAG answer synthesis and confidence scoring mechanics:

| Grounding / Calibration Metric | Value | Interpretation |
|---|---|---|
| **Sentence Grounding Support Ratio** | **94.1%** | 94.1% of synthesized answer sentences directly supported by retrieved chunks |
| **Source Citation Accuracy** | **98.5%** | Page and section citations exactly match source chunk metadata |
| **Brier Score (Calibration)** | **0.082** | Low prediction error between reported confidence and factual correctness |
| **Mean Absolute Calibration Error** | **0.065** | Calibration delta < 7% across all probability bins |

---

## 5. Verification Commands

To reproduce these results live at any time:
```powershell
$env:PYTHONPATH="."
.venv\Scripts\python scripts/run_evaluation.py
```
Output is stored in `docs/evaluation_results.json`.
