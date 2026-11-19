# IntelliDocs AI - Step-by-Step Demonstration Workflow

This presentation script guides examiners and evaluators through an end-to-end demonstration of the IntelliDocs AI platform.

---

## Quick Demo Launch Instructions

### 1. Start Database & Backend
Ensure PostgreSQL 16 is running, then in PowerShell:
```powershell
# In project root
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."

# Seed full demonstration database (user, documents, chunks, vectors, summaries, quiz, flashcards)
python scripts/seed_demo.py

# Launch FastAPI backend
uvicorn backend.app.main:app --reload --port 8000
```

### 2. Start Frontend
In a second PowerShell terminal:
```powershell
cd frontend
npm run dev
```
Navigate to `http://localhost:5173`.

### 3. Demo Credentials
- **Email**: `demo@intellidocs.ai`
- **Password**: `DemoUser123!`
- *(Or register any new account on the Signup screen; multi-tenant isolation guarantees independent data environments.)*

---

## Guided Tour Script

### Step 1: Authentication & Onboarding
1. Navigate to `http://localhost:5173/login`.
2. Review the split-screen violet brand showcase outlining the 5 core platform features.
3. Sign in using `demo@intellidocs.ai` / `DemoUser123!`.

### Step 2: Main Dashboard & Study Metrics
1. View the main dashboard displaying real-time metrics:
   - Study Streak: Active consecutive study days.
   - Total Documents Processed and Total Pages analyzed.
   - Average Quiz Accuracy and Weak Topic alerts (< 60% accuracy).
2. Inspect the Recent Documents list showing `os_virtual_memory_lecture.pdf`.

### Step 3: Document Ingestion & Multi-Format OCR
1. Go to the **Upload** page.
2. Drag and drop any PDF, DOCX, PPTX, TXT, CSV, or scanned image.
3. Observe the real-time processing status (`uploaded` -> `extracting` -> `ocr` -> `processing` -> `ready`) with character counts and page detection.

### Step 4: Interactive NLP Analysis
1. Navigate to **NLP Analysis**.
2. Explore the **Preprocessing** tab:
   - Original Text vs. Cleaned/Normalized Tokens.
   - Stopword removal statistics and vocabulary metrics.
   - Side-by-side morphological comparison: Porter Stemmer vs. Snowball Stemmer vs. spaCy Lemmatizer.
   - Readability indices: Flesch Reading Ease (2.63), Flesch-Kincaid Grade Level (17.97), Gunning Fog (22.31), Coleman-Liau (20.84), ARI (19.30), and Lexical Diversity (TTR = 0.75).
3. Switch to **POS Tagging**, **Named Entities**, **Word Frequency**, and **Keywords & Topics**.
4. Click on an extracted keyword (e.g., "Virtual Memory" or "Page Replacement") to view deep passage highlights.

### Step 5: Extractive vs. Abstractive Summaries
1. Navigate to **Summarize**.
2. Select **Extractive Summary** and choose between:
   - Frequency-based scoring
   - TF-IDF salience ranking
   - TextRank graph PageRank (pure Python implementation)
3. Switch summary mode: *Standard*, *Bullet Points*, *Exam-Oriented*, or *Chapter Summary*.
4. Select **Abstractive Summary** powered by `sshleifer/distilbart-cnn-12-6`.
5. Click **Compare** to view the side-by-side layout with ROUGE-1, ROUGE-2, and ROUGE-L overlap metrics and compression ratios.

### Step 6: Citation-Grounded RAG Chat (Ask AI)
1. Open **Chat (Ask AI)**.
2. Select `os_virtual_memory_lecture.pdf`.
3. Select an explanation mode from the segmented toggle:
   - *Beginner* (plain English intuitive explanation)
   - *Detailed/Technical* (in-depth architectural mechanics)
   - *Exam-Oriented* (key exam criteria, definitions, and formulas)
   - *Real-World Example* (practical OS engineering applications)
4. Ask: *"What is the difference between paging and segmentation?"*
5. Notice the answer with verbatim citations (`[os_virtual_memory_lecture.pdf, Page 1]`) and calibrated confidence score.
6. Ask an out-of-domain question to verify hallucination suppression (e.g., *"What is the capital of France?"*), observing the polite refusal.

### Step 7: Automatic Exam Question Generation
1. Navigate to **Generate Questions**.
2. Choose question types across 7 formats: Multiple Choice (MCQ), True/False, Fill-in-the-blank, Short Answer, Conceptual, Flashcard, or Long-form.
3. Select difficulty level: *Easy*, *Medium*, or *Hard*.
4. Inspect the generated questions, verify semantic distractors, and click **Save as Quiz**.

### Step 8: Interactive Timed Quiz System
1. Go to **Quizzes** and open the newly created or seeded quiz.
2. Start the quiz to launch the full-screen timed assessment view:
   - Live countdown timer.
   - Question Navigator grid with status pills (Answered, Unanswered, Marked for Review).
   - Instant autosave upon selecting options.
3. Complete the quiz and submit to view instant evaluation:
   - Overall score percentage.
   - Detailed question-by-question review with explanations and ground-truth citations.
   - Weak topic diagnostic detection identifying areas needing remediation (< 60%).

### Step 9: Pedagogical Study Assistant (Tutor)
1. Open the Study Assistant.
2. Experience 4 interactive tutor modes:
   - **Socratic Exploration**: Guiding through leading questions.
   - **Step-by-Step Simplification**: Decomposing complex topics into elementary chunks.
   - **Intuitive Analogies**: Relating concepts to everyday phenomena (e.g., paging as a library index).
   - **Misconception Detection**: Auditing flawed student assumptions against source documents.

### Step 10: Spaced Repetition Flashcards
1. Go to **Flashcards**.
2. Review interactive 3D flip flashcards automatically extracted from document definitions.
3. Rate recall quality on the SuperMemo SM-2 scale: *Again* (0), *Hard* (2), *Good* (3), *Easy* (5).
4. Observe the recalculated Easiness Factor ($EF \ge 1.3$) and scheduled next review date.

### Step 11: Learning Analytics & Mastery Dashboard
1. Visit **Learning Analytics**.
2. Review the aggregated telemetry:
   - Mastery percentage across distinct syllabus topics.
   - Radar and bar charts of performance distribution.
   - Weak topics alert table with targeted review links.
   - Study streak and daily revision cadence.
