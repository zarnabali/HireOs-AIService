import json
import hashlib
import time
from typing import Any

from app.core.config import get_settings


class PromptCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._items.get(key)
        if item is None:
            return None
        created_at, value = item
        if time.time() - created_at > self.ttl_seconds:
            self._items.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._items[key] = (time.time(), value)


_prompt_cache = PromptCache()


def _cache_key(system_prompt: str, payload: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}\n{system_prompt}\n{payload}".encode("utf-8")).hexdigest()
    return digest


class CachedOpenAIJsonClient:
    """Small OpenAI JSON client with prompt-response caching and safe fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def complete_json(
        self,
        *,
        system_prompt: str,
        payload: str,
        fallback: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            return fallback

        key = _cache_key(system_prompt, payload[:60000], self.settings.openai_model)
        cached = _prompt_cache.get(key)
        if cached is not None:
            return cached

        try:
            from openai import OpenAI
        except ImportError:
            return fallback

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload[:60000]},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return fallback
            _prompt_cache.set(key, parsed)
            return parsed
        except Exception:
            return fallback


class OpenAIResumeClient:
    """OpenAI-backed structured resume extraction client."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract_resume_fields(self, resume_text: str) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI resume extraction")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract a resume into strict JSON for an AI hiring platform. "
                        "Return only JSON with keys: full_name, email, phone, location, "
                        "linkedin, github, portfolio, professional_summary, skills, "
                        "work_experience, education, projects, certifications, "
                        "languages, achievements. Use arrays for repeated fields. "
                        "Do not infer protected attributes."
                    ),
                },
                {
                    "role": "user",
                    "content": resume_text[:60000],
                },
            ],
        )

        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned invalid JSON for resume extraction") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI resume extraction response must be a JSON object")
        return parsed
