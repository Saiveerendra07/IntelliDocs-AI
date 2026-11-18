# IntelliDocs AI - REST API Documentation

Base URL: `/api/v1` (with root shortcuts `/health` and `/docs`)

---

## 1. System & Health Endpoints
- `GET /health` or `GET /api/v1/health`: System health status, version, device, and active environment.
- `GET /`: API entry point and documentation links.
- `GET /api/v1/system/models`: Resident models in memory, device information, and VRAM/RAM allocation.

---

## 2. Authentication & User Management (`/api/v1/auth`, `/api/v1/users`)
- `POST /api/v1/auth/register`: Register new student/teacher account.
- `POST /api/v1/auth/login`: Authenticate and receive JWT Bearer token.
- `POST /api/v1/auth/refresh`: Refresh JWT credentials.
- `GET /api/v1/users/me`: Fetch authenticated profile and user preferences.
- `PATCH /api/v1/users/me`: Update profile, default explanation mode, or theme.
- `POST /api/v1/users/me/password`: Secure password change.

---

## 3. Documents & Extraction (`/api/v1/documents`)
- `POST /api/v1/documents/upload`: Multi-file upload with MIME validation and background ingestion.
- `GET /api/v1/documents`: List user's documents with search, sorting, and pagination.
- `GET /api/v1/documents/{id}`: Detailed document metadata and chunk stats.
- `GET /api/v1/documents/{id}/status`: Polling endpoint for real-time extraction/OCR progress.
- `GET /api/v1/documents/{id}/pages`: Per-page extracted text, OCR markers, and tables.
- `GET /api/v1/documents/{id}/download`: Authenticated download of original file.
- `GET /api/v1/documents/{id}/export`: Export processed text, summaries, and keywords (JSON / MD / TXT).
- `DELETE /api/v1/documents/{id}`: Delete document, pages, chunks, ChromaDB vectors, and files.

---

## 4. NLP Analysis (`/api/v1/documents/{id}/nlp`)
- `POST /api/v1/nlp/preprocess`: Ad-hoc preprocessing endpoint for raw text snippets.
- `GET /api/v1/documents/{id}/nlp/preprocessing`: Tokenization, stemming, lemmatization, stopword removal stats.
- `GET /api/v1/documents/{id}/nlp/pos`: Part-of-speech tags (Universal and fine-grained tags).
- `GET /api/v1/documents/{id}/nlp/entities`: Named Entity Recognition (NER) entities, labels, and spans.
- `GET /api/v1/documents/{id}/nlp/ngrams`: Unigrams, bigrams, and trigrams with frequencies.
- `GET /api/v1/documents/{id}/nlp/frequency`: Word frequency distribution.
- `GET /api/v1/documents/{id}/nlp/keywords`: TF-IDF, RAKE, and TextRank extracted keywords and scores.
- `GET /api/v1/documents/{id}/nlp/topics`: LDA topics and KMeans semantic chunk clusters.
- `GET /api/v1/documents/{id}/search-term`: Find exact passages and occurrences for a term.

---

## 5. Text Summarization (`/api/v1/documents/{id}/summaries`)
- `POST /api/v1/documents/{id}/summaries/generate`: Generate summary (extractive: freq, tfidf, textrank; abstractive: distilbart).
- `GET /api/v1/documents/{id}/summaries`: List saved summaries for document.
- `GET /api/v1/documents/{id}/summaries/compare`: Extractive vs. abstractive comparison with ROUGE metrics.

---

## 6. Semantic Search & RAG Chat (`/api/v1/search`, `/api/v1/chat`)
- `POST /api/v1/search`: Dense + sparse hybrid passage retrieval with scores.
- `GET /api/v1/chat/conversations`: List active chat conversations.
- `POST /api/v1/chat/conversations`: Create new single or multi-document conversation.
- `GET /api/v1/chat/conversations/{id}/messages`: Fetch conversation history.
- `POST /api/v1/chat/conversations/{id}/ask`: Send question, retrieve passages, and generate grounded answer.

---

## 7. Question Generation, Quizzes & Flashcards
- `POST /api/v1/questions/generate`: Generate 7 question formats from document passages.
- `POST /api/v1/quizzes`: Create interactive quiz from selected generated questions.
- `GET /api/v1/quizzes/{id}`: Fetch quiz questions and configuration.
- `POST /api/v1/quizzes/{id}/attempts`: Start a timed quiz attempt.
- `POST /api/v1/attempts/{id}/submit`: Submit attempt responses and calculate scores.
- `GET /api/v1/attempts/{id}/results`: Detailed results, explanations, and topic performance.
- `GET /api/v1/flashcards`: List flashcards for document.
- `POST /api/v1/flashcards/generate`: Auto-generate flashcards from definitions and key terms.
- `PATCH /api/v1/flashcards/{id}/review`: Mark difficulty and update spaced-repetition schedule.

---

## 8. Learning Analytics (`/api/v1/analytics`)
- `GET /api/v1/analytics/overview`: Aggregated platform metrics and study streaks.
- `GET /api/v1/analytics/progress`: Score history and quiz trends over time.
- `GET /api/v1/analytics/weak-topics`: Weak-topic analysis (< 60% accuracy) with practice recommendations.
- `GET /api/v1/analytics/activity`: Recent activity feed.
