"""OpenFoodFacts integration: barcode → Product (cached locally)."""
from __future__ import annotations

import logging
from typing import Optional

import requests
from django.conf import settings

from .models import Product

logger = logging.getLogger(__name__)


def _normalize_off_product(raw: dict) -> Optional[dict]:
    """Map OFF product JSON to our Product fields. Returns None if no name."""
    name = (
        raw.get("product_name_ru")
        or raw.get("product_name")
        or raw.get("generic_name_ru")
        or raw.get("generic_name")
        or ""
    ).strip()
    if not name:
        return None

    nutriments = raw.get("nutriments") or {}
    calories = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal")
    try:
        calories = float(calories) if calories is not None else None
    except (TypeError, ValueError):
        calories = None

    nutrition = {}
    for key, off_key in (
        ("proteins", "proteins_100g"),
        ("fats", "fat_100g"),
        ("carbs", "carbohydrates_100g"),
        ("fiber", "fiber_100g"),
        ("sugars", "sugars_100g"),
    ):
        v = nutriments.get(off_key)
        try:
            if v is not None:
                nutrition[key] = float(v)
        except (TypeError, ValueError):
            pass

    image = (
        raw.get("image_front_url")
        or raw.get("image_url")
        or raw.get("image_small_url")
    )

    category = (raw.get("categories") or "").split(",")[0].strip() if raw.get("categories") else ""

    return {
        "name": name[:255],
        "category": category[:100],
        "default_unit": "",
        "calories_per_100g": calories,
        "nutrition": nutrition,
        "image_url": image[:1024] if image else None,
    }


def fetch_product_from_off(barcode: str) -> Optional[Product]:
    """Fetch from OFF API, save into local Product table, return it. None if not found."""
    base = getattr(settings, "OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org")
    timeout = getattr(settings, "OPENFOODFACTS_TIMEOUT", 4.0)
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")

    url = f"{base}/api/v2/product/{barcode}.json"
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
    except requests.RequestException as e:
        logger.warning("OFF request failed for barcode=%s: %s", barcode, e)
        return None

    if r.status_code != 200:
        logger.info("OFF returned status=%s for barcode=%s", r.status_code, barcode)
        return None

    try:
        body = r.json()
    except ValueError:
        return None

    if body.get("status") != 1:
        return None

    fields = _normalize_off_product(body.get("product") or {})
    if not fields:
        return None

    product, _created = Product.objects.update_or_create(
        barcode=barcode,
        defaults=fields,
    )
    return product
