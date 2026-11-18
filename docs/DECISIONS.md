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
