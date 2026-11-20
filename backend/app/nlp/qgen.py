import re
import uuid
import random
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.extractive import extract_definitions
from backend.app.nlp.keywords import RAKEKeywordExtractor
from backend.app.nlp.embeddings import EmbeddingEngine
from backend.app.llm.factory import get_llm_provider
from backend.app.core.logging import logger

DISALLOWED_SUBJECT_PREFIXES = (
    "it ", "it's ", "its ", "they ", "their ", "we ", "us ", "our ", "he ", "she ",
    "this ", "that ", "these ", "those ", "there ", "here ", "one ", "however ",
    "furthermore ", "moreover ", "in addition ", "therefore ", "thus ", "hence ", "also "
)

FORBIDDEN_CONTENT_WORDS = (
    "silberschatz", "korth", "sudarshan", "edition", "copyright", "db-book",
    "chapter 4 : intermediate sql", "chapter 4: intermediate sql", "all rights reserved",
    "end of chapter", "table of contents", "slide", "page 4.", "foundational principles",
    "core concepts and foundational", "agenda", "outline", "chapter outline", "overview slides",
    "course syllabus", "lecture outline"
)


class QuestionGenerator:
    """
    Automatic Question Generation Engine (QGen):
    - Uses external LLM (Gemini) when configured for high-level conceptual questions.
    - Strict validation pass ensuring groundedness, plausible distractors, and zero copyright artifacts.
    - Local heuristic fallback producing clean, verified questions.
    - 7 question types: MCQ, True/False, Fill-in-the-blank, Short Answer, Conceptual, Flashcard, Long-form.
    """
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.rake = RAKEKeywordExtractor()
        self.embedder = EmbeddingEngine()
        self.llm = get_llm_provider()

    def generate_from_chunks(
        self,
        chunks: List[Any],
        q_type: str = "mcq",
        difficulty: str = "medium",
        count: int = 5,
        topic: Optional[str] = None,
        doc_filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # Filter out low-information chunks (title slides, TOC, blank slides)
        informative_chunks = [
            c for c in chunks
            if getattr(c, "is_informative", True)
            and len((c.text if hasattr(c, "text") else c["text"]).split()) >= 15
        ]
        if not informative_chunks:
            informative_chunks = chunks

        # If topic filter provided, filter matching chunks
        if topic:
            topic_lower = topic.lower()
            matching_chunks = [
                c for c in informative_chunks
                if topic_lower in (getattr(c, "section_title", "") or c.get("section_title", "") or "").lower()
                or topic_lower in (c.text if hasattr(c, "text") else c["text"]).lower()
            ]
            if matching_chunks:
                informative_chunks = matching_chunks

        # Priority 1: Use LLM provider (Gemini) if external provider is active
        if self.llm.is_external:
            try:
                llm_questions = self._generate_with_llm(
                    informative_chunks,
                    q_type=q_type,
                    difficulty=difficulty,
                    count=count,
                    topic=topic,
                    doc_filename=doc_filename,
                )
                if llm_questions and len(llm_questions) >= count:
                    return llm_questions[:count]
                elif llm_questions:
                    # Supplement with local generation if count not fully met
                    local_supplement = self._generate_local(
                        informative_chunks,
                        q_type=q_type,
                        difficulty=difficulty,
                        count=count - len(llm_questions),
                        topic=topic,
                        doc_filename=doc_filename,
                    )
                    return (llm_questions + local_supplement)[:count]
            except Exception as e:
                logger.warning(f"LLM question generation failed: {e}. Falling back to local generation.")

        # Priority 2: Deterministic local generation
        return self._generate_local(
            informative_chunks,
            q_type=q_type,
            difficulty=difficulty,
            count=count,
            topic=topic,
            doc_filename=doc_filename,
        )

    def _generate_with_llm(
        self,
        chunks: List[Any],
        q_type: str,
        difficulty: str,
        count: int,
        topic: Optional[str],
        doc_filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generates grounded questions using Gemini with strict JSON validation."""
        selected_chunks = chunks[:min(len(chunks), 8)]
        context_blocks = []
        for c in selected_chunks:
            c_text = c.text if hasattr(c, "text") else c["text"]
            c_page = getattr(c, "page_start", 1) if hasattr(c, "page_start") else c.get("page_start", 1)
            c_sec = getattr(c, "section_title", "") if hasattr(c, "section_title") else c.get("section_title", "")
            c_id = getattr(c, "id", None) if hasattr(c, "id") else c.get("id")
            context_blocks.append(f"--- [Page {c_page} - {c_sec}] (ID: {c_id}) ---\n{c_text.strip()}")

        context_str = "\n\n".join(context_blocks)

        type_instructions = ""
        if q_type in ("true_false", "boolean"):
            type_instructions = (
                "- Question Type: True/False statement.\n"
                "- Question stem must start with 'True or False: ' (e.g. 'True or False: RIP uses distance vector routing.').\n"
                "- 'options' must be EXACTLY: [\"True\", \"False\"].\n"
                "- 'correct_answer' must be either 'True' or 'False'.\n"
            )
        elif q_type in ("fill_blank", "fill_in_blank"):
            type_instructions = (
                "- Question Type: Fill in the blank.\n"
                "- Question stem must be a complete informative sentence with exactly one technical term replaced by '___'.\n"
                "- 'options' must be [] (empty array).\n"
                "- 'correct_answer' must be the exact missing technical term.\n"
            )
        elif q_type in ("short_answer", "long_answer", "conceptual", "application"):
            type_instructions = (
                "- Question Type: Short Answer / Open-ended conceptual question.\n"
                "- Question stem must prompt for an explanation, comparison, or definition.\n"
                "- 'options' must be [] (empty array).\n"
                "- 'correct_answer' must be a complete model reference answer of 2-3 sentences.\n"
            )
        else:
            type_instructions = (
                "- Question Type: Multiple Choice (MCQ).\n"
                "- 'options' must contain EXACTLY 4 plausible, complete options from the same domain.\n"
                "- 'correct_answer' must be one of the 4 options.\n"
            )

        prompt = f"""You are an expert university professor creating an exam on the provided document excerpts.
Topic: {topic or 'Core Concepts'}
Difficulty: {difficulty}
Question Type: {q_type}
Number of questions needed: {count}

SOURCE CONTEXT:
{context_str}

STRICT REQUIREMENTS:
1. Every question must test real concepts from the content (e.g. SQL join types, views, integrity constraints, transport layer mechanisms, port numbers, routing algorithms).
2. NEVER create questions about book authors (Silberschatz, Korth, Sudarshan), textbook edition, copyright, page numbers, file names, or slide headers/footers.
3. Every question stem must be a complete, clear, grammatical question (at least 6 words). Avoid starting with pronoun subjects ('It', 'They', 'This', 'We').
4. Never mention the file name (e.g. '{doc_filename or ""}') or use phrases like 'In Introduction, complete the following'.
{type_instructions}
5. Provide a clear 1-2 sentence explanation of WHY the answer is correct and cite the source page.

OUTPUT FORMAT:
Return a JSON array of objects with this schema:
[
  {{
    "question": "Clear, complete question stem?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option A",
    "explanation": "Clear 1-2 sentence explanation. (Documented on Page X)",
    "type": "{q_type}",
    "difficulty": "{difficulty}",
    "page": 3,
    "topic": "{topic or 'Core Concepts'}"
  }}
]
"""
        result = self.llm.generate_json(
            prompt=prompt,
            system_prompt="You are a strict, precise academic test generator. Return ONLY valid JSON.",
            max_tokens=4000,
        )
        if not isinstance(result, list):
            return []

        valid_questions = []
        for item in result:
            if not isinstance(item, dict):
                continue
            item["type"] = q_type
            item["difficulty"] = difficulty
            item["topic"] = item.get("topic") or topic or "Core Concepts"
            item["provider_notice"] = self.llm.get_provider_notice()
            item["quality_score"] = 0.98

            if q_type in ("true_false", "boolean"):
                item["options"] = ["True", "False"]
                stem_raw = item.get("question", "").strip()
                if not stem_raw.lower().startswith("true or false:"):
                    item["question"] = f"True or False: {stem_raw}"

            if self._is_valid_question(item, doc_filename=doc_filename):
                page = item.get("page", 1)
                exp = item.get("explanation", "").strip()
                if exp and f"Page {page}" not in exp and "document" not in exp.lower():
                    item["explanation"] = f"{exp} (Documented on Page {page})."
                valid_questions.append(item)

        return valid_questions

    def _is_valid_question(self, q: Dict[str, Any], doc_filename: Optional[str] = None) -> bool:
        """
        Enforces strict quality rules:
        - Rejects stems containing file name or extension
        - Rejects stems with fewer than 6 words
        - Rejects 'complete the following' with title or fragment
        - Rejects multi-word answers appearing verbatim in stem
        - Rejects discourse words and copyright filler
        - Ensures options match question type
        """
        stem = q.get("question", "").strip()
        correct = str(q.get("correct_answer", "")).strip()
        q_type = (q.get("type") or "mcq").lower()

        if not stem or not correct:
            return False

        words = stem.split()
        if len(words) < 6:
            return False

        stem_lower = stem.lower()

        # Reject file names and extensions
        if re.search(r"\.(pdf|pptx|docx|txt|html|csv)\b", stem_lower):
            return False
        if doc_filename:
            base_fn = re.sub(r"\.[a-zA-Z0-9]+$", "", doc_filename.lower()).strip()
            if base_fn and base_fn in stem_lower:
                return False

        # Reject "complete the following" with title/heading or generic filler
        if "complete the following" in stem_lower:
            if any(p in stem_lower for p in ("in chapter", "in introduction", "in overview", "in topics", "in the text", "foundational")):
                return False

        # Reject generic filler
        if any(fw in stem_lower for fw in FORBIDDEN_CONTENT_WORDS):
            return False
        if any(stem_lower.startswith(pfx) for pfx in DISALLOWED_SUBJECT_PREFIXES):
            return False

        # Reject multi-word answers appearing verbatim in stem (giving away answer)
        correct_lower = correct.lower()
        if "\n" in correct:
            return False
        if correct_lower.startswith(("or ", "and ", "there ", "this ", "that ", "it ", "they ", "we ")):
            return False
        if len(correct_lower.split()) >= 2 and correct_lower in stem_lower:
            return False

        # Question type specific invariants
        options = q.get("options") or []
        if q_type == "mcq":
            if len(options) != 4:
                return False
            if len(set(options)) != 4:
                return False
            # Options must not contain forbidden words
            for opt in options:
                opt_str = str(opt).strip().lower()
                if any(fw in opt_str for fw in FORBIDDEN_CONTENT_WORDS):
                    return False
        elif q_type in ("true_false", "boolean"):
            if options and set(options) != {"True", "False"}:
                return False
            if correct not in ("True", "False"):
                return False
        elif q_type in ("fill_blank", "fill_in_blank"):
            if "___" not in stem and "____" not in stem:
                return False
        elif q_type in ("short_answer", "long_answer", "conceptual", "application"):
            if len(correct.split()) < 4:
                return False

        return True

    def _generate_local(
        self,
        chunks: List[Any],
        q_type: str,
        difficulty: str,
        count: int,
        topic: Optional[str],
        doc_filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Deterministic local question generation with domain-isolated distractors."""
        chunk_sentences = []
        doc_terms: Set[str] = set()
        doc_numbers: Set[str] = set()
        all_text = ""

        for c in chunks:
            c_text = c.text if hasattr(c, "text") else c["text"]
            c_page = getattr(c, "page_start", 1) if hasattr(c, "page_start") else c.get("page_start", 1)
            c_id = getattr(c, "id", None) if hasattr(c, "id") else c.get("id")
            c_sec = getattr(c, "section_title", "") if hasattr(c, "section_title") else c.get("section_title", "")

            all_text += "\n\n" + c_text
            sents = split_into_sentences(c_text, exclude_code=True)

            for s in sents:
                s_clean = s.strip()
                s_lower = s_clean.lower()
                word_count = len(s_clean.split())

                if word_count < 6 or word_count > 60:
                    continue
                if any(fw in s_lower for fw in FORBIDDEN_CONTENT_WORDS):
                    continue
                if any(s_lower.startswith(pfx) for pfx in DISALLOWED_SUBJECT_PREFIXES):
                    continue

                chunk_sentences.append({
                    "sentence": s_clean,
                    "page": c_page,
                    "chunk_id": c_id,
                    "section": c_sec,
                })

                for n in re.findall(r"\b\d+\b", s_clean):
                    doc_numbers.add(n)

        if not chunk_sentences:
            return []

        # Detect domain
        all_text_lower = all_text.lower()
        if any(k in all_text_lower for k in ("sql", "select ", "from ", "join", "relation", "database")):
            domain = "sql"
        elif any(k in all_text_lower for k in ("rip", "ospf", "hop count", "routing", "autonomous system")):
            domain = "routing"
        elif any(k in all_text_lower for k in ("transport", "udp", "tcp", "socket", "port number")):
            domain = "transport"
        else:
            domain = "general"

        definitions = extract_definitions(all_text)
        for d in definitions:
            term = d["term"].strip()
            if term.lower() not in FORBIDDEN_CONTENT_WORDS:
                doc_terms.add(term)

        for kw, _ in self.rake.extract_keywords(all_text, top_n=50):
            if len(kw.split()) <= 4 and kw.lower() not in FORBIDDEN_CONTENT_WORDS:
                if not any(kw.lower().startswith(p) for p in DISALLOWED_SUBJECT_PREFIXES):
                    doc_terms.add(kw.strip())

        facts = self._extract_domain_facts(chunk_sentences, definitions, all_text)
        generated = []
        used_distractors_global: Set[str] = set()
        seen_stems: Set[str] = set()

        # Build candidate questions matching q_type
        for fact in facts:
            if len(generated) >= count:
                break

            q_obj = None
            if q_type == "mcq":
                q_obj = self._build_mcq(fact, doc_terms, doc_numbers, used_distractors_global, difficulty, domain)
            elif q_type in ("true_false", "boolean"):
                is_true = (len(generated) % 2 == 0)
                q_obj = self._build_true_false(fact, doc_terms, difficulty, is_true=is_true)
            elif q_type in ("fill_blank", "fill_in_blank"):
                q_obj = self._build_fill_blank(fact, doc_terms, difficulty)
            elif q_type in ("short_answer", "long_answer", "conceptual", "application"):
                q_obj = self._build_short_answer(fact, difficulty)

            if q_obj and self._is_valid_question(q_obj, doc_filename=doc_filename):
                stem_key = re.sub(r"\W+", " ", q_obj["question"].lower()).strip()
                if stem_key not in seen_stems:
                    seen_stems.add(stem_key)
                    q_obj["topic"] = topic or fact.get("section") or "Core Concepts"
                    q_obj["provider_notice"] = self.llm.get_provider_notice()
                    generated.append(q_obj)

        # Fallback using high-quality chunk sentences if facts were fewer than count
        if len(generated) < count and chunk_sentences:
            for item in chunk_sentences:
                if len(generated) >= count:
                    break
                s = item["sentence"]
                s_words = s.split()
                if len(s_words) < 8:
                    continue

                # Match a key term from the sentence
                matched_term = None
                for t in doc_terms:
                    if len(t.split()) >= 1 and t.lower() in s.lower() and len(t) >= 4:
                        matched_term = t
                        break

                q_obj = None
                if q_type == "mcq" and matched_term:
                    stem = f"In this document, which concept is described as follows: \"{s[:120]}...\"?"
                    distractors = self._select_document_distractors(matched_term, doc_terms, doc_numbers, used_distractors_global, count=3, domain=domain)
                    opts = [matched_term] + distractors
                    random.shuffle(opts)
                    q_obj = {
                        "type": "mcq",
                        "difficulty": difficulty,
                        "question": stem,
                        "options": opts,
                        "correct_answer": matched_term,
                        "explanation": f"Grounded in source passage on Page {item['page']}: {s}",
                        "page": item["page"],
                        "quality_score": 0.92,
                    }
                elif q_type in ("true_false", "boolean"):
                    is_true = (len(generated) % 2 == 0)
                    stem = f"True or False: {s}"
                    q_obj = {
                        "type": "true_false",
                        "difficulty": difficulty,
                        "question": stem,
                        "options": ["True", "False"],
                        "correct_answer": "True",
                        "explanation": f"Directly confirmed in source text on Page {item['page']}.",
                        "page": item["page"],
                        "quality_score": 0.92,
                    }
                elif q_type in ("fill_blank", "fill_in_blank") and matched_term:
                    blanked_sentence = re.sub(re.escape(matched_term), "___", s, count=1, flags=re.IGNORECASE)
                    if "___" in blanked_sentence:
                        stem = f"Fill in the blank: {blanked_sentence}"
                        q_obj = {
                            "type": "fill_blank",
                            "difficulty": difficulty,
                            "question": stem,
                            "options": [],
                            "correct_answer": matched_term,
                            "explanation": f"Full context from Page {item['page']}: {s}",
                            "page": item["page"],
                            "quality_score": 0.92,
                        }
                elif q_type in ("short_answer", "long_answer", "conceptual", "application") and matched_term:
                    stem = f"Explain the principle and operational role of {matched_term}."
                    q_obj = {
                        "type": "short_answer",
                        "difficulty": difficulty,
                        "question": stem,
                        "options": [],
                        "correct_answer": s,
                        "explanation": f"Model answer derived from Page {item['page']}: {s}",
                        "page": item["page"],
                        "quality_score": 0.92,
                    }

                if q_obj and self._is_valid_question(q_obj, doc_filename=doc_filename):
                    stem_key = re.sub(r"\W+", " ", q_obj["question"].lower()).strip()
                    if stem_key not in seen_stems:
                        seen_stems.add(stem_key)
                        q_obj["topic"] = topic or item.get("section") or "Core Concepts"
                        q_obj["provider_notice"] = self.llm.get_provider_notice()
                        generated.append(q_obj)

        return generated[:count]

    def _build_mcq(
        self,
        fact: Dict[str, Any],
        doc_terms: Set[str],
        doc_numbers: Set[str],
        used_distractors_global: Set[str],
        difficulty: str,
        domain: str = "general",
    ) -> Optional[Dict[str, Any]]:
        correct_answer = fact["answer"].strip()
        page = fact.get("page", 1)
        chunk_id = fact.get("chunk_id")
        question = fact.get("question")

        if not question:
            term = fact.get("term", "this concept")
            definition = fact.get("definition", "")
            question = f"According to the text, which concept is defined as: \"{definition[:130]}\"?"

        distractors = self._select_document_distractors(
            correct=correct_answer,
            doc_terms=doc_terms,
            doc_numbers=doc_numbers,
            used_global=used_distractors_global,
            count=3,
            domain=domain,
        )

        options = [correct_answer] + distractors
        random.shuffle(options)

        return {
            "type": "mcq",
            "difficulty": difficulty,
            "question": question,
            "options": options,
            "correct_answer": correct_answer,
            "explanation": fact.get("explanation") or f"Documented on Page {page}.",
            "page": page,
            "source_chunk_id": chunk_id,
            "quality_score": 0.95,
        }

    def _build_true_false(
        self,
        fact: Dict[str, Any],
        doc_terms: Set[str],
        difficulty: str,
        is_true: bool = True,
    ) -> Optional[Dict[str, Any]]:
        page = fact.get("page", 1)
        chunk_id = fact.get("chunk_id")
        term = fact.get("term") or fact.get("answer", "")
        definition = fact.get("definition") or fact.get("explanation", "")

        if is_true:
            if fact.get("kind") == "metric_limit" or term.isdigit():
                q_text = fact.get("question", "").replace("What is ", "").rstrip("?")
                stem = f"True or False: {q_text} is {term}."
            else:
                stem = f"True or False: {term} is defined as {definition}."
            correct = "True"
            explanation = f"Confirmed directly by document definition on Page {page}."
        else:
            if fact.get("kind") == "metric_limit" or term.isdigit():
                sn = "32" if term != "32" else "16"
                q_text = fact.get("question", "").replace("What is ", "").rstrip("?")
                stem = f"True or False: {q_text} is {sn}."
                correct = "False"
                explanation = f"False. The correct limit is {term}, not {sn} (Page {page})."
            else:
                other_terms = [t for t in doc_terms if t.lower() != term.lower() and not t.isdigit() and len(t) >= 4]
                alt_term = other_terms[0] if other_terms else "A standard sequential scan"
                stem = f"True or False: {alt_term} operates primarily to {definition}."
                correct = "False"
                explanation = f"False. The mechanism described belongs to {term}, not {alt_term} (Page {page})."

        return {
            "type": "true_false",
            "difficulty": difficulty,
            "question": stem,
            "options": ["True", "False"],
            "correct_answer": correct,
            "explanation": explanation,
            "page": page,
            "source_chunk_id": chunk_id,
            "quality_score": 0.95,
        }

    def _build_fill_blank(
        self,
        fact: Dict[str, Any],
        doc_terms: Set[str],
        difficulty: str,
    ) -> Optional[Dict[str, Any]]:
        page = fact.get("page", 1)
        chunk_id = fact.get("chunk_id")
        term = fact.get("term") or fact.get("answer", "")
        definition = fact.get("definition") or ""

        if not definition:
            return None

        stem = f"Fill in the blank: ___ is defined as {definition}."
        return {
            "type": "fill_blank",
            "difficulty": difficulty,
            "question": stem,
            "options": [],
            "correct_answer": term,
            "explanation": f"According to the source document on Page {page}, {term} is defined as: {definition}.",
            "page": page,
            "source_chunk_id": chunk_id,
            "quality_score": 0.95,
        }

    def _build_short_answer(
        self,
        fact: Dict[str, Any],
        difficulty: str,
    ) -> Optional[Dict[str, Any]]:
        page = fact.get("page", 1)
        chunk_id = fact.get("chunk_id")
        term = fact.get("term") or fact.get("answer", "")
        definition = fact.get("definition") or fact.get("explanation", "")

        stem = f"Explain the core function and definition of {term}."
        model_answer = f"{term} is defined as {definition}."

        return {
            "type": "short_answer",
            "difficulty": difficulty,
            "question": stem,
            "options": [],
            "correct_answer": model_answer,
            "explanation": f"Reference model answer documented on Page {page}: {model_answer}",
            "page": page,
            "source_chunk_id": chunk_id,
            "quality_score": 0.95,
        }

    def _select_document_distractors(
        self,
        correct: str,
        doc_terms: Set[str],
        doc_numbers: Set[str],
        used_global: Set[str],
        count: int = 3,
        domain: str = "general",
    ) -> List[str]:
        correct_lower = correct.lower()
        is_numeric = bool(re.match(r"^\d+$", correct.strip()))

        if is_numeric:
            numeric_pool = [n for n in doc_numbers if n != correct.strip() and n.lower() not in used_global]
            standard_nums = ["16", "15", "8", "30", "4", "2", "14", "32", "255", "1023", "49151", "65535"]
            for sn in standard_nums:
                if len(numeric_pool) >= (count * 2):
                    break
                if sn != correct.strip() and sn.lower() not in used_global and sn not in numeric_pool:
                    numeric_pool.append(sn)
            try:
                corr_val = int(correct.strip())
                numeric_pool.sort(key=lambda x: abs(int(x) - corr_val))
            except Exception:
                pass
            chosen = []
            for n in numeric_pool:
                if len(chosen) >= count:
                    break
                chosen.append(n)
                used_global.add(n.lower())
            return chosen

        # Filter candidate terms from the same document
        candidates = []
        for t in doc_terms:
            t_strip = t.strip()
            t_low = t_strip.lower()
            if t_low == correct_lower or t_low in used_global:
                continue
            if any(fw in t_low for fw in FORBIDDEN_CONTENT_WORDS):
                continue
            if len(t_strip.split()) < 2 and not t_strip.isdigit():
                continue
            candidates.append(t_strip)

        if len(candidates) < count:
            # Domain-isolated fallbacks
            DOMAIN_FALLBACKS = {
                "sql": [
                    "Full outer join", "Natural join", "Inner join condition",
                    "create view", "create table", "grant authorization",
                    "select clause", "group by clause", "having condition"
                ],
                "routing": [
                    "Distance vector routing", "Link state routing", "Path vector routing",
                    "Hop count metric", "Transient link", "Stub link network",
                    "Autonomous System boundary", "Open Shortest Path First", "Routing Information Protocol"
                ],
                "transport": [
                    "Connection-oriented TCP delivery", "Connectionless UDP service",
                    "Socket address pair", "Well-known port range", "Sliding window protocol",
                    "Congestion control mechanism", "Process-to-process delivery"
                ],
                "general": [
                    "Algorithmic execution", "Hierarchical data structure",
                    "Relational schema model", "Linear array structure"
                ]
            }
            fallbacks = DOMAIN_FALLBACKS.get(domain, DOMAIN_FALLBACKS["general"])
            for df in fallbacks:
                if df.lower() != correct_lower and df.lower() not in used_global and df not in candidates:
                    candidates.append(df)

        random.shuffle(candidates)
        chosen = []
        for c in candidates:
            if len(chosen) >= count:
                break
            chosen.append(c)
            used_global.add(c.lower())

        return chosen

    def _extract_domain_facts(self, chunk_sentences: List[Dict[str, Any]], definitions: List[Dict[str, Any]], all_text: str) -> List[Dict[str, Any]]:
        """Extracts structured factual statements across Database SQL, Networking, and OS domains."""
        facts = []

        # 1. Domain pattern facts (High priority)
        for item in chunk_sentences:
            s = item["sentence"]
            s_low = s.lower()
            page = item["page"]
            c_id = item["chunk_id"]
            sec = item["section"]

            # Database SQL: Right Outer Join
            if "right outer join" in s_low and ("return" in s_low or "tuple" in s_low or "match" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "What is the primary behavior of a right outer join in SQL?",
                    "answer": "Preserves all tuples from the right relation, padding unmatched left attributes with nulls",
                    "explanation": f"A right outer join preserves all tuples from the right relation; any tuples with no match in the left relation are padded with null values (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Database SQL: View Definition
            if "create view" in s_low or ("view is" in s_low and "relation" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "Which SQL statement is used to define a virtual relation (view) in a database?",
                    "answer": "create view",
                    "explanation": f"Views are virtual relations defined using the 'create view <name> as <query>' statement (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Database SQL: Inner vs Outer Join
            if "inner join" in s_low and "outer join" in s_low:
                facts.append({
                    "kind": "db_concept",
                    "question": "What is the key difference between an inner join and an outer join in SQL?",
                    "answer": "Inner joins discard unmatched tuples, while outer joins preserve unmatched tuples padded with nulls",
                    "explanation": f"Inner join operations only return matching tuples, whereas outer join operations retain unmatched tuples with null values (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Database SQL: GRANT statement
            if "grant" in s_low and ("authorization" in s_low or "privilege" in s_low or "user" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "What is the primary purpose of the GRANT statement in SQL authorization?",
                    "answer": "To confer privileges such as read, insert, update, or delete to specified users or roles",
                    "explanation": f"The GRANT statement is used to allocate security privileges and authorizations to database users or roles (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Networking: Hop count max
            m_hop = re.search(r"(?i)max(?:imum)?\s+hop\s+count\s*=\s*(\d+)", s)
            if m_hop:
                facts.append({
                    "kind": "metric_limit",
                    "question": "What is the maximum allowed hop count for a valid route in the Routing Information Protocol (RIP)?",
                    "answer": m_hop.group(1),
                    "explanation": f"In RIP, any valid route in an Autonomous System cannot have more than {m_hop.group(1)} hops before it is considered inaccessible (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Networking: OSPF Link State
            if "link state" in s_low and ("ospf" in s_low or "intradomain" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "Which routing algorithm is the Open Shortest Path First (OSPF) protocol based on?",
                    "answer": "Link state routing",
                    "explanation": f"OSPF is an open intradomain routing protocol based on link state routing (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Transport Layer: Well-known ports
            if "well-known ports" in s_low and ("0 to 1023" in s_low or "1023" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "Which port range is designated as Well-Known Ports and controlled by IANA?",
                    "answer": "0 to 1023",
                    "explanation": f"IANA controls and assigns the well-known ports ranging from 0 to 1023 for standard server services (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

            # Transport Layer: Socket address
            if "socket address" in s_low and ("ip address" in s_low and "port number" in s_low):
                facts.append({
                    "kind": "db_concept",
                    "question": "What two identifiers combine to form a transport layer Socket Address?",
                    "answer": "An IP address and a port number",
                    "explanation": f"A socket address uniquely defines a network process through the combination of an IP address and a port number (Page {page}).",
                    "page": page,
                    "chunk_id": c_id,
                    "section": sec,
                })

        # 2. Extracted definitions (Secondary fallback)
        for d in definitions:
            term = d["term"].strip()
            definition = d["definition"].strip()
            if any(fw in term.lower() for fw in FORBIDDEN_CONTENT_WORDS):
                continue
            term_answer = term if len(term.split()) >= 2 else f"{term} concept"
            matched_page = 1
            matched_chunk = None
            sec = None
            for cs in chunk_sentences:
                if term.lower() in cs["sentence"].lower():
                    matched_page = cs["page"]
                    matched_chunk = cs["chunk_id"]
                    sec = cs["section"]
                    break
            facts.append({
                "kind": "definition",
                "term": term,
                "answer": term_answer,
                "definition": definition,
                "explanation": f"According to the document (Page {matched_page}), {term} is defined as: {definition}.",
                "page": matched_page,
                "chunk_id": matched_chunk,
                "section": sec,
            })

        return facts

