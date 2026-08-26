"""
Provider-agnostic AI text client.

Selects backend via AI_PROVIDER env:
  - "yandex"    -> Yandex Cloud Foundation Models (OpenAI-compatible endpoint)
  - "anthropic" -> Anthropic Claude
  - "openai"    -> OpenAI (or any OpenAI-compatible /chat/completions endpoint)

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


class AIUnavailable(RuntimeError):
    """Провайдер не отвечает — долгий прогон запускать бессмысленно."""


def check_ai_available(model=None, timeout=None):
    """Один дешёвый запрос перед длинной работой. Отказ — исключение, не None.

    `model` и `timeout` — те же, с которыми пойдёт сама работа. Проверять чем-то
    другим смысла нет: ключ бывает валиден, а модель из настройки недоступна.

    MG_AIPING: `get_ai_client()` только СОБИРАЕТ клиента. Пустой ключ он ловит,
    а неверный — нет: неправильный токен виден лишь по ответу сервиса. Поэтому
    проверки вида «AI-клиент недоступен» вокруг фабрики от протухшего ключа не
    спасают: команда доходит до конца, ловя 401 на каждой пачке.

    Дороже всего это обходилось канонизации состава: она гасила ошибку пачки
    молча, и прогон выглядел успешным, а в каталог ехали сырые названия прямо
    из текста рецепта — «Сливы», «Мандарина», «Время приготовления 40 мин».
    """
    try:
        client = get_ai_client(model=model, timeout=timeout)
        # MG_AIEMPTY: щедрый лимит намеренно. Двадцати токенов хватало обычной
        # модели, но рассуждатель тратит их на размышление и отдаёт пустой текст
        # при HTTP 200 — проверка падала на живом провайдере.
        answer = client.complete(prompt="Ответь одним словом: столица России?", max_tokens=256, temperature=0.0)
    except Exception as exc:
        raise AIUnavailable("%s: %s" % (type(exc).__name__, exc))
    if not (answer or "").strip():
        raise AIUnavailable("провайдер ответил пустым текстом")


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
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=self._timeout)
        except requests.RequestException as exc:
            raise AIRequestError(f"Yandex AI request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIRequestError(f"Yandex AI HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRequestError(f"Unexpected Yandex AI response: {data}") from exc


class OpenAIAIClient(BaseAIClient):
    """OpenAI (or any OpenAI-compatible) chat-completions endpoint.

    Uses only ``requests`` (no new dependency). Works against api.openai.com
    or any compatible gateway via ``AI_BASE_URL``. Auth is a Bearer token.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        text_model: str,
        timeout: float,
    ) -> None:
        if not api_key:
            raise AIConfigError("AI_API_KEY is not set for provider 'openai'.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._text_model = text_model
        self._timeout = timeout

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
            "model": self._text_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=self._timeout)
        except requests.RequestException as exc:
            raise AIRequestError(f"OpenAI request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIRequestError(f"OpenAI HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

        # MG_AIEMPTY: шлюз умеет отдать ошибку с кодом 200 в теле ответа
        # ({"error": {"message": "The operation was aborted", "code": 504}}).
        # Без этой ветки такое приходило как «Unexpected OpenAI response» —
        # формально верно, но по тексту не понять, что это таймаут у шлюза.
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            err = data["error"]
            raise AIRequestError("OpenAI: ошибка в теле ответа (code=%s): %s" % (err.get("code"), err.get("message")))

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRequestError(f"Unexpected OpenAI response: {data}") from exc

        # MG_AIEMPTY: у совместимых шлюзов content бывает списком частей
        # ({"type": "text", "text": ...}) — так отвечают модели семейства Gemini.
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        content = content or ""

        # Пустой текст при HTTP 200 — это отказ, который ни на что не похож.
        # Так ведут себя модели-рассуждатели: весь лимит max_tokens уходит на
        # размышление, на сам ответ не остаётся ничего, и finish_reason=length.
        # Без этих подробностей причину по «пустому ответу» не угадать.
        if not content.strip():
            raise AIRequestError(
                "OpenAI: пустой ответ при HTTP 200 (model=%s, finish_reason=%s, usage=%s). "
                "Для модели-рассуждателя увеличьте max_tokens: лимит уходит на размышление."
                % (self._text_model, choice.get("finish_reason"), data.get("usage"))
            )
        return content


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


def get_ai_client(
    provider: Optional[str] = None, model: Optional[str] = None, timeout: Optional[float] = None
) -> BaseAIClient:
    """Factory. Reads configuration from environment.

    Env vars:
      AI_PROVIDER     "yandex" | "anthropic" | "openai"  (default: "yandex")
      AI_API_KEY      provider API key                   (required)
      AI_BASE_URL     OpenAI-compatible base URL          (yandex/openai default below)
      AI_FOLDER_ID    Yandex folder id                    (required for yandex)
      AI_TEXT_MODEL   model id or full URI                (per-provider default)
      AI_TIMEOUT      request timeout, seconds            (default 30)

    MG_AIMODEL: `model` перебивает AI_TEXT_MODEL для одной задачи. Нужно там, где
    качество важнее цены — например, канонизация названий продуктов: результат
    её работы видят все пользователи в каталоге, а запускается она изредка.
    Раньше такую подмену делали через setattr на приватное поле клиента, и она
    молча ничего не делала для всех провайдеров, кроме Yandex.

    MG_AITIMEOUT: `timeout` — туда же. AI_TIMEOUT подобран под разовый запрос в
    пользовательском пути, где ждать нельзя. Пакетная работа устроена иначе: она
    шлёт пачками по три десятка названий и просит до 3000 токенов ответа, и
    сильная модель в те же 30 секунд не укладывается. Отваливаться по таймауту
    там дороже, чем подождать.
    """
    provider = (provider or config("AI_PROVIDER", default="yandex")).strip().lower()
    api_key = config("AI_API_KEY", default="")
    timeout = timeout or config("AI_TIMEOUT", default=30.0, cast=float)

    if provider == "yandex":
        base_url = config("AI_BASE_URL", default="https://llm.api.cloud.yandex.net/v1")
        folder_id = config("AI_FOLDER_ID", default="")
        text_model = model or config("AI_TEXT_MODEL", default="yandexgpt-lite")
        return YandexAIClient(
            api_key=api_key,
            folder_id=folder_id,
            base_url=base_url,
            text_model=text_model,
            timeout=timeout,
        )

    if provider == "openai":
        base_url = config("AI_BASE_URL", default="https://api.openai.com/v1")
        text_model = model or config("AI_TEXT_MODEL", default="gpt-4o-mini")
        return OpenAIAIClient(
            api_key=api_key,
            base_url=base_url,
            text_model=text_model,
            timeout=timeout,
        )

    if provider == "anthropic":
        # Backward-compat: fall back to ANTHROPIC_API_KEY if AI_API_KEY empty.
        if not api_key:
            api_key = config("ANTHROPIC_API_KEY", default="")
        text_model = model or config("AI_TEXT_MODEL", default="claude-haiku-4-5-20251001")
        return AnthropicAIClient(api_key=api_key, text_model=text_model)

    raise AIConfigError(f"Unknown AI_PROVIDER: {provider!r}")
