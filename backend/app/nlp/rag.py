import re
import uuid
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.nlp.retrieval import HybridRetriever
from backend.app.nlp.embeddings import EmbeddingEngine
from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.extractive import extract_definitions
from backend.app.llm.factory import get_llm_provider
from backend.app.db.models.document import Document, DocumentChunk
from backend.app.core.logging import logger

# Calibrated relevance thresholds
RELEVANCE_THRESHOLD_COSINE = 0.32
RELEVANCE_THRESHOLD_STRICT = 0.40

DOCUMENT_OVERVIEW_PATTERNS = [
    re.compile(r"(?i)\b(?:explain|summarize|overview|about|outline|what is in)\s+(?:the|this)?\s*(?:pdf|document|slide|slides|chapter|file|deck)\b"),
    re.compile(r"(?i)^explain\s+(?:the\s+)?(?:pdf|document|file|slides?)$"),
    re.compile(r"(?i)^what\s+is\s+this\s+(?:document|pdf|file|chapter)\s+about\??$"),
]

FORBIDDEN_FOOTER_PATTERNS = [
    re.compile(r"^(?:©|copyright|\(c\)|all rights reserved).*", re.IGNORECASE),
    re.compile(r".*silberschatz,\s*korth\s*and\s*sudarshan.*", re.IGNORECASE),
    re.compile(r".*database\s+system\s+concepts.*(?:edition|ed\.).*", re.IGNORECASE),
    re.compile(r".*see\s+www\.db-book\.com.*", re.IGNORECASE),
    re.compile(r"^\d+\.\d+$"),
    re.compile(r"^chapter\s*\d+\s*:\s*intermediate sql.*", re.IGNORECASE),
]


class RAGEngine:
    """
    Grounded Retrieval-Augmented Generation (RAG) Engine:
    - Multi-tenant isolated hybrid retrieval (Dense MiniLM + Sparse BM25 + RRF)
    - Strict relevance threshold checking to reject off-topic questions
    - Handles broad document requests ("explain the pdf") with structured overviews
    - Answers structured as: Direct Answer (1-2 sentences) -> Detailed Explanation -> Document Example -> Sources
    - Cleaned passages in answer and retrieved_passages panel (no footers or copyright lines)
    - Supports 4 explanation modes: Beginner, Detailed/Technical, Exam-Oriented, Real-World Example
    """
    def __init__(self, db: Session):
        self.db = db
        self.retriever = HybridRetriever(db)
        self.embedding_engine = EmbeddingEngine()
        self.llm = get_llm_provider()

    def generate_answer(
        self,
        user_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        explanation_mode: str = "technical",
        top_k: int = 4,
    ) -> Dict[str, Any]:
        query_clean = query.strip()
        if not query_clean:
            return {
                "answer": "Please ask a question about your documents.",
                "explanation_mode": explanation_mode,
                "confidence_score": 0.0,
                "sources": [],
                "retrieved_passages": [],
            }

        # Check for broad document overview requests (e.g. "explain the pdf")
        if self._is_overview_request(query_clean):
            return self._handle_overview_request(
                user_id=user_id,
                query=query_clean,
                document_ids=document_ids,
                explanation_mode=explanation_mode,
            )

        # 1. Retrieve top passages using Hybrid Retriever
        retrieved_passages = self.retriever.search_hybrid(
            user_id=user_id,
            query=query_clean,
            top_k=top_k,
            document_ids=document_ids,
        )

        if not retrieved_passages:
            return {
                "answer": "I couldn't find this in the selected document(s).",
                "explanation_mode": explanation_mode,
                "confidence_score": 0.0,
                "sources": [],
                "retrieved_passages": [],
            }

        # Clean passages (remove any lingering footers or copyright watermarks)
        for p in retrieved_passages:
            p["text"] = self._clean_passage_text(p["text"])
            p["snippet"] = p["text"][:260] + "..." if len(p["text"]) > 260 else p["text"]

        # 2. Strict relevance threshold evaluation across retrieved passages
        query_vec = self.embedding_engine.embed_text(query_clean)
        max_sim = -1.0
        for p in retrieved_passages:
            p_vec = self.embedding_engine.embed_text(p["text"][:1500])
            sim = float(self.embedding_engine.cosine_similarity(query_vec, p_vec))
            p["cosine_similarity"] = round(sim, 4)
            if sim > max_sim:
                max_sim = sim

        retrieved_passages.sort(key=lambda x: x.get("cosine_similarity", 0.0), reverse=True)
        top_passage = retrieved_passages[0]
        top_sim = top_passage.get("cosine_similarity", max_sim)

        # Content keyword overlap check
        query_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", query_clean.lower()))
        stop_words = {
            "what", "when", "where", "which", "who", "whom", "this", "that", "these", "those",
            "explain", "describe", "tell", "about", "does", "have", "with", "from", "into",
            "based", "used", "work", "role", "mean", "state", "type", "difference", "between"
        }
        content_query_words = {w for w in query_words if w not in stop_words}
        combined_text = "\n\n".join([p["text"] for p in retrieved_passages]).lower()
        lexical_matches = sum(1 for w in content_query_words if w in combined_text)
        lexical_ratio = lexical_matches / max(1, len(content_query_words))

        is_relevant = (top_sim >= RELEVANCE_THRESHOLD_COSINE) and (
            top_sim >= RELEVANCE_THRESHOLD_STRICT or lexical_matches > 0
        )

        if not is_relevant:
            logger.info(f"RAG query rejected as off-topic: query={query_clean!r}, top_sim={top_sim:.4f}, lexical_matches={lexical_matches}")
            return {
                "answer": "I couldn't find this in the selected document(s).",
                "explanation_mode": explanation_mode,
                "confidence_score": 0.0,
                "sources": [],
                "retrieved_passages": [],
            }

        # 3. Filter to relevant subset
        relevant_passages = [p for p in retrieved_passages if p.get("cosine_similarity", 0.0) >= (RELEVANCE_THRESHOLD_COSINE - 0.05)]
        if not relevant_passages:
            relevant_passages = [top_passage]

        # 4. Generate structured answer
        p_title = top_passage.get("document_title", "Document")
        p_start = top_passage.get("page_start", 1)
        p_end = top_passage.get("page_end", p_start)
        p_sec = top_passage.get("section_title", "").strip()

        cit_tag = f"[{p_title}, Page {p_start}]" if p_start == p_end else f"[{p_title}, Pages {p_start}-{p_end}]"
        if p_sec and p_sec.lower() not in p_title.lower():
            cit_tag = f"[{p_title}, Page {p_start} - {p_sec}]"

        norm_mode = explanation_mode.lower()
        answer_text = ""
        provider_notice = self.llm.get_provider_notice()

        if self.llm.is_external:
            context_blocks = []
            for i, p in enumerate(relevant_passages, 1):
                context_blocks.append(f"Passage {i} (Page {p['page_start']} - {p.get('section_title', '')}):\n{p['text']}")
            context_str = "\n\n".join(context_blocks)

            sys_prompt = self._build_grounded_system_prompt(norm_mode)
            user_prompt = f"""DOCUMENT CONTEXT:
{context_str}

USER QUESTION:
{query_clean}

Please provide a structured response adhering strictly to the required format."""
            try:
                answer_text = self.llm.generate(prompt=user_prompt, system_prompt=sys_prompt, max_tokens=1200)
            except Exception as e:
                logger.warning(f"Gemini RAG synthesis error: {e}. Falling back to local synthesis.")

        if not answer_text or not answer_text.strip():
            answer_text = self._synthesize_local_structured_answer(
                query=query_clean,
                passages=relevant_passages,
                mode=norm_mode,
                citation=cit_tag,
                content_words=content_query_words,
            )

        confidence = round(0.70 * top_sim + 0.30 * min(1.0, lexical_ratio), 4)
        confidence = max(0.40, min(0.98, confidence))

        # Build clean sources list
        sources = []
        seen_cits = set()
        for p in relevant_passages:
            c_tag = f"{p.get('document_title', 'Doc')} (Page {p['page_start']})"
            if c_tag not in seen_cits:
                seen_cits.add(c_tag)
                sources.append({
                    "chunk_id": str(p.get("chunk_id", "")),
                    "document_id": str(p.get("document_id", "")),
                    "document_title": p.get("document_title", "Document"),
                    "page_start": p["page_start"],
                    "page_end": p["page_end"],
                    "section_title": p.get("section_title"),
                    "citation": c_tag,
                    "score": p.get("cosine_similarity", top_sim),
                    "snippet": p.get("snippet", ""),
                })

        return {
            "answer": answer_text,
            "explanation_mode": explanation_mode,
            "confidence_score": confidence,
            "sources": sources,
            "retrieved_passages": retrieved_passages,
            "provider_notice": provider_notice,
        }

    def _is_overview_request(self, query: str) -> bool:
        q_low = query.lower().strip()
        if q_low in ("explain the pdf", "explain this pdf", "summarize the pdf", "what is this document", "overview"):
            return True
        for pat in DOCUMENT_OVERVIEW_PATTERNS:
            if pat.search(q_low):
                return True
        return False

    def _handle_overview_request(
        self,
        user_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]],
        explanation_mode: str,
    ) -> Dict[str, Any]:
        """Synthesizes a structured document overview when the user asks broad questions like 'explain the pdf'."""
        if not document_ids:
            # Pick first user document
            doc = self.db.query(Document).filter(Document.user_id == user_id).first()
            if not doc:
                return {
                    "answer": "No documents found to explain.",
                    "explanation_mode": explanation_mode,
                    "confidence_score": 0.0,
                    "sources": [],
                    "retrieved_passages": [],
                }
            document_ids = [doc.id]

        target_id = document_ids[0]
        doc = self.db.query(Document).filter(Document.id == target_id).first()
        doc_title = doc.original_filename if doc else "Document"

        chunks = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == target_id).order_by(DocumentChunk.chunk_index).all()
        if not chunks:
            return {
                "answer": f"The document {doc_title} has not been indexed yet.",
                "explanation_mode": explanation_mode,
                "confidence_score": 0.0,
                "sources": [],
                "retrieved_passages": [],
            }

        # Collect unique section titles
        sections = []
        seen_secs = set()
        sample_texts = []
        for c in chunks:
            sec = (c.section_title or "").strip()
            if sec and sec.lower() not in seen_secs and not sec.startswith("Page"):
                seen_secs.add(sec.lower())
                sections.append(sec)
            if len(sample_texts) < 6 and len(c.text.split()) > 20:
                sample_texts.append(f"[{sec or 'Section'} - Page {c.page_start}]: {c.text[:300]}")

        overview_text = ""
        if self.llm.is_external:
            prompt = f"""The user asked: "{query}" about the document "{doc_title}".
Sections detected in document: {', '.join(sections[:15])}

Sample excerpts:
{chr(10).join(sample_texts)}

Provide a structured, executive overview with:
1. Direct summary of the document's central subject and purpose.
2. Key topic areas covered (as bullet points).
3. Practical importance or exam relevance."""
            try:
                overview_text = self.llm.generate(prompt=prompt, system_prompt="You are a clear academic tutor.")
            except Exception:
                pass

        if not overview_text:
            overview_text = f"### Document Overview: {doc_title}\n\n"
            overview_text += f"This document contains comprehensive instructional material covering {len(chunks)} slides/sections across {doc.page_count if doc else 'multiple'} pages.\n\n"
            overview_text += "**Key Topics Covered:**\n"
            for sec in sections[:8]:
                overview_text += f"- **{sec}**\n"
            overview_text += f"\n*Source: [{doc_title}, Pages 1-{doc.page_count if doc else len(chunks)}]*"

        sources = [{
            "chunk_id": str(chunks[0].id),
            "document_id": str(target_id),
            "document_title": doc_title,
            "page_start": 1,
            "page_end": doc.page_count if doc else len(chunks),
            "section_title": "Full Document Overview",
            "citation": f"{doc_title} (Pages 1-{doc.page_count if doc else len(chunks)})",
            "score": 1.0,
            "snippet": f"Overview of all topics in {doc_title}",
        }]

        return {
            "answer": overview_text,
            "explanation_mode": explanation_mode,
            "confidence_score": 0.95,
            "sources": sources,
            "retrieved_passages": [],
            "provider_notice": self.llm.get_provider_notice(),
        }

    def _build_grounded_system_prompt(self, mode: str) -> str:
        base = """You are an expert AI professor and study assistant.
CRITICAL GROUNDING RULES:
1. Answer ONLY using facts directly stated in the provided context. Do NOT invent, assume, or extrapolate.
2. Structure your response in EXACTLY this format:
   **Direct Answer:** (A direct, complete 1 to 2 sentence answer to the user's question)
   **Detailed Explanation:** (Elaborate clearly using bullet points for key mechanisms or rules)
   **Document Example:** (If the document includes a SQL query, code block, or concrete example, show it here; otherwise state: 'No specific code example provided in the source excerpt.')
   **Citation:** (Exact document title and page number)
3. Never include raw slide footers, copyright lines (e.g. Silberschatz), or repeated headers in your prose.
4. If the question cannot be answered from the context, state: 'I couldn't find this in the selected document(s).'"""

        if mode == "beginner":
            return base + "\nTone: Intuitive, accessible, clear everyday analogies where helpful."
        elif mode == "exam":
            return base + "\nTone: Rigorous exam focus, highlighting definitions, key distinctions, and common exam pitfalls."
        elif mode == "realworld":
            return base + "\nTone: Practical application focus, highlighting real-world database or networking deployment."
        return base + "\nTone: Precise, technical, and in-depth."

    def _synthesize_local_structured_answer(
        self,
        query: str,
        passages: List[Dict[str, Any]],
        mode: str,
        citation: str,
        content_words: Set[str],
    ) -> str:
        """Local deterministic synthesis strictly structured without template repetition."""
        top_p = passages[0]
        text = top_p["text"]
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Extract direct definition or top matching sentence
        sentences = split_into_sentences(text, exclude_code=True)
        direct_sentence = ""
        for s in sentences:
            s_low = s.lower()
            if any(w in s_low for w in content_words):
                direct_sentence = s
                break
        if not direct_sentence and sentences:
            direct_sentence = sentences[0]

        # Extract code/SQL example if present
        code_example = None
        for l in lines:
            if l.startswith("[Code/SQL Example]:") or l.lower().startswith("create ") or l.lower().startswith("select "):
                code_example = l.replace("[Code/SQL Example]:", "").strip()
                break

        # Additional bullets from surrounding sentences
        bullets = []
        for s in sentences[1:4]:
            if s != direct_sentence and len(s.split()) >= 6:
                bullets.append(s)

        out = f"**Direct Answer:**\n{direct_sentence}\n\n"
        out += "**Detailed Explanation:**\n"
        if bullets:
            for b in bullets:
                out += f"- {b}\n"
        else:
            out += f"Based on {citation}, this mechanism provides key operational functionality in the system architecture.\n"

        if code_example:
            out += f"\n**Document Example:**\n```sql\n{code_example}\n```\n"

        out += f"\n*Source: {citation}*"
        return out

    def _clean_passage_text(self, text: str) -> str:
        lines = text.splitlines()
        clean = []
        for l in lines:
            ls = l.strip()
            if not ls:
                continue
            if any(pat.match(ls) for pat in FORBIDDEN_FOOTER_PATTERNS):
                continue
            clean.append(ls)
        return "\n".join(clean)
