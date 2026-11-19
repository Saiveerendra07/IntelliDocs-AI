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

    def get_provider_notice(self) -> Optional[str]:
        """User-facing disclosure notice if external API is used."""
        if self.is_external:
            return f"Processed using external {self.name.title()} API. Note: Document passages were sent externally."
        return None
