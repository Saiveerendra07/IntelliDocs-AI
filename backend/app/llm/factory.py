from typing import Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.llm.base import BaseLLM
from backend.app.llm.local import LocalLLM
from backend.app.llm.gemini import GeminiLLM
from backend.app.llm.openai import OpenAILLM


def get_llm_provider(provider_override: Optional[str] = None) -> BaseLLM:
    """
    Factory function to instantiate the configured LLM provider.
    Priority:
    1. If provider_override is specified, use it.
    2. If settings.LLM_PROVIDER is 'gemini' and GEMINI_API_KEY is present -> GeminiLLM.
    3. If settings.LLM_PROVIDER is 'openai' and OPENAI_API_KEY is present -> OpenAILLM.
    4. If GEMINI_API_KEY is set (even if LLM_PROVIDER is default) -> GeminiLLM.
    5. Default -> LocalLLM (100% offline, local execution).
    """
    target = (provider_override or settings.LLM_PROVIDER or "local").lower().strip()

    if target == "gemini" or (settings.GEMINI_API_KEY and target != "local" and target != "openai"):
        if settings.GEMINI_API_KEY:
            return GeminiLLM(api_key=settings.GEMINI_API_KEY)
        logger.warning("GEMINI requested but GEMINI_API_KEY is empty. Using Local provider.")
        return LocalLLM()

    if target == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAILLM(api_key=settings.OPENAI_API_KEY)
        logger.warning("OPENAI requested but OPENAI_API_KEY is empty. Using Local provider.")
        return LocalLLM()

    return LocalLLM()
