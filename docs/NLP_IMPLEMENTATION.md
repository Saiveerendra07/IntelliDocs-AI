# IntelliDocs AI - NLP Algorithms & Implementation Details

This document provides mathematical formulations, algorithmic logic, and architectural locations for all genuine natural language processing techniques implemented in IntelliDocs AI.

---

## 1. Text Preprocessing Pipeline (`backend/app/nlp/preprocessing.py`)

1. **Text Normalization**: Unicode NFKC normalization, smart quote transformation, whitespace de-duplication, and hyphenation de-wrapping at line boundaries.
2. **Word & Sentence Tokenization**: NLTK punkt tokenization and spaCy sentence boundary detection.
3. **Stopword Filtering**: Extended NLTK English stopword lexicon with punctuation removal.
4. **Morphological Stemming**: Comparison of Porter Stemmer and Snowball (Porter2) Stemmer algorithms.
5. **Lemmatization**: spaCy rule-based and statistical lemmatizer (backed by WordNet dictionary).
6. **POS Tagging**: spaCy Universal POS tags (`NOUN`, `VERB`, `ADJ`, etc.) and Penn Treebank fine-grained tags (`NN`, `VBD`, `JJ`).
7. **Named Entity Recognition (NER)**: Statistical entity boundary extraction with standard categories (`PERSON`, `ORG`, `GPE`, `DATE`, `CARDINAL`, `EVENT`).
8. **N-gram Analysis**: Moving window extraction for unigrams, bigrams, and trigrams with Pointwise Mutual Information (PMI) scoring.

---

## 2. Extractive Summarization (`backend/app/nlp/extractive.py`)

All extractive summarization algorithms are implemented from scratch without black-box summarization packages:

### A. Frequency-Based Sentence Scoring
Sentences are scored based on the normalized frequency of their non-stopword tokens:
$$Score(S) = \frac{\sum_{w \in S} \text{Freq}(w)}{\text{len}(S)^\alpha}$$
where $\alpha$ is a length penalty parameter preventing overly long sentences from dominating.

### B. TF-IDF Sentence Ranking
Sentences are vectorized into TF-IDF space:
$$\text{TF-IDF}(t, d, D) = \text{TF}(t, d) \times \log\left(\frac{1 + |D|}{1 + |\{d \in D : t \in d\}|}\right) + 1$$
The sentence score is computed as the normalized sum of TF-IDF weights of its constituent terms.

### C. TextRank Graph Algorithm
Sentences form nodes in an undirected graph $G = (V, E)$. Edges between sentences $S_i$ and $S_j$ are weighted by cosine similarity between sentence vectors. Node importance is determined by PageRank iteration:
$$WS(V_i) = (1 - d) + d \sum_{V_j \in \text{In}(V_i)} \frac{w_{ji}}{\sum_{V_k \in \text{Out}(V_j)} w_{jk}} WS(V_j)$$
Top scoring sentences are selected and restored to original chronological document order.

---

## 3. Abstractive Summarization & Comparison (`backend/app/nlp/abstractive.py`)

- **Model**: `sshleifer/distilbart-cnn-12-6`
- **Map-Reduce Long Document Strategy**: Segments documents into context-bounded windows, generates chunk summaries, and reduces intermediate summaries through a final abstractive pass.
- **Extractive vs. Abstractive Comparison**: Evaluates ROUGE-1, ROUGE-2, and ROUGE-L overlap between the two summaries, alongside word-level compression ratio.

---

## 4. Keywords, Phrases & Topic Modeling (`backend/app/nlp/keywords.py`, `backend/app/nlp/topics.py`)

- **RAKE (Rapid Automatic Keyword Extraction)**: Custom implementation using stopword delimiters and degree-to-frequency co-occurrence ratios:
  $$\text{WordScore}(w) = \frac{\text{deg}(w)}{\text{freq}(w)}$$
- **TextRank Keyword Extraction**: Co-occurrence graph within sliding word windows.
- **LDA (Latent Dirichlet Allocation)**: Unsupervised generative probabilistic topic modeling via scikit-learn.
- **KMeans Semantic Chunk Clustering**: Clustering sentence embeddings with top TF-IDF cluster keywords.

---

## 5. Question Generation & Evaluation (`backend/app/nlp/qgen.py`)

- **MCQ Distractor Generation**: Nearest-neighbor search in semantic embedding space filtered by matching POS tags, excluding correct answer.
- **Rule-Based Question Patterns**: Cloze (fill-in-the-blank) key-entity masking and definition extraction.
- **Model-Assisted Generation**: FLAN-T5 generation for short/long answers and conceptual reasoning.
