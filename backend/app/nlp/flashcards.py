import re
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.extractive import extract_definitions
from backend.app.nlp.keywords import RAKEKeywordExtractor
from backend.app.llm.factory import get_llm_provider
from backend.app.core.logging import logger

DISALLOWED_FLASHCARD_WORDS = (
    "it", "they", "we", "he", "she", "this", "that", "these", "those",
    "there", "here", "one", "however", "furthermore", "moreover", "considerations",
    "silberschatz", "korth", "sudarshan", "edition", "copyright", "db-book"
)


class SM2Scheduler:
    """
    SuperMemo SM-2 Spaced Repetition Algorithm Implementation.
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
        q = max(0, min(5, rating))
        if q < 3:
            new_repetitions = 0
            new_interval = 1
        else:
            if repetitions == 0:
                new_interval = 1
            elif repetitions == 1:
                new_interval = 6
            else:
                new_interval = max(1, int(math.ceil(interval * easiness_factor)))
            new_repetitions = repetitions + 1

        delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        new_ef = max(1.3, round(easiness_factor + delta_ef, 3))
        next_review_at = datetime.now(timezone.utc) + timedelta(days=new_interval)
        return new_repetitions, new_ef, new_interval, next_review_at


# Alias for backward compatibility with routers and tests
SM2SpacedRepetition = SM2Scheduler


class FlashcardGenerator:
    """
    Automatic Flashcard Generator:
    - Uses Gemini LLM when configured for conceptual question-answer cards.
    - Local fallback extracting definitions and core statements without reference artifacts.
    - Front: clear conceptual question or term. Back: complete 1-3 sentence explanation.
    - Separate source_page integer field and topic.
    """
    def __init__(self):
        self.rake = RAKEKeywordExtractor()
        self.llm = get_llm_provider()

    def generate_flashcards(self, chunks: List[Any], max_cards: int = 15) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        informative_chunks = [
            c for c in chunks
            if getattr(c, "is_informative", True)
            and len((c.text if hasattr(c, "text") else c["text"]).split()) >= 15
        ]
        if not informative_chunks:
            informative_chunks = chunks

        # Priority 1: Use LLM provider if external
        if self.llm.is_external:
            try:
                cards = self._generate_with_llm(informative_chunks, max_cards=max_cards)
                if cards and len(cards) >= min(max_cards, 5):
                    return cards[:max_cards]
            except Exception as e:
                logger.warning(f"LLM flashcard generation failed: {e}. Falling back to local generation.")

        # Priority 2: Local heuristic generation
        return self._generate_local(informative_chunks, max_cards=max_cards)

    def _generate_with_llm(self, chunks: List[Any], max_cards: int) -> List[Dict[str, Any]]:
        selected = chunks[:min(len(chunks), 10)]
        context_blocks = []
        for c in selected:
            c_text = c.text if hasattr(c, "text") else c["text"]
            c_page = getattr(c, "page_start", 1) if hasattr(c, "page_start") else c.get("page_start", 1)
            c_sec = getattr(c, "section_title", "") if hasattr(c, "section_title") else c.get("section_title", "")
            context_blocks.append(f"--- [Page {c_page} - {c_sec}] ---\n{c_text.strip()}")

        prompt = f"""You are an expert educator creating high-yield study flashcards from the provided document excerpts.
Create {max_cards} clear, substantive flashcards.

SOURCE CONTEXT:
{"\n\n".join(context_blocks)}

RULES:
1. Front must be a clear conceptual question or term (e.g. 'What is a view in SQL?', 'What is a socket address?').
2. Back must be a complete, correct 1-3 sentence definition or explanation based on the content.
3. NEVER generate cards about textbook authors (Silberschatz, Korth, Sudarshan), editions, copyright, or slide footers.
4. DO NOT use raw SQL code fragments or syntax as the card front.
5. Provide a topic and the integer source_page number.

OUTPUT FORMAT:
Return a JSON array of objects with this schema:
[
  {{
    "front": "What is a view in SQL?",
    "back": "A view is a virtual relation that is not physically stored in the database but is defined by an SQL query and computed when accessed.",
    "topic": "SQL Views",
    "source_page": 22,
    "difficulty_mark": "medium"
  }}
]
"""
        result = self.llm.generate_json(
            prompt=prompt,
            system_prompt="You are an academic flashcard generator. Output ONLY valid JSON.",
            max_tokens=3500,
        )
        if not isinstance(result, list):
            return []

        cards = []
        seen_fronts = set()
        for item in result:
            if not isinstance(item, dict):
                continue
            front = item.get("front", "").strip()
            back = item.get("back", "").strip()
            page = item.get("source_page", 1)
            topic = item.get("topic", "Core Concepts")

            if not front or not back or len(front) < 8 or len(back) < 15:
                continue

            front_low = front.lower()
            if any(fw in front_low for fw in DISALLOWED_FLASHCARD_WORDS):
                continue
            norm_front = re.sub(r"\W+", " ", front_low).strip()
            if norm_front in seen_fronts:
                continue
            seen_fronts.add(norm_front)

            cards.append({
                "front": front,
                "back": back,
                "topic": topic,
                "source_page": page,
                "difficulty_mark": item.get("difficulty_mark") or "medium",
                "provider_notice": self.llm.get_provider_notice(),
            })

        return cards

    def _generate_local(self, chunks: List[Any], max_cards: int) -> List[Dict[str, Any]]:
        all_text = ""
        chunk_sentences = []
        for c in chunks:
            c_text = c.text if hasattr(c, "text") else c["text"]
            c_page = getattr(c, "page_start", 1) if hasattr(c, "page_start") else c.get("page_start", 1)
            c_sec = getattr(c, "section_title", "") if hasattr(c, "section_title") else c.get("section_title", "")

            sents = split_into_sentences(c_text, exclude_code=True)
            for s in sents:
                s_clean = s.strip()
                word_count = len(s_clean.split())
                if word_count < 6 or word_count > 50:
                    continue
                first_word = s_clean.split()[0].lower()
                if first_word in DISALLOWED_FLASHCARD_WORDS:
                    continue

                chunk_sentences.append({
                    "sentence": s_clean,
                    "page": c_page,
                    "section": c_sec,
                    "word_count": word_count,
                })
            all_text += "\n\n" + c_text

        cards = []
        seen_terms: Set[str] = set()

        # Domain conceptual rules
        for item in chunk_sentences:
            if len(cards) >= max_cards:
                break
            s = item["sentence"]
            s_low = s.lower()
            page = item["page"]
            sec = item["section"]

            # SQL Views
            if "view" in s_low and ("virtual relation" in s_low or "not part of the logical model" in s_low) and "view" not in seen_terms:
                seen_terms.add("view")
                cards.append({
                    "topic": "SQL Views",
                    "front": "What is a View in SQL databases?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # Right Outer Join
            if "right outer join" in s_low and "right outer join" not in seen_terms:
                seen_terms.add("right outer join")
                cards.append({
                    "topic": "Join Expressions",
                    "front": "What does a Right Outer Join return in SQL?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # Natural Join
            if "natural join" in s_low and "matches tuples" in s_low and "natural join" not in seen_terms:
                seen_terms.add("natural join")
                cards.append({
                    "topic": "Join Expressions",
                    "front": "What is a Natural Join in SQL?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "easy",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # GRANT / Authorization
            if "grant" in s_low and ("privilege" in s_low or "authorization" in s_low) and "grant" not in seen_terms:
                seen_terms.add("grant")
                cards.append({
                    "topic": "Security & Authorization",
                    "front": "What is the function of the GRANT statement in SQL?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # Index
            if "index" in s_low and ("data structure" in s_low or "efficiently" in s_low) and "index" not in seen_terms:
                seen_terms.add("index")
                cards.append({
                    "topic": "Indexing",
                    "front": "What is the purpose of an Index in relational databases?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # Transport Layer: Socket Address
            if "socket address" in s_low and ("ip address" in s_low and "port number" in s_low) and "socket address" not in seen_terms:
                seen_terms.add("socket address")
                cards.append({
                    "topic": "Transport Layer",
                    "front": "What is a Socket Address in computer networking?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "easy",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # Port numbers / Well known ports
            if "well-known ports" in s_low and "well-known ports" not in seen_terms:
                seen_terms.add("well-known ports")
                cards.append({
                    "topic": "Port Ranges",
                    "front": "What are Well-Known Ports and what is their range?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "easy",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # RIP Hop Count
            if "number of networks that must be traversed" in s_low and "hop count" not in seen_terms:
                seen_terms.add("hop count")
                cards.append({
                    "topic": "RIP Routing",
                    "front": "What is the definition of Hop Count in network routing?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "easy",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # RIP Infinity
            if "infinity is defined as 16" in s_low and "infinity metric" not in seen_terms:
                seen_terms.add("infinity metric")
                cards.append({
                    "topic": "RIP Limits",
                    "front": "In RIP, what is the maximum hop count and what value represents infinity?",
                    "back": "The maximum valid route cannot exceed 15 hops; a hop count of 16 is defined as infinity (inaccessible network).",
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

            # OSPF Transient Link
            if "transient link is a network" in s_low and "transient link" not in seen_terms:
                seen_terms.add("transient link")
                cards.append({
                    "topic": "OSPF Link Types",
                    "front": "What is a Transient Link in OSPF?",
                    "back": s,
                    "source_page": page,
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

        # General definitions fallback
        if len(cards) < max_cards:
            definitions = extract_definitions(all_text)
            for d in definitions:
                if len(cards) >= max_cards:
                    break
                term = d["term"].strip()
                t_low = term.lower()
                if t_low in seen_terms or any(fw in t_low for fw in DISALLOWED_FLASHCARD_WORDS):
                    continue
                seen_terms.add(t_low)
                matched_page = 1
                for cs in chunk_sentences:
                    if t_low in cs["sentence"].lower():
                        matched_page = cs["page"]
                        break
                cards.append({
                    "topic": "Core Definitions",
                    "front": f"What is '{term}' in the context of this document?",
                    "back": d["definition"],
                    "source_page": matched_page,
                    "difficulty_mark": "easy",
                    "provider_notice": self.llm.get_provider_notice(),
                })

        # Final fallback from substantive sentences
        if len(cards) < max_cards and chunk_sentences:
            for item in chunk_sentences:
                if len(cards) >= max_cards:
                    break
                s = item["sentence"]
                words = s.split()
                if len(words) < 8 or s in seen_terms:
                    continue
                seen_terms.add(s)
                sec = item["section"] or "Core Principles"
                if any(fw in sec.lower() for fw in ("silberschatz", "korth", "sudarshan", "copyright", "edition", "©")):
                    sec = "Core Principles"
                cards.append({
                    "topic": sec,
                    "front": f"In {sec}, explain the principle: \"{' '.join(words[:4])}...\"",
                    "back": s,
                    "source_page": item["page"],
                    "difficulty_mark": "medium",
                    "provider_notice": self.llm.get_provider_notice(),
                })

        return cards[:max_cards]
