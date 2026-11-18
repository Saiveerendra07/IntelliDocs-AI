# IntelliDocs AI - Step-by-Step Demonstration Workflow

This presentation script guides examiners and evaluators through an end-to-end demonstration of the IntelliDocs AI platform.

---

## Demo Script

### Step 1: Authentication & Onboarding
1. Navigate to `http://localhost:5173/login`.
2. Review the split-screen violet brand showcase outlining the 5 core platform features.
3. Login using `demo@intellidocs.ai` or click "Sign Up" to register a new user.

### Step 2: Document Ingestion
1. Go to the **Upload** page.
2. Drag and drop the Operating Systems lecture notes (`os_lecture_notes.pdf`).
3. Observe live extraction progress (text extraction, table detection, OCR validation, sentence-aware chunking).

### Step 3: Interactive NLP Analysis
1. Navigate to **NLP Analysis**.
2. Explore the **Preprocessing** tab: Compare raw text vs. normalized tokens, stopword removal counts, Porter vs. Snowball stemming, and spaCy lemmatization.
3. Switch to **POS Tagging**, **Named Entities**, **Word Frequency**, and **Keywords & Topics**.
4. Click on an extracted keyword (e.g., "Virtual Memory") to trigger deep passage lookup with text highlights.

### Step 4: Extractive vs. Abstractive Summaries
1. Navigate to **Summarize**.
2. Select **Extractive Summary** with TextRank algorithm (Medium length).
3. Toggle to **Abstractive Summary** (DistilBART) in Exam-oriented mode.
4. Click **Compare** to inspect the side-by-side view with ROUGE-L overlap metrics and compression ratio.

### Step 5: Citation-Grounded RAG Chat
1. Open **Chat (Ask AI)** in split-screen mode.
2. Ask: *"What is the difference between paging and segmentation?"*
3. Notice the formatted answer with verbatim `[Page X]` citations and confidence score.
4. Switch explanation mode from *Beginner* to *Exam-Oriented* and ask a follow-up: *"What causes page thrashing?"*

### Step 6: Exam Question Generation & Interactive Quiz
1. Navigate to **Generate Questions**.
2. Configure 5 Multiple Choice Questions (Medium difficulty) on the Operating Systems document.
3. Verify distractors and explanations, then click **Save as Quiz**.
4. Start the interactive quiz: use the Question Navigator grid, toggle Mark for Review, and submit.
5. Review the results dashboard: circular score gauge, topic-wise accuracy, and targeted study recommendations.

### Step 7: Flashcards & Learning Analytics
1. Navigate to **Flashcards** to review auto-generated definition cards with flip animations.
2. Visit **Learning Analytics** to see learning progress, score trends, and weak-topic analysis.
