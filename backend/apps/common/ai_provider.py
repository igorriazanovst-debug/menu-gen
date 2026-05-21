"""
Provider-agnostic AI text client.

Selects backend via AI_PROVIDER env:
  - "yandex"    -> Yandex Cloud Foundation Models (OpenAI-compatible endpoint)
  - "anthropic" -> Anthropic Claude

All configuration comes from environment (decouple.config). No hardcoded
URLs, keys or model names.

Public API:
    client = get_ai_client()
    text = client.complete(system="...", prompt="...", max_tokens=150, temperature=0.0)

Both providers return plain assistant text (str).

This module deliberately depends only on `requests` (already in requirements)
for the Yandex path, and on `anthropic` (already in requirements) for the
Anthropic path, so no new dependency is introduced.
"""
from __future__ import annotations

import json
from typing import Optional

from decouple import config


class AIConfigError(RuntimeError):
    """Raised when AI provider configuration is missing or invalid."""


class AIRequestError(RuntimeError):
    """Raised when the upstream AI request fails."""


class BaseAIClient:
    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError


class YandexAIClient(BaseAIClient):
    """Yandex Cloud Foundation Models via OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: str,
        folder_id: str,
        base_url: str,
        text_model: str,
        timeout: float,
    ) -> None:
        if not api_key:
            raise AIConfigError("AI_API_KEY is not set for provider 'yandex'.")
        if not folder_id:
            raise AIConfigError("AI_FOLDER_ID is not set for provider 'yandex'.")
        self._api_key = api_key
        self._folder_id = folder_id
        self._base_url = base_url.rstrip("/")
        self._text_model = text_model
        self._timeout = timeout

    def _model_uri(self) -> str:
        # If a full URI was provided, use as-is; else build gpt://<folder>/<model>/latest
        if self._text_model.startswith("gpt://"):
            return self._text_model
        return f"gpt://{self._folder_id}/{self._text_model}/latest"

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        import requests  # local import to avoid hard dependency at import time

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model_uri(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise AIRequestError(f"Yandex AI request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIRequestError(
                f"Yandex AI HTTP {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRequestError(f"Unexpected Yandex AI response: {data}") from exc


class AnthropicAIClient(BaseAIClient):
    """Anthropic Claude (kept for parity / fallback)."""

    def __init__(self, api_key: str, text_model: str) -> None:
        if not api_key:
            raise AIConfigError("AI_API_KEY (or ANTHROPIC_API_KEY) is not set for provider 'anthropic'.")
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._text_model = text_model

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        resp = self._client.messages.create(
            model=self._text_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text


def get_ai_client(provider: Optional[str] = None) -> BaseAIClient:
    """Factory. Reads configuration from environment.

    Env vars:
      AI_PROVIDER     "yandex" | "anthropic"            (default: "yandex")
      AI_API_KEY      provider API key                   (required)
      AI_BASE_URL     OpenAI-compatible base URL          (yandex default below)
      AI_FOLDER_ID    Yandex folder id                    (required for yandex)
      AI_TEXT_MODEL   model id or full URI                (per-provider default)
      AI_TIMEOUT      request timeout, seconds            (default 30)
    """
    provider = (provider or config("AI_PROVIDER", default="yandex")).strip().lower()
    api_key = config("AI_API_KEY", default="")
    timeout = config("AI_TIMEOUT", default=30.0, cast=float)

    if provider == "yandex":
        base_url = config(
            "AI_BASE_URL", default="https://llm.api.cloud.yandex.net/v1"
        )
        folder_id = config("AI_FOLDER_ID", default="")
        text_model = config("AI_TEXT_MODEL", default="yandexgpt-lite")
        return YandexAIClient(
            api_key=api_key,
            folder_id=folder_id,
            base_url=base_url,
            text_model=text_model,
            timeout=timeout,
        )

    if provider == "anthropic":
        # Backward-compat: fall back to ANTHROPIC_API_KEY if AI_API_KEY empty.
        if not api_key:
            api_key = config("ANTHROPIC_API_KEY", default="")
        text_model = config("AI_TEXT_MODEL", default="claude-haiku-4-5-20251001")
        return AnthropicAIClient(api_key=api_key, text_model=text_model)

    raise AIConfigError(f"Unknown AI_PROVIDER: {provider!r}")
