# MG_PRODALIAS — alias-aware product resolution (synonyms fold to ONE Product).
import re

# Visually identical latin->cyrillic glyphs (handles "C1" with latin C, etc.).
_HOMO = str.maketrans({"a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у", "k": "к", "m": "м"})
# Trailing egg-grade tokens (С0/С1/С2/СО/СВ/ВС/В/Д), only after another word.
_GRADE_RE = re.compile(r"(?<=\S)\s+(с[0-9]|со|св|вс|в|д)$")
# Leading quantity + optional unit ("10 яиц", "2 кг ...").
_LEADQTY_RE = re.compile(r"^\d+[.,]?\d*\s*(кг|г|мл|л|шт|штук[аи]?)?\s+")
_BRACKET_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_QUOTED_RE = re.compile(r"[«\"'][^«»\"']*[»\"']")


def normalize_alias(name):
    """Canonical key for matching: lower, ё→е, homoglyphs, drop brand/qty/grade."""
    s = (name or "").strip().lower().replace("ё", "е")
    s = s.translate(_HOMO)
    s = _BRACKET_RE.sub(" ", s)
    s = _QUOTED_RE.sub(" ", s)
    s = re.sub(r"[«»\"'()\[\]{}]", " ", s)
    s = _LEADQTY_RE.sub("", s)
    s = re.sub(r"[.,;:!?]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _GRADE_RE.sub("", s).strip()
    return s


# MG_ALLERGEN: короткие служебные слова, которые НЕ должны становиться базой
# при схлопывании («филе куриное» → «куриное», а не «филе»).
_ALLERGEN_STOPWORDS = {"филе", "мясо", "масло", "сок", "паста", "смесь"}


def canonical_allergen(name):
    """Базовое слово-аллерген для схлопывания вариантов продукта в один.

    Каталог именуется «существительное + уточнение» («Сыр гауда», «Сыр
    тёртый», «Молоко 2.5%», «Творог 5%»), поэтому первое значимое слово
    нормализованного имени — это базовый продукт. Так «Сыр гауда» и «Сыр
    тёртый» схлопываются в «сыр», и один аллерген «сыр» (подстрочный матч в
    генераторе) исключает все варианты сыра.

    Возвращает пустую строку для пустого/мусорного имени.
    """
    n = normalize_alias(name)
    if not n:
        return ""
    tokens = n.split(" ")
    first = tokens[0]
    # Если первое слово — служебное (масло/сок/филе…), а дальше есть
    # содержательное слово, берём именно его: «филе куриное» → «куриное».
    if first in _ALLERGEN_STOPWORDS and len(tokens) > 1:
        return tokens[1]
    return first


def product_ref_index():
    """norm/alias -> {id, name, slug, cat_id}. Includes Product names + ProductAlias."""
    from .models import Product, ProductAlias

    idx = {}
    for p in Product.objects.select_related("category_fk").only("id", "name", "category_fk__slug", "category_fk__id"):
        n = normalize_alias(p.name)
        if n and n not in idx:
            cat = p.category_fk
            idx[n] = {"id": p.id, "name": p.name, "slug": cat.slug if cat else "", "cat_id": cat.id if cat else None}
    for a in ProductAlias.objects.select_related("product", "product__category_fk"):
        cat = a.product.category_fk
        idx[a.alias_norm] = {
            "id": a.product_id,
            "name": a.product.name,
            "slug": cat.slug if cat else "",
            "cat_id": cat.id if cat else None,
        }
    return idx


def resolve_ref(name, index):
    """Dict ref via prebuilt index (no DB hit)."""
    n = normalize_alias(name)
    return index.get(n) if n else None


def resolve_product(name):
    """Return canonical Product for a raw name (alias → else normalized name)."""
    from .models import Product, ProductAlias

    n = normalize_alias(name)
    if not n:
        return None
    a = ProductAlias.objects.select_related("product").filter(alias_norm=n).first()
    if a is not None:
        return a.product
    for p in Product.objects.only("id", "name"):
        if normalize_alias(p.name) == n:
            return p
    return None


def learn_alias(name, product, source="auto"):
    """Record an alias (idempotent). Never raises."""
    from .models import ProductAlias

    n = normalize_alias(name)
    if not n or product is None:
        return None
    if normalize_alias(product.name) == n:
        return None  # equals canonical name already
    try:
        obj, _ = ProductAlias.objects.update_or_create(alias_norm=n, defaults={"product": product, "source": source})
        return obj
    except Exception:
        return None
