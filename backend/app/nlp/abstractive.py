import math
from typing import List, Tuple, Dict, Any, Optional
from backend.app.core.logging import logger
from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.model_manager import get_model_manager
from backend.app.nlp.extractive import TextRankSummarizer, extract_definitions, extract_key_points
from backend.app.llm.factory import get_llm_provider


class AbstractiveSummarizer:
    """
    Abstractive & Structured summarization:
    - Uses Gemini LLM when configured for comprehensive structured summaries:
      Overview, Main Topics & Key Mechanisms, Key Definitions, Key SQL Examples, Exam Focus.
    - Local fallback: Hugging Face DistilBART / TextRank with clean prose sentences.
    """
    def __init__(self):
        self.model_manager = get_model_manager()
        self.fallback = TextRankSummarizer()
        self.llm = get_llm_provider()

    def _get_length_params(self, length: str) -> Dict[str, int]:
        length = length.lower()
        if length == "short":
            return {"max_length": 100, "min_length": 35}
        elif length == "detailed":
            return {"max_length": 450, "min_length": 150}
        else:  # medium
            return {"max_length": 250, "min_length": 80}

    def summarize(
        self,
        text: str,
        length: str = "medium",
        mode: str = "standard",
    ) -> Tuple[str, List[str], List[Dict[str, str]], str]:
        """
        Generates structured abstractive summary.
        Returns: (summary_content, key_points, definitions, model_used)
        """
        text = text.strip()
        if not text:
            return "No content to summarize.", [], [], "none"

        # Priority 1: Gemini LLM Structured Summary
        if self.llm.is_external:
            try:
                summary_content, key_points, defs = self._summarize_with_gemini(text, length)
                if summary_content:
                    return summary_content, key_points, defs, f"gemini ({self.llm.model})"
            except Exception as e:
                logger.warning(f"Gemini summarization failed: {e}. Falling back to local model.")

        # Priority 2: Local DistilBART or TextRank Map-Reduce
        return self._summarize_local(text, length)

    def _summarize_with_gemini(self, text: str, length: str) -> Tuple[str, List[str], List[Dict[str, str]]]:
        truncated_text = text[:8000]

        prompt = f"""You are an expert professor summarizing the following technical document lecture notes.
Length preference: {length}

DOCUMENT TEXT:
{truncated_text}

FORMAT INSTRUCTIONS:
Create a well-structured markdown summary containing EXACTLY these sections:
### 1. Overview
(2 to 4 sentences introducing the core document theme and scope)

### 2. Main Topics & Key Mechanisms
(Organized subheadings or bullet points covering key architectural, algorithmic, or syntactic mechanisms)

### 3. Key Definitions
(Bullet list of critical terms and their precise technical definitions)

### 4. Key SQL / Code Examples
(Clean, formatted code blocks with brief explanations. If the document has no code, provide key protocol or packet structure examples)

### 5. Exam Focus
(Key exam questions, distinctions, and pitfalls students must know)

STRICT RULES:
- Do not repeat sentences.
- NEVER include book watermarks, copyright notices, author names (Silberschatz, Korth, Sudarshan), or slide numbers in the prose.
- Separate code cleanly from explanations.
"""
        res = self.llm.generate(prompt=prompt, system_prompt="You are a senior computer science academic synthesizer.", max_tokens=1500)
        if not res:
            return "", [], []

        # Extract bullet key points
        key_points = []
        for line in res.splitlines():
            line_s = line.strip()
            if line_s.startswith("- ") or line_s.startswith("* "):
                clean_point = line_s[2:].strip()
                if len(clean_point) > 15:
                    key_points.append(clean_point)

        # Extract definitions
        defs = extract_definitions(text)
        return res, key_points[:8], defs

    def _summarize_local(self, text: str, length: str) -> Tuple[str, List[str], List[Dict[str, str]], str]:
        words = text.split()
        params = self._get_length_params(length)

        try:
            summarizer = self.model_manager.get_summarizer()
            model_name = getattr(summarizer.model, "name_or_path", "distilbart-cnn-12-6")

            # MAP-REDUCE for long documents (> 500 words)
            if len(words) > 500:
                sentences = split_into_sentences(text, exclude_code=True)
                chunks = []
                current_chunk = []
                current_len = 0

                for s in sentences:
                    s_len = len(s.split())
                    if current_len + s_len > 350 and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = [s]
                        current_len = s_len
                    else:
                        current_chunk.append(s)
                        current_len += s_len
                if current_chunk:
                    chunks.append(" ".join(current_chunk))

                intermediate = []
                for chunk in chunks[:5]:
                    res = summarizer(
                        chunk,
                        max_length=params["max_length"],
                        min_length=params["min_length"],
                        do_sample=False,
                        truncation=True,
                    )
                    if res and len(res) > 0:
                        intermediate.append(res[0]["summary_text"].strip())

                combined = " ".join(intermediate)
                final_res = summarizer(
                    combined,
                    max_length=params["max_length"],
                    min_length=params["min_length"],
                    do_sample=False,
                    truncation=True,
                )
                summary_text = final_res[0]["summary_text"].strip()
            else:
                res = summarizer(
                    text,
                    max_length=params["max_length"],
                    min_length=params["min_length"],
                    do_sample=False,
                    truncation=True,
                )
                summary_text = res[0]["summary_text"].strip()

            key_points = extract_key_points(text, num_points=5)
            definitions = extract_definitions(text)
            
            kp_bullets = "\n".join([f"- {p}" for p in key_points])
            def_bullets = "\n".join([f"- **{d['term']}**: {d['definition']}" for d in definitions])
            structured_md = (
                f"### 1. Overview\n{summary_text}\n\n"
                f"### 2. Main Topics & Key Mechanisms\n{kp_bullets or '- Core conceptual mechanisms and structural rules.'}\n\n"
                f"### 3. Key Definitions\n{def_bullets or '- Domain definitions and syntax operations.'}\n\n"
                f"### 4. Key SQL / Code Examples\n*(Code and syntax structures extracted directly in document context)*\n\n"
                f"### 5. Exam Focus\nReview the core operational definitions, distinction boundaries, and protocol limit metrics outlined above."
            )
            return structured_md, key_points, definitions, model_name

        except Exception as e:
            logger.warning(f"Local DistilBART summarization fallback to TextRank: {e}")
            num_sents = 3 if length == "short" else (7 if length == "detailed" else 5)
            raw_sents, _ = self.fallback.summarize(text, num_sentences=num_sents)
            summary_text = raw_sents if isinstance(raw_sents, str) else " ".join(raw_sents)
            key_points = extract_key_points(text, num_points=num_sents)
            definitions = extract_definitions(text)
            
            kp_bullets = "\n".join([f"- {p}" for p in key_points])
            def_bullets = "\n".join([f"- **{d['term']}**: {d['definition']}" for d in definitions])
            structured_md = (
                f"### 1. Overview\n{summary_text}\n\n"
                f"### 2. Main Topics & Key Mechanisms\n{kp_bullets or '- Core conceptual mechanisms and structural rules.'}\n\n"
                f"### 3. Key Definitions\n{def_bullets or '- Domain definitions and syntax operations.'}\n\n"
                f"### 4. Key SQL / Code Examples\n*(Code and syntax structures extracted directly in document context)*\n\n"
                f"### 5. Exam Focus\nReview the core operational definitions, distinction boundaries, and protocol limit metrics outlined above."
            )
            return structured_md, key_points, definitions, "textrank"
