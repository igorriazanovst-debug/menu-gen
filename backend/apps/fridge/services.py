"""Fridge services: OpenFoodFacts lookup + menu-usage stats."""

from __future__ import annotations

import datetime
import logging
import os
import uuid
from functools import lru_cache
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


_IMAGE_EXT_BY_CTYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def download_image_to_media(src_url: str, subdir: str = "product_images") -> Optional[str]:
    """MG_OFFIMG: скачать изображение и положить в MEDIA (self-host).

    Возвращает абсолютный URL (BACKEND_PUBLIC_URL + /media/...), либо относительный
    /media/..., если публичный URL бэкенда не задан. Так картинка не зависит от
    доступности провайдера/прокси (никаких 424 и блокировок хотлинка на показе).
    """
    if not src_url:
        return None
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")
    timeout = getattr(settings, "OPENVERSE_TIMEOUT", 15.0)
    try:
        r = requests.get(src_url, headers={"User-Agent": ua}, timeout=timeout)
    except requests.RequestException as e:
        logger.warning("image download failed for %s: %s", src_url, e)
        return None
    if r.status_code != 200:
        logger.warning("image download status=%s for %s", r.status_code, src_url)
        return None
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        return None
    data = r.content
    if not data or len(data) > 12_000_000:  # защита от пустых/огромных файлов
        return None
    ext = _IMAGE_EXT_BY_CTYPE.get(ctype, "jpg")
    dest_dir = os.path.join(settings.MEDIA_ROOT, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    fname = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(dest_dir, fname), "wb") as f:
        f.write(data)
    rel = f"{str(settings.MEDIA_URL).rstrip('/')}/{subdir}/{fname}"
    public = (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")
    return (public + rel) if public else rel


def fetch_pixabay_image_url(query: str) -> Optional[str]:
    """MG_OFFIMG: фуд-фото продукта из Pixabay (нужен бесплатный ключ) + self-host.

    Курируемый сток с фильтром category=food — намного релевантнее свалки CC.
    Ключ — settings.PIXABAY_API_KEY (env PIXABAY_API_KEY). Без ключа возвращает None.
    """
    key = getattr(settings, "PIXABAY_API_KEY", "") or ""
    if not query or not key:
        return None
    timeout = getattr(settings, "OPENVERSE_TIMEOUT", 15.0)
    lang = getattr(settings, "PIXABAY_LANG", "ru") or "ru"
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")
    params = {
        "key": key,
        "q": query,
        "image_type": "photo",
        "category": "food",  # ключевой фильтр релевантности
        "safesearch": "true",
        "per_page": 5,
        "lang": lang,
    }
    try:
        r = requests.get("https://pixabay.com/api/", params=params, headers={"User-Agent": ua}, timeout=timeout)
    except (requests.RequestException, ValueError) as e:
        logger.warning("Pixabay search q=%s failed: %s", query, e)
        return None
    if r.status_code != 200:
        logger.warning("Pixabay status=%s for q=%s", r.status_code, query)
        return None
    for hit in (r.json() or {}).get("hits", []) or []:
        src = hit.get("webformatURL") or hit.get("largeImageURL")
        local = download_image_to_media(src) if src else None
        if local:
            return local
    return None


@lru_cache(maxsize=4096)
def translate_product_name_to_en(name: str) -> str:
    """MG_OFFIMG: RU→EN название продукта (для релевантного поиска фото).

    Использует AI-клиент проекта. Кэшируется в процессе. При ошибке/недоступности
    возвращает исходное имя (тогда поиск идёт по нему).
    """
    q = (name or "").strip()
    if not q:
        return q
    try:
        from apps.common.ai_provider import get_ai_client

        system = (
            "Translate the food product name to English. "
            "Answer with ONLY a short lowercase noun phrase, no quotes, no explanation."
        )
        raw = get_ai_client().complete(prompt=q, system=system, max_tokens=12, temperature=0.0)
        en = (raw or "").strip().splitlines()[0].strip().strip("\"'. ")
        if en and all(ord(c) < 128 for c in en) and len(en) <= 40:
            return en.lower()
    except Exception as e:  # перевод не критичен — тихо откатываемся на исходное имя
        logger.warning("translate '%s' failed: %s", q, e)
    return q


def fetch_wikimedia_image_url(query: str) -> Optional[str]:
    """MG_OFFIMG: фото продукта из Wikimedia Commons (CC) + self-host.

    Ищем файлы (namespace 6) по запросу, берём первый растровый (jpeg/png/webp),
    скачиваем масштабированный thumb к себе.
    """
    if not query:
        return None
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")
    timeout = getattr(settings, "OPENVERSE_TIMEOUT", 15.0)
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": 800,
    }
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php", params=params, headers={"User-Agent": ua}, timeout=timeout
        )
    except (requests.RequestException, ValueError) as e:
        logger.warning("Wikimedia search q=%s failed: %s", query, e)
        return None
    if r.status_code != 200:
        logger.warning("Wikimedia status=%s for q=%s", r.status_code, query)
        return None
    pages = ((r.json() or {}).get("query") or {}).get("pages") or {}
    for p in sorted(pages.values(), key=lambda x: x.get("index", 1_000_000)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        src = info.get("thumburl") or info.get("url")
        local = download_image_to_media(src) if src else None
        if local:
            return local
    return None


def fetch_product_image_url(name: str) -> Optional[str]:
    """MG_OFFIMG: единая точка получения фото продукта.

    По умолчанию (PRODUCT_IMAGE_SOURCE=wikimedia): Wikimedia Commons по
    английскому названию (перевод RU→EN), фолбэк — Openverse. Pixabay блокируется
    сетью части серверов, поэтому в цепочку по умолчанию не входит (можно включить
    PRODUCT_IMAGE_SOURCE=pixabay).
    """
    source = getattr(settings, "PRODUCT_IMAGE_SOURCE", "wikimedia")
    if source == "pixabay":
        url = fetch_pixabay_image_url(name)
        if url:
            return url

    en = translate_product_name_to_en(name)
    queries = [en] + ([name] if name and name != en else [])
    for q in queries:
        url = fetch_wikimedia_image_url(q)
        if url:
            return url
    return fetch_openverse_image_url(en or name)


def fetch_openverse_image_url(query: str) -> Optional[str]:
    """MG_OFFIMG: найти фото продукта в Openverse (CC, без ключа) и self-host'ить.

    Ищем по названию (как есть), скачиваем найденную картинку к себе в media и
    возвращаем НАШ URL. По умолчанию берём лицензии, пригодные для коммерческого
    использования (OPENVERSE_LICENSE_TYPE).
    """
    if not query:
        return None
    base = getattr(settings, "OPENVERSE_BASE_URL", "https://api.openverse.org")
    timeout = getattr(settings, "OPENVERSE_TIMEOUT", 15.0)
    license_type = getattr(settings, "OPENVERSE_LICENSE_TYPE", "commercial")
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")
    params = {"q": query, "page_size": 5, "mature": "false"}
    if license_type:
        params["license_type"] = license_type
    try:
        r = requests.get(f"{base}/v1/images/", params=params, headers={"User-Agent": ua}, timeout=timeout)
    except (requests.RequestException, ValueError) as e:
        logger.warning("Openverse search q=%s failed: %s", query, e)
        return None
    if r.status_code != 200:
        logger.warning("Openverse status=%s for q=%s", r.status_code, query)
        return None
    for item in (r.json() or {}).get("results", []) or []:
        # Сначала прямая ссылка на изображение, затем thumbnail-прокси Openverse.
        for src in (item.get("url"), item.get("thumbnail")):
            local = download_image_to_media(src) if src else None
            if local:
                return local
    return None


def fetch_off_image_url(barcode: Optional[str] = None, name: Optional[str] = None) -> Optional[str]:
    """MG_OFFIMG: URL изображения продукта из OpenFoodFacts (свободно к использованию).

    Сначала пробуем по штрих-коду (точный товар), затем — поиском по названию
    (для продуктов без штрих-кода, напр. овощи/фрукты). Возвращает URL или None.
    """
    base = getattr(settings, "OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org")
    timeout = getattr(settings, "OPENFOODFACTS_TIMEOUT", 4.0)
    # Поиск по названию (search.pl) заметно медленнее запроса по штрих-коду —
    # даём ему отдельный, увеличенный таймаут, иначе часты Read timed out.
    search_timeout = getattr(settings, "OPENFOODFACTS_SEARCH_TIMEOUT", 20.0)
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")
    headers = {"User-Agent": ua}

    def _pick(prod: dict) -> Optional[str]:
        img = prod.get("image_front_url") or prod.get("image_url") or prod.get("image_small_url")
        return img[:1024] if img else None

    if barcode:
        try:
            r = requests.get(f"{base}/api/v2/product/{barcode}.json", headers=headers, timeout=timeout)
            if r.status_code == 200:
                img = _pick((r.json() or {}).get("product") or {})
                if img:
                    return img
        except (requests.RequestException, ValueError) as e:
            logger.warning("OFF image by barcode=%s failed: %s", barcode, e)

    if name:
        try:
            params = {
                "search_terms": name,
                "json": 1,
                "page_size": 5,
                "fields": "image_front_url,image_url,image_small_url,product_name",
            }
            r = requests.get(f"{base}/cgi/search.pl", params=params, headers=headers, timeout=search_timeout)
            if r.status_code == 200:
                for prod in (r.json() or {}).get("products", []) or []:
                    img = _pick(prod)
                    if img:
                        return img
        except (requests.RequestException, ValueError) as e:
            logger.warning("OFF image search name=%s failed: %s", name, e)

    return None


def fetch_product_from_off(barcode: str) -> Optional[Product]:
    # MENUGEN_BARCODE_FETCH: OFF lookup + category_fk mapping + GPT fallbacks.
    base = getattr(settings, "OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org")
    timeout = getattr(settings, "OPENFOODFACTS_TIMEOUT", 4.0)
    ua = getattr(settings, "OPENFOODFACTS_USER_AGENT", "MenuGen/1.0")

    raw_off = {}
    fields = None
    url = f"{base}/api/v2/product/{barcode}.json"
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
        if r.status_code == 200:
            body = r.json()
            if body.get("status") == 1:
                raw_off = body.get("product") or {}
                fields = _normalize_off_product(raw_off)
        else:
            logger.info("OFF returned status=%s for barcode=%s", r.status_code, barcode)
    except (requests.RequestException, ValueError) as e:
        logger.warning("OFF request failed for barcode=%s: %s", barcode, e)

    category_fk = None
    if fields:
        # OFF hit: resolve category_fk (deterministic, GPT only if 'other').
        category_fk = _resolve_category_fk(fields, raw_off)
        # KBJU gap -> GPT fill by name.
        if not fields.get("nutrition") and fields.get("calories_per_100g") is None:
            cals, nutrition = gpt_fill_nutrition(fields.get("name", ""))
            if cals is not None:
                fields["calories_per_100g"] = cals
            if nutrition:
                fields["nutrition"] = nutrition
    else:
        # OFF miss: last-resort GPT lookup by barcode (low confidence).
        fields = gpt_lookup_by_barcode(barcode)
        if not fields:
            return None
        category_fk = _resolve_category_fk(fields, {})

    defaults = dict(fields)
    if category_fk is not None:
        defaults["category_fk"] = category_fk

    product, _ = Product.objects.update_or_create(barcode=barcode, defaults=defaults)
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
    # MENUGEN_BARCODE_GPT: ice-cream / desserts (OFF tags + RU text) -> sweets
    ("ice-cream", "sweets"),
    ("ice creams", "sweets"),
    ("icecream", "sweets"),
    ("dessert", "sweets"),
    ("морожен", "sweets"),
    ("десерт", "sweets"),
    ("пломбир", "sweets"),
    ("эскимо", "sweets"),
]


def map_off_category_to_slug(category_str: str) -> str:
    s = (category_str or "").strip().lower()
    if not s:
        return "other"
    for token, slug in _OFF_TOKEN_MAP:
        if token in s:
            return slug
    return "other"


# ── MENUGEN_BARCODE_GPT: GPT fallbacks for category / KBJU / barcode lookup ──
def _allowed_slugs() -> list:
    """Active category slugs, for constraining GPT output. Local import keeps
    this module importable without the app registry at import time."""
    from .models import ProductCategory

    return list(
        ProductCategory.objects.filter(is_active=True).order_by("sort_order", "name_ru").values_list("slug", "name_ru")
    )


def _strip_fences(text: str) -> str:
    import re as _re

    t = (text or "").strip()
    if t.startswith("```"):
        t = _re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", t, flags=_re.IGNORECASE)
    return t.strip()


def _parse_json_loose(text: str):
    import json as _json
    import re as _re

    cleaned = _strip_fences(text)
    try:
        return _json.loads(cleaned)
    except ValueError:
        m = _re.search(r"(\{.*\}|\[.*\])", cleaned, _re.DOTALL)
        if not m:
            return None
        try:
            return _json.loads(m.group(1))
        except ValueError:
            return None


def _num_or_none(v):
    import re as _re

    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _re.search(r"-?\d+(?:[.,]\d+)?", str(v))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def gpt_pick_category_slug(name: str, hints: str = "") -> str:
    """Ask the text LLM to choose ONE slug from our active categories.
    Returns a valid slug or "" on failure. Never raises."""
    from apps.common.ai_provider import AIRequestError, get_ai_client

    choices = _allowed_slugs()
    if not name or not choices:
        return ""
    listing = ", ".join(f"{slug} ({ru})" for slug, ru in choices)
    valid = {slug for slug, _ in choices}
    system = (
        "Ты классификатор продуктов питания. По названию (и подсказкам) выбери "
        "ОДНУ категорию строго из списка slug'ов. Верни СТРОГО JSON без markdown: "
        '{"category":"slug"}. Если не уверен — {"category":"other"}. '
        f"Список: {listing}."
    )
    prompt = f"Название: {name}\nПодсказки: {hints or '—'}"
    try:
        raw = get_ai_client().complete(prompt=prompt, system=system, max_tokens=40, temperature=0.0)
    except AIRequestError as exc:
        logger.warning("gpt_pick_category_slug failed for %r: %s", name, exc)
        return ""
    data = _parse_json_loose(raw) or {}
    slug = str(data.get("category", "")).strip().lower()
    return slug if slug in valid else ""


def gpt_fill_nutrition(name: str):
    """Ask the text LLM for KBJU per 100 g by product name.
    Returns (calories_per_100g|None, nutrition_dict). Never raises."""
    from apps.common.ai_provider import AIRequestError, get_ai_client

    if not name:
        return None, {}
    system = (
        "Ты нутрициолог. По названию продукта дай среднюю пищевую ценность на 100 г. "
        "Верни СТРОГО JSON без markdown: "
        '{"calories_per_100g":0,"proteins":0,"fats":0,"carbs":0,"sugars":0}. '
        "Числа на 100 г. Если продукт неизвестен — все значения null, не выдумывай."
    )
    try:
        raw = get_ai_client().complete(prompt=f"Продукт: {name}", system=system, max_tokens=120, temperature=0.0)
    except AIRequestError as exc:
        logger.warning("gpt_fill_nutrition failed for %r: %s", name, exc)
        return None, {}
    data = _parse_json_loose(raw) or {}
    cals = _num_or_none(data.get("calories_per_100g"))
    nutrition = {}
    for k in ("proteins", "fats", "carbs", "sugars"):
        v = _num_or_none(data.get(k))
        if v is not None:
            nutrition[k] = v
    return cals, nutrition


def gpt_lookup_by_barcode(barcode: str):
    """Last resort when OFF has nothing: ask the LLM to identify a product by
    its barcode (EAN). High hallucination risk -> caller marks low confidence.
    Returns a normalized fields dict (like _normalize_off_product) or None."""
    from apps.common.ai_provider import AIRequestError, get_ai_client

    if not barcode:
        return None
    system = (
        "Ты определяешь продукт питания по штрих-коду (EAN). Если НЕ знаешь товар "
        "точно — верни name=null, НЕ выдумывай. Верни СТРОГО JSON без markdown: "
        '{"name":"...","calories_per_100g":0,"proteins":0,"fats":0,"carbs":0,"sugars":0}.'
    )
    try:
        raw = get_ai_client().complete(prompt=f"Штрих-код: {barcode}", system=system, max_tokens=160, temperature=0.0)
    except AIRequestError as exc:
        logger.warning("gpt_lookup_by_barcode failed for %s: %s", barcode, exc)
        return None
    data = _parse_json_loose(raw) or {}
    name = str(data.get("name")).strip() if data.get("name") else ""
    if not name or name.lower() in ("null", "none"):
        return None
    cals = _num_or_none(data.get("calories_per_100g"))
    nutrition = {}
    for k in ("proteins", "fats", "carbs", "sugars"):
        v = _num_or_none(data.get(k))
        if v is not None:
            nutrition[k] = v
    return {
        "name": name[:255],
        "category": "",
        "default_unit": "",
        "calories_per_100g": cals,
        "nutrition": nutrition,
        "image_url": None,
    }


def _resolve_category_fk(fields: dict, raw_off: dict):
    """Map OFF text+tags to a category_fk; GPT fallback if mapping is 'other'.
    Returns a ProductCategory instance or None. Never raises."""
    from .models import ProductCategory

    text = fields.get("category") or ""
    tags = []
    if isinstance(raw_off, dict):
        tags = raw_off.get("categories_tags") or []
    hint = " ".join([text] + [str(t) for t in tags])
    slug = map_off_category_to_slug(hint)
    if slug == "other":
        gpt_slug = gpt_pick_category_slug(fields.get("name", ""), hints=hint)
        if gpt_slug:
            slug = gpt_slug
    return ProductCategory.objects.filter(is_active=True, slug=slug).first()


# ── MENUGEN_ENRICH_EXISTING: fix a cached Product missing category_fk / KBJU ──
def enrich_existing_product(product) -> bool:
    """Backfill category_fk and/or nutrition on an existing Product in place.
    Uses deterministic category mapping (legacy text), GPT fallbacks otherwise.
    Returns True if anything changed. Never raises."""
    updates = []

    # category_fk: map from legacy text; GPT only if mapping gives 'other'.
    if product.category_fk_id is None:
        from .models import ProductCategory

        slug = map_off_category_to_slug(product.category or "")
        if slug == "other":
            gpt_slug = gpt_pick_category_slug(product.name or "", hints=product.category or "")
            if gpt_slug:
                slug = gpt_slug
        cat = ProductCategory.objects.filter(is_active=True, slug=slug).first()
        if cat is not None:
            product.category_fk = cat
            updates.append("category_fk")

    # KBJU: fill only if completely missing.
    if not product.nutrition and product.calories_per_100g is None:
        cals, nutrition = gpt_fill_nutrition(product.name or "")
        if cals is not None:
            product.calories_per_100g = cals
            updates.append("calories_per_100g")
        if nutrition:
            product.nutrition = nutrition
            updates.append("nutrition")

    if updates:
        product.save(update_fields=updates)
        return True
    return False
