from typing import Optional
import httpx
from backend.app.llm.base import BaseLLM
from backend.app.core.config import settings
from backend.app.core.logging import logger


class OpenAILLM(BaseLLM):
    """
    OpenAI provider via official Chat Completions REST API.
    Used when OPENAI_API_KEY is configured in .env.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_external(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        if not self.api_key:
            logger.warning("OpenAI API key not configured. Falling back to local mode.")
            return ""

        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    logger.warning(f"OpenAI API returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"OpenAI API generation error: {e}")

        return ""
