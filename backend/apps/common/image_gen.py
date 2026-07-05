"""
YandexART image generation (async foundation-models API).

Pipeline:
  1) POST {host}/foundationModels/v1/imageGenerationAsync  -> operation id
  2) poll GET {host}/operations/<id> until done            -> base64 image
  3) decode base64 -> JPEG bytes

Configuration comes from settings/env (no hardcoded keys/urls/models). The
host is derived from AI_BASE_URL's root (the trailing "/v1" is stripped) unless
AI_IMAGE_BASE_URL overrides it. The same Api-Key and folder as the text/OCR
clients are reused.

Depends only on `requests` (already in requirements).

Public API:
    bytes_jpeg = generate_image("a photo of ...", seed=123)
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Optional

from django.conf import settings


class ImageGenConfigError(RuntimeError):
    """Raised when image-generation configuration is missing or invalid."""


class ImageGenError(RuntimeError):
    """Raised when the upstream image-generation request fails."""


def _host_root() -> str:
    """Foundation-models host root, e.g. 'https://llm.api.cloud.yandex.net'.

    Priority: AI_IMAGE_BASE_URL override, else AI_BASE_URL with a trailing
    '/v1' (or any path) stripped down to scheme://host.
    """
    override = (getattr(settings, "AI_IMAGE_BASE_URL", "") or "").strip()
    if override:
        return override.rstrip("/")
    base = (getattr(settings, "AI_BASE_URL", "") or "").strip()
    if not base:
        raise ImageGenConfigError("AI_BASE_URL is not set; cannot derive image endpoint.")
    m = re.match(r"^(https?://[^/]+)", base)
    if not m:
        raise ImageGenConfigError(f"AI_BASE_URL is malformed: {base!r}")
    return m.group(1)


def _clean_key(raw: str) -> str:
    """Снять случайные обёртки вокруг ключа: пробелы, кавычки, угловые скобки.

    Защита от опечаток в .env вроде AI_IMAGE_API_KEY=<AQV...age> (брекеты из
    плейсхолдера) — Yandex иначе отдаёт 401 «Unknown api key».
    """
    k = (raw or "").strip()
    if len(k) >= 2 and ((k[0] == k[-1] and k[0] in "\"'") or (k[0] == "<" and k[-1] == ">")):
        k = k[1:-1].strip()
    return k


def _model_uri() -> str:
    """Build art://<folder>/<model>/latest unless a full URI was provided."""
    model = (getattr(settings, "AI_IMAGE_MODEL", "") or "yandex-art").strip()
    if model.startswith("art://"):
        return model
    # ART runs under its own service account/folder ("menugen-image"); allow a
    # dedicated folder, fall back to the shared text folder.
    folder_id = (getattr(settings, "AI_IMAGE_FOLDER_ID", "") or getattr(settings, "AI_FOLDER_ID", "") or "").strip()
    if not folder_id:
        raise ImageGenConfigError("AI_IMAGE_FOLDER_ID/AI_FOLDER_ID is not set for image generation.")
    return f"art://{folder_id}/{model}/latest"


def generate_image(
    prompt: str,
    seed: Optional[int] = None,
    width_ratio: int = 1,
    height_ratio: int = 1,
    *,
    poll_timeout: Optional[float] = None,
    poll_interval: Optional[float] = None,
) -> bytes:
    """Generate one image from `prompt` and return decoded JPEG bytes.

    Blocks until the async operation finishes or `poll_timeout` elapses.
    Raises ImageGenConfigError / ImageGenError.
    """
    import requests  # local import, mirrors ai_provider/vision style

    prompt = (prompt or "").strip()
    if not prompt:
        raise ImageGenConfigError("Empty prompt for image generation.")

    # Dedicated image SA key ("menugen-image"); fall back to the shared key.
    api_key = _clean_key(getattr(settings, "AI_IMAGE_API_KEY", "") or getattr(settings, "AI_API_KEY", ""))
    if not api_key:
        raise ImageGenConfigError("AI_IMAGE_API_KEY/AI_API_KEY is not set for image generation.")

    req_timeout = float(getattr(settings, "AI_IMAGE_TIMEOUT", 30.0) or 30.0)
    poll_timeout = float(
        poll_timeout if poll_timeout is not None else getattr(settings, "AI_IMAGE_POLL_TIMEOUT", 120.0)
    )
    poll_interval = float(
        poll_interval if poll_interval is not None else getattr(settings, "AI_IMAGE_POLL_INTERVAL", 2.0)
    )

    host = _host_root()
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": _model_uri(),
        "generationOptions": {
            "aspectRatio": {"widthRatio": str(width_ratio), "heightRatio": str(height_ratio)},
            "mimeType": "image/jpeg",
        },
        "messages": [{"weight": "1", "text": prompt}],
    }
    if seed is not None:
        payload["generationOptions"]["seed"] = str(seed)

    # 1) start async operation
    start_url = f"{host}/foundationModels/v1/imageGenerationAsync"
    try:
        resp = requests.post(start_url, headers=headers, data=json.dumps(payload), timeout=req_timeout)
    except requests.RequestException as exc:
        raise ImageGenError(f"Image generation request failed: {exc}") from exc
    if resp.status_code != 200:
        raise ImageGenError(f"Image generation HTTP {resp.status_code}: {resp.text[:500]}")
    try:
        op = resp.json()
        op_id = op["id"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ImageGenError(f"Unexpected start response: {resp.text[:500]}") from exc

    # 2) poll the operation
    poll_url = f"{host}/operations/{op_id}"
    deadline = time.monotonic() + poll_timeout
    while True:
        try:
            pr = requests.get(poll_url, headers=headers, timeout=req_timeout)
        except requests.RequestException as exc:
            raise ImageGenError(f"Operation poll failed: {exc}") from exc
        if pr.status_code != 200:
            raise ImageGenError(f"Operation poll HTTP {pr.status_code}: {pr.text[:500]}")
        try:
            data = pr.json()
        except ValueError as exc:
            raise ImageGenError(f"Operation poll non-JSON: {pr.text[:400]}") from exc

        if data.get("done"):
            if "error" in data and data["error"]:
                raise ImageGenError(f"Image generation error: {data['error']}")
            b64 = ((data.get("response") or {}).get("image")) or ""
            if not b64:
                raise ImageGenError(f"Operation done but no image: {str(data)[:500]}")
            try:
                return base64.b64decode(b64)
            except (ValueError, TypeError) as exc:
                raise ImageGenError("Failed to decode generated image base64.") from exc

        if time.monotonic() >= deadline:
            raise ImageGenError(f"Image generation timed out after {poll_timeout:.0f}s (op {op_id}).")
        time.sleep(poll_interval)
