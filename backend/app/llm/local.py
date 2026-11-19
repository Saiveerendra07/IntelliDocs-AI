from typing import Optional
from backend.app.llm.base import BaseLLM
from backend.app.core.logging import logger


class LocalLLM(BaseLLM):
    """
    Local-first LLM provider.
    Runs entirely on device using local models or context-grounded extractive synthesis.
    Zero external network calls; 100% private.
    """
    @property
    def name(self) -> str:
        return "local"

    @property
    def is_external(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        # Local execution: returns empty string to signal caller to use local extractive/rule-based synthesis
        # or local model pipeline.
        return ""
