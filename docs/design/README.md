# IntelliDocs AI - Design References & UI Mockups

> [!NOTE]
> The assets in this directory (`docs/design/`) are **authoritative design mockups and reference specifications**, NOT screenshots of working functionality.
> Genuine screenshots of the running application are maintained separately in `docs/screenshots/` captured via automated testing / Playwright from live database records and document processing.

## Authoritative Reference Overview

The primary visual reference is based on the 9 core interface designs:
1. **Login Screen**: Split brand panel with violet gradient + feature highlights and authentication form.
2. **Main Dashboard**: Metric tiles, recent documents list, learning progress ring, weak-topics and activity widgets.
3. **Document Upload & Processing**: Dashed drag-and-drop zone, file rows with real-time percentage progress and extraction status tags.
4. **Document Summarization**: Extractive vs. Abstractive comparison, length controls (Short, Medium, Detailed), bullet/chapter/exam modes, key takeaways & definitions.
5. **NLP Analysis**: Interactive tabs for Preprocessing (Original vs. Cleaned, Lemmatized tokens), POS Tagging, Named Entities, N-grams, Word Frequency, and Keywords & Topics with educational explanations.
6. **Document Q&A (RAG Chat)**: Split-screen document selector/passage viewer and conversational assistant with verbatim citations, confidence scores, and explanation mode switches.
7. **Automatic Question Generation**: Configuration drawer (difficulty, question type, count) and generated interactive cards (MCQ, True/False, Fill-in-the-blank, Short/Long-answer, Conceptual, Application-based).
8. **Interactive Quiz**: Real-time timer countdown, question progress bar, mark-for-review toggle, and full Question Navigator grid with legend states.
9. **Quiz Results & Learning Analytics**: Circular score gauge, topic-wise accuracy breakdowns, recommendations, and in-depth per-question rationale.

## Design System Tokens
- **Primary Brand Palette**: Deep Violet/Indigo (`#5B3FD0` to `#6D4AFF`)
- **Sidebar Surface**: Deep Dark Indigo (`#1E1546`)
- **Active Navigation Pill**: Light Violet highlight with white iconography
- **Main Surface**: Light grayish-violet (`#F6F5FB`) and clean white cards (`#FFFFFF`) with `rounded-xl` and subtle elevation shadows
- **Semantic Accents**: Success Green (`#10B981`), Amber/Review (`#F59E0B`), Danger Red (`#EF4444`), Info Blue (`#3B82F6`)
- **Typography**: Clean sans-serif (`Inter`, system-ui)
- **Dark Mode**: High-contrast slate/zinc palette maintaining the violet brand accents
