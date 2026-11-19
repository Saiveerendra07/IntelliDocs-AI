import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.extractive import extract_definitions
from backend.app.nlp.keywords import RAKEKeywordExtractor


class SM2SpacedRepetition:
    """
    SuperMemo SM-2 Spaced Repetition Algorithm:
    - Calculates review intervals, repetition counts, and easiness factor (EF >= 1.3).
    - Maps 0-5 performance ratings or semantic difficulty marks (easy, medium, difficult).
    """
    @staticmethod
    def map_difficulty_to_rating(difficulty: Optional[str]) -> int:
        if not difficulty:
            return 4
        d = difficulty.lower().strip()
        if d in ("easy", "perfect", "5"):
            return 5
        elif d in ("good", "medium", "4"):
            return 4
        elif d in ("pass", "hard", "difficult", "3"):
            return 3
        elif d in ("fail", "2"):
            return 2
        elif d in ("blackout", "0"):
            return 0
        return 4

    @classmethod
    def calculate_next_review(
        cls,
        rating: int,
        repetitions: int = 0,
        easiness_factor: float = 2.5,
        interval: int = 1,
    ) -> Tuple[int, float, int, datetime]:
        """
        Calculates the next review schedule based on SuperMemo SM-2:
        Returns: (repetitions, easiness_factor, interval_days, next_review_datetime)
        """
        # Clamp rating between 0 and 5
        q = max(0, min(5, rating))

        # 1. Calculate repetitions and interval
        if q < 3:
            # Failed recall: reset repetitions count and schedule for tomorrow
            new_repetitions = 0
            new_interval = 1
        else:
            # Successful recall
            if repetitions == 0:
                new_interval = 1
            elif repetitions == 1:
                new_interval = 6
            else:
                new_interval = max(1, int(math.ceil(interval * easiness_factor)))
            new_repetitions = repetitions + 1

        # 2. Update Easiness Factor (EF)
        # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        new_ef = easiness_factor + delta_ef
        new_ef = max(1.3, round(new_ef, 3))

        # 3. Next review timestamp
        next_review_at = datetime.now(timezone.utc) + timedelta(days=new_interval)

        return new_repetitions, new_ef, new_interval, next_review_at


class FlashcardGenerator:
    """
    Automatic Flashcard Generator:
    - Extracts definitions and key conceptual statements from document text chunks.
    - Generates balanced prompt-answer pairs with page citations.
    """
    def __init__(self):
        self.rake = RAKEKeywordExtractor()

    def generate_flashcards(self, chunks: List[Any], max_cards: int = 10) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        all_text = ""
        chunk_sentences = []
        for c in chunks:
            c_text = c.text if hasattr(c, "text") else c["text"]
            c_page = getattr(c, "page_start", 1) if hasattr(c, "page_start") else c.get("page_start", 1)
            c_sec = getattr(c, "section_title", "") if hasattr(c, "section_title") else c.get("section_title", "")

            sents = split_into_sentences(c_text)
            for s in sents:
                s_clean = s.strip()
                if len(s_clean.split()) >= 6:
                    chunk_sentences.append({
                        "sentence": s_clean,
                        "page": c_page,
                        "section": c_sec,
                    })
            all_text += " " + c_text

        cards = []
        seen_terms = set()

        # 1. Extract from explicit definitions
        definitions = extract_definitions(all_text)
        for d in definitions:
            term = d["term"].strip()
            if term.lower() in seen_terms:
                continue
            seen_terms.add(term.lower())

            # Find page for this term
            page = 1
            topic = "Core Definitions"
            for item in chunk_sentences:
                if term.lower() in item["sentence"].lower():
                    page = item["page"]
                    if item["section"]:
                        topic = item["section"]
                    break

            cards.append({
                "topic": topic,
                "front": f"Define and describe the function of '{term}'.",
                "back": f"{d['definition']}\n\n*Reference: Page {page}*",
                "source_page": page,
                "difficulty_mark": "medium",
            })
            if len(cards) >= max_cards:
                return cards

        # 2. Extract from salient keywords and sentences
        keywords = [kw for kw, _ in self.rake.extract_keywords(all_text, top_n=20)]
        for item in chunk_sentences:
            if len(cards) >= max_cards:
                break
            sent = item["sentence"]
            matched_kw = None
            for kw in keywords:
                if kw.lower() in sent.lower() and kw.lower() not in seen_terms:
                    matched_kw = kw
                    break

            if matched_kw:
                seen_terms.add(matched_kw.lower())
                cards.append({
                    "topic": item["section"] or "Key Concepts",
                    "front": f"What is the significance of {matched_kw} in this context?",
                    "back": f"{sent}\n\n*Reference: Page {item['page']}*",
                    "source_page": item["page"],
                    "difficulty_mark": "medium",
                })

        return cards
