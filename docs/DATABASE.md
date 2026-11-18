# IntelliDocs AI - Database Architecture & ER Diagram

## 1. Relational Schema Design (PostgreSQL / SQLite)

All tables use UUID primary keys, explicit foreign key constraints with `ON DELETE CASCADE` for data hygiene, and automated timestamp tracking (`created_at`, `updated_at`).

### Entity-Relationship Diagram

```mermaid
erDiagram
    users ||--o{ documents : owns
    users ||--o{ conversations : initiates
    users ||--o{ quizzes : creates
    users ||--o{ quiz_attempts : takes
    users ||--o{ flashcards : studies
    users ||--o{ learning_progress : tracks
    users ||--o{ activity_log : generates

    documents ||--o{ document_pages : contains
    documents ||--o{ document_chunks : segments
    documents ||--o{ nlp_analyses : computes
    documents ||--o{ summaries : generates
    documents ||--o{ generated_questions : derives
    documents ||--o{ quizzes : organizes
    documents ||--o{ flashcards : defines

    conversations ||--o{ chat_messages : records

    quizzes ||--o{ quiz_questions : includes
    generated_questions ||--o{ quiz_questions : references
    quizzes ||--o{ quiz_attempts : executes
    quiz_attempts ||--o{ quiz_responses : answers
    quiz_questions ||--o{ quiz_responses : evaluates

    users {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        string theme
        jsonb preferences
        datetime last_login_at
        datetime created_at
        datetime updated_at
    }

    documents {
        uuid id PK
        uuid user_id FK
        string original_filename
        string stored_path
        string mime_type
        integer file_size
        string file_hash
        integer page_count
        string status
        text error_message
        string language
        boolean is_scanned
        float processing_progress
        datetime created_at
        datetime updated_at
    }

    document_pages {
        uuid id PK
        uuid document_id FK
        integer page_number
        text text
        boolean ocr_applied
        jsonb tables_json
        datetime created_at
    }

    document_chunks {
        uuid id PK
        uuid document_id FK
        integer chunk_index
        text text
        integer page_start
        integer page_end
        integer token_count
        string section_title
        string chroma_id
        datetime created_at
    }

    nlp_analyses {
        uuid id PK
        uuid document_id FK
        string kind
        jsonb result
        jsonb params
        datetime created_at
    }

    summaries {
        uuid id PK
        uuid document_id FK
        string method
        string length
        string mode
        text content
        jsonb key_points
        jsonb definitions
        string model_used
        datetime created_at
    }

    conversations {
        uuid id PK
        uuid user_id FK
        string title
        jsonb document_ids
        string explanation_mode
        datetime created_at
        datetime updated_at
    }

    chat_messages {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        jsonb sources
        datetime created_at
    }

    generated_questions {
        uuid id PK
        uuid user_id FK
        uuid document_id FK
        string type
        string difficulty
        string topic
        text question
        jsonb options
        string correct_answer
        text explanation
        uuid source_chunk_id
        integer page
        float quality_score
        datetime created_at
    }

    quizzes {
        uuid id PK
        uuid user_id FK
        uuid document_id FK
        string title
        jsonb config
        integer time_limit_seconds
        datetime created_at
    }

    quiz_questions {
        uuid id PK
        uuid quiz_id FK
        uuid generated_question_id FK
        integer position
    }

    quiz_attempts {
        uuid id PK
        uuid quiz_id FK
        uuid user_id FK
        datetime started_at
        datetime submitted_at
        float score
        integer total
        float accuracy
        integer time_taken_seconds
        string status
    }

    quiz_responses {
        uuid id PK
        uuid attempt_id FK
        uuid quiz_question_id FK
        string selected_answer
        boolean is_correct
        boolean marked_for_review
        integer time_spent
    }

    flashcards {
        uuid id PK
        uuid user_id FK
        uuid document_id FK
        string topic
        text front
        text back
        integer source_page
        string difficulty_mark
        integer review_count
        datetime last_reviewed_at
        datetime next_review_at
        datetime created_at
    }

    learning_progress {
        uuid id PK
        uuid user_id FK
        uuid document_id FK
        string topic
        integer attempts
        integer correct
        float accuracy
        datetime last_updated
    }

    activity_log {
        uuid id PK
        uuid user_id FK
        string type
        uuid ref_id
        jsonb metadata
        datetime created_at
    }
```

---

## 2. Vector Database Integration (ChromaDB)
- **Collection Name**: `chunks`
- **Embedding Dimensions**: 384 (via `all-MiniLM-L6-v2`)
- **Distance Metric**: Cosine Similarity (`hnsw:space=cosine`)
- **Metadata Fields**: `user_id`, `document_id`, `chunk_id`, `page_start`, `page_end`, `chunk_index`
- **Consistency Invariant**: Deleting a document from PostgreSQL cascades to delete all corresponding records from the ChromaDB collection.
