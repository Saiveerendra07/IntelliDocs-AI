# IntelliDocs AI - NLP Evaluation Framework

This document outlines the evaluation framework, metrics, benchmark datasets, and empirical results for the IntelliDocs AI system.

---

## 1. Evaluation Methodology

All metrics reported in this document are computed live via `scripts/run_evaluation.py` against reproducible ground-truth test fixtures located in `backend/tests/fixtures/`. No synthetic or fabricated metrics are recorded.

---

## 2. Metric Formulations

### A. Information Retrieval (RAG Chunks)
- **Precision@k**: Proportion of retrieved chunks in top-$k$ that are relevant:
  $$\text{Precision@}k = \frac{|\text{Retrieved}_k \cap \text{Relevant}|}{k}$$
- **Recall@k**: Proportion of all relevant chunks captured in top-$k$:
  $$\text{Recall@}k = \frac{|\text{Retrieved}_k \cap \text{Relevant}|}{|\text{Relevant}|}$$
- **Mean Reciprocal Rank (MRR)**: Average of reciprocal ranks of the first relevant chunk:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$

### B. Answer Quality & Grounding
- **Semantic Answer Relevance**: Cosine similarity between embeddings of generated answer and gold reference answer.
- **ROUGE-1, ROUGE-2, ROUGE-L**: N-gram and longest common subsequence recall against gold references.
- **Faithfulness (Groundedness)**: Fraction of answer sentences strongly supported by retrieved source context.
- **Citation Precision**: Proportion of cited page/chunk references that correctly match the gold source pages.

---

## 3. Benchmark Dataset (`backend/tests/fixtures/`)
- **Domain**: Operating Systems Concepts (Paging, Virtual Memory, Deadlocks, Semaphore Synchronization).
- **Gold Set**: Annotated test set of 25 question-answer pairs with associated ground-truth chunk IDs and page numbers.
- **Evaluation Script**: `python scripts/run_evaluation.py` writes output to `docs/evaluation_results.json`.
