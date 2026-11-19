import json
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the provider name (e.g. 'local', 'gemini', 'openai')."""
        pass

    @property
    @abstractmethod
    def is_external(self) -> bool:
        """Whether this provider sends document data outside the local machine."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        """Generates completion text from prompt."""
        pass

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> Optional[Any]:
        """Generates and parses strict JSON. Returns None if invalid."""
        raw = self.generate(prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature)
        if not raw:
            return None
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def get_provider_notice(self) -> str:
        """User-facing disclosure notice."""
        if self.is_external:
            return f"Processed using external {self.name.title()} API. Note: Document passages were sent externally."
        return "Basic mode: connect an LLM provider (GEMINI_API_KEY) for higher quality."
