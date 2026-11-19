import math
from typing import List, Tuple, Dict, Any, Optional
from backend.app.core.logging import logger
from backend.app.documents.chunking import split_into_sentences
from backend.app.nlp.model_manager import get_model_manager
from backend.app.nlp.extractive import TextRankSummarizer, extract_definitions, extract_key_points


class AbstractiveSummarizer:
    """
    Abstractive summarization using Hugging Face Transformers.
    Implements Map-Reduce chunking for long documents exceeding model context limits.
    """
    def __init__(self):
        self.model_manager = get_model_manager()
        self.fallback = TextRankSummarizer()

    def _get_length_params(self, length: str) -> Dict[str, int]:
        length = length.lower()
        if length == "short":
            return {"max_length": 60, "min_length": 25}
        elif length == "detailed":
            return {"max_length": 250, "min_length": 90}
        else:  # medium
            return {"max_length": 140, "min_length": 50}

    def summarize(
        self,
        text: str,
        length: str = "medium",
        mode: str = "standard",
    ) -> Tuple[str, List[str], List[Dict[str, str]], str]:
        """
        Generates an abstractive summary.
        Returns: (summary_content, key_points, definitions, model_used)
        """
        text = text.strip()
        if not text:
            return "No content to summarize.", [], [], "none"

        words = text.split()
        params = self._get_length_params(length)

        try:
            summarizer = self.model_manager.get_summarizer()
            model_name = getattr(summarizer.model, "name_or_path", "distilbart-cnn-12-6")

            # MAP-REDUCE for long documents (> 500 words)
            if len(words) > 500:
                sentences = split_into_sentences(text)
                chunks = []
                current_chunk = []
                current_len = 0

                for s in sentences:
                    s_len = len(s.split())
                    if current_len + s_len > 400 and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = [s]
                        current_len = s_len
                    else:
                        current_chunk.append(s)
                        current_len += s_len
                if current_chunk:
                    chunks.append(" ".join(current_chunk))

                # Map stage: summarize each chunk
                intermediate = []
                for chunk in chunks[:6]:  # Limit to top 6 chunks for speed
                    res = summarizer(
                        chunk,
                        max_length=params["max_length"],
                        min_length=params["min_length"],
                        do_sample=False,
                        truncation=True,
                    )
                    intermediate.append(res[0]["summary_text"].strip())

                # Reduce stage
                combined_text = " ".join(intermediate)
                if len(combined_text.split()) > params["max_length"]:
                    final_res = summarizer(
                        combined_text,
                        max_length=params["max_length"],
                        min_length=params["min_length"],
                        do_sample=False,
                        truncation=True,
                    )
                    summary_content = final_res[0]["summary_text"].strip()
                else:
                    summary_content = combined_text

            else:
                # Direct summarization for short/medium documents
                res = summarizer(
                    text,
                    max_length=min(params["max_length"], max(30, int(len(words) * 0.8))),
                    min_length=min(params["min_length"], max(15, int(len(words) * 0.2))),
                    do_sample=False,
                    truncation=True,
                )
                summary_content = res[0]["summary_text"].strip()

        except Exception as e:
            logger.warning(f"Abstractive neural summarization failed or unavailable: {e}. Falling back to TextRank.")
            num_sent = 3 if length == "short" else (8 if length == "detailed" else 5)
            summary_content, _ = self.fallback.summarize(text, num_sentences=num_sent)
            model_name = "TextRank (Extractive Fallback)"

        # Mode transformations
        sentences = split_into_sentences(summary_content)
        key_points = extract_key_points(sentences)
        definitions = extract_definitions(text)

        if mode == "bullet":
            summary_content = "\n".join([f"• {s}" for s in sentences if s.strip()])
        elif mode == "exam":
            exam_header = "### Exam Preparation Key Takeaways:\n\n"
            bullets = "\n".join([f"• {p}" for p in key_points])
            def_section = ""
            if definitions:
                def_section = "\n\n### Core Definitions:\n" + "\n".join([f"- **{d['term']}**: {d['definition']}." for d in definitions])
            summary_content = f"{summary_content}\n\n{exam_header}{bullets}{def_section}"

        return summary_content, key_points, definitions, model_name
