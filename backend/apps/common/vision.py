"""
Photo product recognition: Yandex Vision OCR -> text -> LLM name extraction.

Pipeline (all synchronous, no batch):
  1) recognize_text(image_bytes, mime)  -> raw OCR fullText  (Yandex Vision OCR)
  2) extract_products(ocr_text, mode)    -> structured product(s) via text LLM

No hardcoded URLs/keys/folder/models — everything from settings/env.
The OCR host is DERIVED from AI_BASE_URL's domain (e.g. llm.api.cloud.yandex.net
-> ocr.api.cloud.yandex.net), so changing the cloud region/domain in one env
var keeps both endpoints consistent.

Depends only on `requests` (already in requirements) and the existing
get_ai_client() text client. No new dependency.
"""
from __future__ import annotations

import base64
import json
import re
from typing import List, Optional, Tuple

from django.conf import settings

from .ai_provider import AIRequestError, get_ai_client

# ── allowed image mime types for OCR ────────────────────────────────────────
_ALLOWED_MIME = {"image/jpeg", "image/png", "application/pdf"}
_DEFAULT_MIME = "image/jpeg"

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class VisionConfigError(RuntimeError):
    """Raised when vision/OCR configuration is missing or invalid."""


class VisionRequestError(RuntimeError):
    """Raised when the OCR upstream request fails."""


def _ocr_url() -> str:
    """Derive the Vision OCR endpoint from AI_BASE_URL's domain.

    AI_BASE_URL e.g. 'https://llm.api.cloud.yandex.net/v1'
      -> host root 'https://llm.api.cloud.yandex.net'
      -> domain base 'api.cloud.yandex.net'
      -> OCR host 'https://ocr.api.cloud.yandex.net'
    Override fully via OCR_BASE_URL if ever needed.
    """
    override = getattr(settings, "OCR_BASE_URL", "") or ""
    if override:
        return override.rstrip("/") + "/ocr/v1/recognizeText"

    base = (getattr(settings, "AI_BASE_URL", "") or "").strip()
    if not base:
        raise VisionConfigError("AI_BASE_URL is not set; cannot derive OCR endpoint.")
    m = re.match(r"^(https?)://([^/]+)", base)
    if not m:
        raise VisionConfigError(f"AI_BASE_URL is malformed: {base!r}")
    scheme, host = m.group(1), m.group(2)
    # strip leftmost label (e.g. 'llm') -> domain base
    parts = host.split(".")
    domain_base = ".".join(parts[1:]) if len(parts) > 2 else host
    return f"{scheme}://ocr.{domain_base}/ocr/v1/recognizeText"


def recognize_text(image_bytes: bytes, mime: str = _DEFAULT_MIME) -> str:
    """Call Yandex Vision OCR synchronously, return recognized fullText.

    Raises VisionConfigError / VisionRequestError.
    """
    import requests  # local import, mirrors ai_provider style

    api_key = getattr(settings, "AI_API_KEY", "") or ""
    folder_id = getattr(settings, "AI_FOLDER_ID", "") or ""
    timeout = float(getattr(settings, "AI_TIMEOUT", 30.0) or 30.0)
    if not api_key:
        raise VisionConfigError("AI_API_KEY is not set for OCR.")
    if not folder_id:
        raise VisionConfigError("AI_FOLDER_ID is not set for OCR.")

    if mime not in _ALLOWED_MIME:
        mime = _DEFAULT_MIME

    content_b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "mimeType": mime,
        "languageCodes": list(getattr(settings, "OCR_LANGUAGE_CODES", ["ru", "en"])),
        "model": getattr(settings, "OCR_MODEL", "page"),
        "content": content_b64,
    }
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
        "x-folder-id": folder_id,
    }
    url = _ocr_url()
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    except requests.RequestException as exc:
        raise VisionRequestError(f"OCR request failed: {exc}") from exc

    if resp.status_code != 200:
        raise VisionRequestError(f"OCR HTTP {resp.status_code}: {resp.text[:400]}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise VisionRequestError(f"OCR returned non-JSON: {resp.text[:400]}") from exc

    result = data.get("result") or data
    ta = (result or {}).get("textAnnotation") or {}
    full_text = ta.get("fullText", "") or ""
    return full_text.strip()


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences the model may add."""
    t = text.strip()
    if t.startswith("```"):
        t = _FENCE_RE.sub("", t)
    return t.strip()


def _extract_model() -> str:
    """Model id for name extraction (default: AI_TEXT_MODEL, override via env)."""
    return (
        getattr(settings, "AI_VISION_EXTRACT_MODEL", "")
        or getattr(settings, "AI_TEXT_MODEL", "")
        or "yandexgpt-lite"
    )


def _category_choices() -> List[Tuple[str, str]]:
    """Active categories as (slug, name_ru), to constrain the model's output."""
    # local import keeps this module importable without app registry at import time
    from apps.fridge.models import ProductCategory

    return list(
        ProductCategory.objects.filter(is_active=True)
        .order_by("sort_order", "name_ru")
        .values_list("slug", "name_ru")
    )


def _categories_block() -> str:
    """Human-readable allowed-categories list for the prompt; empty if none."""
    choices = _category_choices()
    if not choices:
        return ""
    lines = ", ".join(f"{slug} ({name})" for slug, name in choices)
    return (
        "Поле category выбирай ТОЛЬКО из этого списка slug'ов "
        f"(если ни один не подходит — пустая строка): {lines}. "
    )


_RULES = (
    "Правила для name: это сам ПРОДУКТ, а не бренд, не производитель и не "
    "служебный текст с этикетки. Бренд/марку в name не включай. "
    "Пример: текст 'ЯСНЫЕ ЗОРИ Полуфабрикат из мяса' -> name='полуфабрикат из мяса'. "
    "Исправляй очевидные опечатки OCR. name — на русском, в нижнем регистре, кратко. "
)


def _system_single() -> str:
    return (
        "Ты помощник для распознавания продуктов питания по тексту с упаковки. "
        "На вход дан зашумлённый текст OCR с этикетки (возможны опечатки и мусор). "
        + _RULES
        + _categories_block()
        + "Определи ОДИН продукт. Верни СТРОГО JSON без пояснений и без markdown, формат: "
        '{"name":"название продукта",'
        '"category":"slug категории или пустая строка",'
        '"quantity":"масса или объём если есть, иначе null",'
        '"confidence":0.0}. '
        "confidence — число от 0 до 1. Если текст не относится к еде — name=null."
    )


def _system_multi() -> str:
    return (
        "Ты помощник для распознавания продуктов питания по тексту с фото. "
        "На вход дан зашумлённый текст OCR (возможны опечатки и мусор), на фото может быть "
        "НЕСКОЛЬКО продуктов. "
        + _RULES
        + _categories_block()
        + "Определи все продукты. Верни СТРОГО JSON-массив без пояснений и без markdown: "
        '[{"name":"название продукта",'
        '"category":"slug категории или пустая строка",'
        '"quantity":"масса/объём или null",'
        '"confidence":0.0}]. '
        "confidence — число от 0 до 1. Если еды нет — верни []."
    )


def _coerce_item(obj: dict) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not name or not str(name).strip():
        return None
    conf = obj.get("confidence", 0.0)
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    qty = obj.get("quantity")
    if isinstance(qty, str) and qty.strip().lower() in ("", "null", "none"):
        qty = None
    return {
        "name": str(name).strip(),
        "category": (str(obj.get("category")).strip() if obj.get("category") else ""),
        "quantity": qty,
        "confidence": conf,
    }


def extract_products(ocr_text: str, mode: str = "single") -> List[dict]:
    """Turn noisy OCR text into structured product dict(s) via text LLM.

    Returns a list (length 1 for single mode, 0..N for multi). Empty list if
    nothing food-like was found.
    """
    ocr_text = (ocr_text or "").strip()
    if not ocr_text:
        return []

    multi = str(mode).lower() == "multi"
    system = _system_multi() if multi else _system_single()
    model = _extract_model()

    client = get_ai_client()
    # ai_provider builds gpt://<folder>/<model>/latest from AI_TEXT_MODEL.
    # Override the model only for the Yandex client (it understands bare model
    # ids); leave other providers (e.g. Anthropic) untouched to avoid passing
    # a Yandex model id to them.
    if type(client).__name__ == "YandexAIClient":
        setattr(client, "_text_model", model)

    try:
        raw = client.complete(
            prompt=ocr_text,
            system=system,
            max_tokens=400 if multi else 200,
            temperature=0.0,
        )
    except AIRequestError as exc:
        raise VisionRequestError(f"Name extraction failed: {exc}") from exc

    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except ValueError:
        # last resort: try to find a JSON object/array inside the text
        m = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if not m:
            return []
        try:
            parsed = json.loads(m.group(1))
        except ValueError:
            return []

    items: List[dict] = []
    if isinstance(parsed, list):
        for o in parsed:
            it = _coerce_item(o)
            if it:
                items.append(it)
    elif isinstance(parsed, dict):
        it = _coerce_item(parsed)
        if it:
            items.append(it)

    if not multi:
        items = items[:1]
    return items


def recognize_products(
    image_bytes: bytes, mime: str = _DEFAULT_MIME, mode: str = "single"
) -> Tuple[List[dict], str]:
    """Full pipeline. Returns (products, raw_ocr_text)."""
    raw_text = recognize_text(image_bytes, mime=mime)
    products = extract_products(raw_text, mode=mode)
    return products, raw_text
