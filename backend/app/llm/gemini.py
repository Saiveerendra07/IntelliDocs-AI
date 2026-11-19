import json
import re
from typing import Optional, Any, List
import httpx
from backend.app.llm.base import BaseLLM
from backend.app.core.config import settings
from backend.app.core.logging import logger

AVAILABLE_GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]


class GeminiLLM(BaseLLM):
    """
    Google Gemini provider via official REST API.
    Used when GEMINI_API_KEY is configured in .env.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.5-flash-lite"):
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
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        if not self.api_key:
            logger.warning("Gemini API key not configured. Falling back to local mode.")
            return ""

        models_to_try = [self.model] + [m for m in AVAILABLE_GEMINI_MODELS if m != self.model]

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

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                with httpx.Client(timeout=httpx.Timeout(12.0, connect=3.0)) as client:
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
                    elif resp.status_code == 404:
                        logger.warning(f"Gemini model {model_name} returned 404. Trying next available model...")
                        continue
                    elif resp.status_code == 429:
                        logger.warning("Gemini API rate limit (429) hit. Falling back to local mode.")
                        return ""
                    else:
                        logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
            except (httpx.ConnectError, httpx.NetworkError, httpx.ConnectTimeout) as e:
                logger.warning(f"Gemini connection unreachable: {e}. Falling back to local mode.")
                break
            except httpx.TimeoutException:
                logger.warning(f"Gemini API request timed out for model {model_name}.")
                continue
            except Exception as e:
                logger.error(f"Gemini API generation error: {e}")
                break

        return ""

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> Optional[Any]:
        """
        Requests strict JSON from Gemini, parses it, and retries once if malformed.
        """
        json_sys_prompt = (
            (system_prompt or "") + "\n\nCRITICAL: Output ONLY valid, parsable JSON. "
            "Do not wrap in markdown code blocks. Do not add any explanatory text before or after the JSON."
        ).strip()

        raw_output = self.generate(
            prompt=prompt,
            system_prompt=json_sys_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if not raw_output:
            return None

        # Clean potential markdown wrapping (e.g. ```json ... ```)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_output.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Gemini JSON parse failed on first attempt: {e}. Retrying once with error feedback...")
            # Retry once with explicit repair request
            repair_prompt = f"The previous output was not valid JSON ({e}). Please format and output ONLY valid JSON for this request:\n\n{raw_output}"
            retry_output = self.generate(
                prompt=repair_prompt,
                system_prompt="Output ONLY valid raw JSON.",
                max_tokens=max_tokens,
                temperature=0.0,
            )
            if retry_output:
                cleaned_retry = re.sub(r"^```(?:json)?\s*", "", retry_output.strip(), flags=re.IGNORECASE)
                cleaned_retry = re.sub(r"\s*```$", "", cleaned_retry.strip())
                try:
                    return json.loads(cleaned_retry)
                except Exception as retry_err:
                    logger.error(f"Gemini JSON repair retry failed: {retry_err}")
            return None
