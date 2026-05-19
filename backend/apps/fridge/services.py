"""Fridge services: OpenFoodFacts lookup + menu-usage stats."""

from __future__ import annotations

import datetime
import logging
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from apps.menu.models import MenuItem

from .models import Product

logger = logging.getLogger(__name__)


# ── OpenFoodFacts (existing) ────────────────────────────────────────────────
def _normalize_off_product(raw: dict) -> Optional[dict]:
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

    image = raw.get("image_front_url") or raw.get("image_url") or raw.get("image_small_url")
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

    product, _ = Product.objects.update_or_create(barcode=barcode, defaults=fields)
    return product


# ── Menu usage stats ────────────────────────────────────────────────────────
def get_menu_usage_30d(family, product_name: str, days: int = 30) -> dict:
    """
    Count occurrences of a product in menu items for the given family.
    Match: case-insensitive exact match of ingredient.name == product_name.
    Period: Menu.start_date in [today - days, today].
    Returns: {"count": int, "recipes": [{"recipe_id", "title", "times"}], "period_days": days}
    """
    if not family or not product_name:
        return {"count": 0, "recipes": [], "period_days": days}

    target = product_name.strip().lower()
    if not target:
        return {"count": 0, "recipes": [], "period_days": days}

    today = timezone.now().date()
    since = today - datetime.timedelta(days=days)

    qs = MenuItem.objects.filter(
        menu__family=family,
        menu__start_date__gte=since,
        menu__start_date__lte=today,
    ).select_related("recipe")

    total = 0
    by_recipe: dict[int, dict] = {}
    for item in qs.iterator():
        recipe = item.recipe
        ingredients = recipe.ingredients or []
        if not isinstance(ingredients, list):
            continue
        match = False
        for ing in ingredients:
            if isinstance(ing, dict):
                nm = (ing.get("name") or "").strip().lower()
                if nm == target:
                    match = True
                    break
        if match:
            total += 1
            slot = by_recipe.get(recipe.id)
            if slot is None:
                by_recipe[recipe.id] = {
                    "recipe_id": recipe.id,
                    "title": recipe.title,
                    "times": 1,
                }
            else:
                slot["times"] += 1

    top = sorted(by_recipe.values(), key=lambda x: x["times"], reverse=True)[:10]
    return {"count": total, "recipes": top, "period_days": days}


# MG-609: OFF category string -> our ProductCategory slug.
_OFF_TOKEN_MAP = [
    ("dair", "dairy"),
    ("milk", "dairy"),
    ("cheese", "dairy"),
    ("yogurt", "dairy"),
    ("meat", "meat"),
    ("chicken", "meat"),
    ("beef", "meat"),
    ("pork", "meat"),
    ("sausage", "meat"),
    ("fish", "fish"),
    ("seafood", "fish"),
    ("shrimp", "fish"),
    ("vegetabl", "vegetables"),
    ("legume", "vegetables"),
    ("fruit", "fruits"),
    ("berry", "fruits"),
    ("grain", "grains"),
    ("pasta", "grains"),
    ("rice", "grains"),
    ("cereal", "grains"),
    ("bread", "bakery"),
    ("bakery", "bakery"),
    ("egg", "eggs"),
    ("oil", "oils"),
    ("sauce", "oils"),
    ("condiment", "condiments"),
    ("spice", "condiments"),
    ("beverage", "drinks"),
    ("drink", "drinks"),
    ("juice", "drinks"),
    ("water", "drinks"),
    ("frozen", "frozen"),
    ("chocolate", "sweets"),
    ("candy", "sweets"),
    ("sweet", "sweets"),
    ("biscuit", "sweets"),
]


def map_off_category_to_slug(category_str: str) -> str:
    s = (category_str or "").strip().lower()
    if not s:
        return "other"
    for token, slug in _OFF_TOKEN_MAP:
        if token in s:
            return slug
    return "other"
