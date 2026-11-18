# IntelliDocs AI - Model Inventory & Resource Management

IntelliDocs AI is designed to run locally on consumer hardware (Intel Core i5, 16 GB RAM, NVIDIA RTX 3050 4 GB VRAM or pure CPU). This document catalogs all models, their footprints, and memory management policies.

---

## 1. Model Registry

| Model Name | Hugging Face ID / Source | Purpose | Parameter Size | Disk Footprint | Peak RAM / VRAM | Default Device |
|---|---|---|---|---|---|---|
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Dense chunk & query vectorization for ChromaDB semantic search | ~22.7M | ~90 MB | ~120 MB RAM / 80 MB VRAM | CPU / CUDA |
| **Abstractive Summarizer** | `sshleifer/distilbart-cnn-12-6` | Abstractive document summarization & map-reduce condensation | ~306M | ~1.2 GB | ~1.6 GB RAM / 1.1 GB VRAM (FP16) | CPU / CUDA |
| **Question & Answer Generator** | `google/flan-t5-base` | Exam question generation, conceptual explanation & local RAG | ~248M | ~990 MB | ~1.4 GB RAM / 950 MB VRAM | CPU / CUDA |
| **Cross-Encoder Reranker (Optional)** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Secondary reranking of retrieved semantic chunks | ~22.7M | ~90 MB | ~150 MB RAM | CPU |
| **spaCy Language Model** | `en_core_web_sm` | Sentence segmentation, POS tagging, Dependency parsing, NER | - | ~13 MB | ~60 MB RAM | CPU |
| **NLTK Corpora** | `punkt`, `stopwords`, `wordnet` | Tokenization, stopword lists, lemmatization | - | ~25 MB | Minimal | CPU |

---

## 2. ModelManager Architecture (`backend/app/nlp/model_manager.py`)

To ensure stability on a 4 GB VRAM GPU or 16 GB system RAM:
1. **Lazy Loading**: Models are not loaded into memory at application startup. They are initialized only when an endpoint requiring that model is invoked.
2. **Strict Single-Heavy-Model Resident Policy**:
   - Only **one** generation or summarization model (`distilbart` OR `flan-t5`) is kept in active memory at any time.
   - When switching between tasks (e.g., from summarization to question generation), the resident model is automatically unloaded, followed by:
     ```python
     gc.collect()
     if torch.cuda.is_available():
         torch.cuda.empty_cache()
     ```
3. **Automatic Device Detection & Graceful Fallback**:
   - The system checks `torch.cuda.is_available()`. If available, it inspects free VRAM. If free VRAM < 3 GB, it runs on CPU to prevent CUDA `OutOfMemoryError`.
   - If an `OutOfMemoryError` occurs on GPU at runtime, the `ModelManager` catches it, clears GPU memory, falls back to CPU execution, and logs a descriptive notice.
4. **Offline Extractive Fallbacks**:
   - If local heavy models fail to load or system memory is constrained, the platform provides offline extractive fallbacks (TextRank summarization and rule-based sentence masking/distractors) so the user is never blocked.
