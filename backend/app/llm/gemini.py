import json
from typing import Optional
import httpx
from backend.app.llm.base import BaseLLM
from backend.app.core.config import settings
from backend.app.core.logging import logger


class GeminiLLM(BaseLLM):
    """
    Google Gemini provider via official REST API.
    Used when GEMINI_API_KEY is configured in .env.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model

    @property
    def name(self) -> str:
        return "gemini"

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
            logger.warning("Gemini API key not configured. Falling back to local mode.")
            return ""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nPlease follow the system instructions strictly."}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will strictly follow the instructions and only use the provided context."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Gemini API generation error: {e}")

        return ""
