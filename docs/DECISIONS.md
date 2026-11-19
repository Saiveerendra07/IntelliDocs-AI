# IntelliDocs AI - Architecture & Technical Decisions Record (ADR)

This document tracks all key technical, architectural, and design decisions made throughout the development of IntelliDocs AI.

---

### DEC-001: Local Environment & Python / Node Version Alignment
- **Date**: 2026-11-18
- **Context**: The user's local machine is configured with Python 3.12.10, Node.js v24.14.1, and Git 2.50.1 on Windows 11.
- **Decision**: Target Python 3.12 and Node 24 natively. Pin compatible packages in `requirements.txt` and `package.json` ensuring no deprecated C-extensions break on Python 3.12.
- **Rationale**: Meets user environment constraint without requiring Python version switching while ensuring stable execution.

---

### DEC-002: Dual Database Strategy (PostgreSQL with SQLite Dev/Test Fallback)
- **Date**: 2026-11-18
- **Context**: The primary production and milestone target is PostgreSQL 15/16 with SQLAlchemy 2.x and Alembic. On clean local development machines or when Postgres service is not yet initialized or sandboxed, instant zero-configuration testing is essential.
- **Decision**: Configure SQLAlchemy models using cross-dialect types (`sa.JSON` which maps to native `JSONB` on PostgreSQL and JSON text on SQLite; UUID columns compatible with both). Allow `DATABASE_URL` to point to PostgreSQL by default, with automatic or configured fallback to SQLite for immediate sandbox tests.
- **Rationale**: Guarantees tests and local dev work instantly in sandboxed environments without requiring manual external database provisioning, while maintaining 100% PostgreSQL schema compatibility and migration readiness.

---

### DEC-003: Git Push and GitHub Authentication Handling
- **Date**: 2026-11-18
- **Context**: `git --version` verified Git 2.50.1. Remote is configured as `origin https://github.com/Saiveerendra07/IntelliDocs-AI.git`. However, `gh auth status` reports not logged in, and push attempts prompt for interactive authentication.
- **Decision**: Strictly adhere to the non-negotiable instruction: "If neither works, STOP pushing, tell the user exactly what is needed (e.g., gh auth login or a PAT/credential manager setup), keep committing locally and continue development. Do not invent URLs or claim access." Every milestone will be committed locally to `main` with its required conventional commit message, logged in `docs/PROGRESS.md`, and pushed once GitHub authentication is completed.
- **Rationale**: Avoids hanging background processes or fabricating push confirmations while preserving a complete, clean, verifiable local Git history.

---

### DEC-004: Pure Local NLP Algorithms Without External API Dependency
- **Date**: 2026-11-18
- **Context**: Course requirements stipulate genuine NLP algorithms implemented and applied locally (not a thin wrapper around OpenAI/Gemini).
- **Decision**: Implement all core algorithms from first principles:
  - Extractive summarization: Frequency-based, TF-IDF ranking, and TextRank graph algorithm (NetworkX PageRank).
  - Keyword extraction: TF-IDF, RAKE (implemented from scratch), TextRank keyword co-occurrence.
  - Question generation: Rule-based distractor generation via nearest-neighbor embedding and POS filtering, masking, and definition extraction.
  - Topic modeling: Scikit-learn LDA and KMeans chunk clustering.
  - LLM generation: HuggingFace transformers (`FLAN-T5`, `distilbart`) loaded locally on CPU/CUDA, with optional pluggable external providers (Gemini/OpenAI) disabled by default.
- **Rationale**: Academic rigor, 100% offline functionality, and full student control.

---

### DEC-005: Model Management & Memory Optimization (RTX 3050 4GB / 16GB RAM)
- **Date**: 2026-11-18
- **Context**: Hardware constraint: Intel Core i5, 16 GB RAM, NVIDIA RTX 3050 4 GB VRAM.
- **Decision**: Implement a singleton `ModelManager` with lazy loading, device auto-detection (`cuda` if >= 3 GB VRAM available, else `cpu`), FP16 precision on GPU, `torch.no_grad()`, and strict single-heavy-model resident policy (automatic memory eviction with `gc.collect()` and `torch.cuda.empty_cache()` before loading another model).
- **Rationale**: Prevents OutOfMemory errors and ensures responsive performance on both CPU and entry-level dedicated GPUs.

---

### DEC-006: PostgreSQL Database Verification & Alembic Migrations
- **Date**: 2026-11-19
- **Context**: Audit of database execution between SQLite fallback and real PostgreSQL 16.
- **Findings & Action**:
  - In earlier M05 development, the session layer fell back to SQLite (`backend/storage/intellidocs.db`) because local PostgreSQL authentication failed with default credentials.
  - With PostgreSQL 16 running and `.env` configured with user `intellidocs_user` and database `intellidocs`, Alembic migrations were generated (`2026_11_19_1024-bdd25604e9e5_initial_schema.py`) and executed with `alembic upgrade head` on `PostgresqlImpl`.
  - All 16 database tables (`users`, `documents`, `document_pages`, `document_chunks`, `nlp_analyses`, `summaries`, `conversations`, `chat_messages`, `generated_questions`, `quizzes`, `quiz_questions`, `quiz_attempts`, `quiz_responses`, `flashcards`, `learning_progress`, `activity_log`) were verified in PostgreSQL.
  - `test_database_and_cascades.py` was re-run and verified against PostgreSQL 16 (3 passed in 4.21s).

---

### DEC-007: Tesseract OCR Verification on Scanned Documents and Images
- **Date**: 2026-11-19
- **Context**: Verification of OCR execution against Tesseract v5.4.0 on Windows.
- **Findings & Action**:
  - M06 originally tested digital extractors (PyMuPDF vector text, docx, pptx, txt, csv).
  - Tesseract 5.4.0 was verified on PATH (`tesseract v5.4.0.20240606`).
  - Added dedicated OCR verification tests in `backend/tests/unit/test_ocr_processing.py`:
    1. A rendered PNG image passed through `ImageExtractor` with `pytesseract`.
    2. A synthetic scanned PDF (image embedded without digital text layer) passed through `PDFExtractor` triggering scanned-page detection and OCR fallback.
  - Both tests passed with real OCR extraction on Windows in 3.74s.

---

### DEC-008: Local Neural Model Execution Benchmarking (MiniLM & DistilBART)
- **Date**: 2026-11-19
- **Context**: Empirical benchmarking of local neural models (`all-MiniLM-L6-v2` and `sshleifer/distilbart-cnn-12-6`).
- **Findings & Benchmark Results**:
  - Both models were downloaded to local HuggingFace cache and benchmarked on real document passages.
  - Device used: CPU (`torch.cuda.is_available() == False` on installed PyTorch CPU build).
  - `all-MiniLM-L6-v2`:
    - Cold-start load: ~10.88s.
    - Warm inference: 12.46ms per query, producing 384-dimensional dense vectors.
  - `sshleifer/distilbart-cnn-12-6`:
    - Adapted for Transformers 5.x via `AutoModelForSeq2SeqLM` and `AutoTokenizer` inside `ModelManager`.
    - Cold-start load + download: ~16.03s.
    - Warm inference: 2.15s per passage (beam search, num_beams=2, max_length=60), producing true abstractive summary text.


---

## DEC-009: RAG Relevance Calibration, In-Document Distractor Generation, and Extraction Quality
- **Date**: 2026-11-19
- **Status**: Accepted & Verified
- **Context**: An empirical quality audit conducted on `RIP_OSPF.pptx` identified that off-topic queries (e.g. "explain virtual memory paging" on a routing document) produced weak answers with ungrounded citations, distractors in QGen were using canned synthetic patterns, flashcard bodies contained formatting artifacts like `*Reference: Page X*`, and PPTX title extraction duplicated header text across slides.
- **Decision**:
  1. **RAG Relevance Threshold Calibration**: Set `RELEVANCE_THRESHOLD_COSINE = 0.32` and `RELEVANCE_THRESHOLD_STRICT = 0.40`. Re-ranker and similarity pass evaluates dense cosine similarity between query and retrieved passages alongside lexical content overlap (`lexical_matches`). If cosine similarity is below 0.32, or below 0.40 without keyword overlap, the RAG engine immediately aborts retrieval and returns `I couldn't find this in the selected document(s).` with `confidence_score = 0.0` and `sources = []`.
  2. **In-Document Distractor Selection**: Eliminated all generic canned distractors. Distractors are strictly selected from other extracted terms, definitions, or numeric values of the same entity type occurring in the document, ranked by embedding similarity to the stem. Distractor terms are globally tracked across questions to enforce that no distractor is repeated across questions.
  3. **Meaningful Question Generation**: Questions are constructed from verified definitions, metrics, and algorithms. Pronoun subjects (`It`, `They`, `We`, `This`, etc.) and colon headings (`:-`) are discarded. Every question has single-page attribution and genuine source explanations.
  4. **Flashcard Hygiene**: Separated page references into a dedicated integer `source_page` field and stripped all `*Reference: Page*` strings from the flashcard back. Flashcards are capped to the top 10 highest-quality cards.
  5. **Presentation Chunking & PPTX Ingestion**: Fixed slide title duplication in `pptx.py`. In `chunking.py`, presentation slide boundaries are preserved as single-page chunks (`page_start == page_end`) to maintain 1:1 attribution for slide decks and avoid topic dilution.
  6. **Multi-Provider LLM Abstraction**: Implemented `backend/app/llm/` supporting `GEMINI_API_KEY` and `OPENAI_API_KEY` with explicit user notice (`provider_notice`) when external APIs are used, while maintaining 100% offline local synthesis.

---

## DEC-010: Document Cleaning Overhaul, Presentation Slide Chunking, Interactive One-by-One Quiz, and Grounded Multi-Model Synthesis
- **Date**: 2026-11-19
- **Status**: Accepted & Verified
- **Context**: A comprehensive evaluation across diverse slide decks (`ch4.pdf` - 58 pages, `RIP_OSPF.pptx` - 18 pages, `Unit 4 Transport Layer.pptx` - 95 pages) revealed repetitive slide footers (e.g., Silberschatz copyright, author watermarks, slide numbering `4.x`) contaminating generated questions, flashcard fronts, and summary prose. Furthermore, users required an engaging one-by-one interactive quiz UI with instant feedback and answer locking, while LLM integration required robust JSON generation with local offline fallback.
- **Decision**:
  1. **Document Cleaning & Frequency-Based Header/Footer Removal (`cleaner.py`)**:
     - Built `clean_pages()` calculating line frequency across all pages of a document. Any line occurring on $\ge 25\%$ of pages (such as copyright notices, publisher URLs, textbook titles, or course headers) is automatically removed as a repeated header/footer.
     - Added regex cleaning for textbook patterns (`©Silberschatz, Korth and Sudarshan`, `Database System Concepts`, `See www.db-book.com`, `End of Chapter X`, solitary numbers and `X.Y` slide counters).
     - Isolated SQL queries, code blocks (`CREATE`, `SELECT`, `FROM`, `WHERE`, `GRANT`, `REVOKE`, braces, semicolons) and tables into distinct chunk types so they are never parsed as prose definitions, never used as flashcard fronts, and preserved only as illustrative examples.
     - Dropped low-information slides (title slides, tables of contents, blank/transitional slides) from QGen, flashcards, and summary generation.
  2. **Presentation Slide Chunking & Attribution (`chunking.py`, `pdf.py`)**:
     - Presentation slides are chunked 1:1 with single-page boundaries (`page_start == page_end`) with slide titles attached directly to chunk headers (`## Slide Title\n\nContent`).
     - Sanitized `active_section` and `section_title` heuristics to explicitly reject header/copyright strings from becoming chunk topics.
  3. **Interactive One-by-One Quiz UI (`Quiz.jsx`, `QuestionGen.jsx`)**:
     - Upgraded the Quiz interface to a single-question interactive examination flow.
     - Features instant visual feedback on option selection: correct answers glow green with checkmark icons, incorrect selections glow red with X icons, other options dim out.
     - Enforced answer locking: once an option is selected, answers cannot be altered.
     - Integrated grounded explanation callout with source page citations upon answering.
     - Added a top question navigator chip bar showing current progress, answered status, and jump capabilities, with a detailed score summary breakdown upon completion.
  4. **Grounded Multi-Model Synthesis & Fault-Tolerant Fallback (`gemini.py`, `qgen.py`, `flashcards.py`, `abstractive.py`)**:
     - Updated LLM integration to use active Google Gemini models (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.8-flash`).
     - Enforced strict JSON schema output with single-repair retry on malformed JSON.
     - Increased generation token limits (`max_tokens=4000` for QGen, `3500` for Flashcards) to prevent truncated JSON tokens.
     - Implemented graceful fallback on timeouts, HTTP 429/503 errors, or offline environments: cleanly delegates to local offline models (DistilBART, sentence-transformers, rule-based extractive) with zero user crashes and a visible provider banner.
  5. **Structured Multi-Section Summarization & RAG Synthesis (`abstractive.py`, `rag.py`)**:
     - Enforced standardized 5-part structured summaries across both Gemini and local offline summarizers: Overview, Main Topics & Key Mechanisms, Key Definitions, Key SQL / Code Examples, and Exam Focus.
     - RAG Chat produces multi-tier structured answers (Direct Answer, Detailed Explanation, Document Example, and Sources), handles broad document overview intents, and rejects off-topic queries with 0 sources when relevance falls below calibrated cosine thresholds.

