# MG_PRODALIAS — alias-aware product resolution (synonyms fold to ONE Product).
import re
import unicodedata

# Visually identical latin->cyrillic glyphs (handles "C1" with latin C, etc.).
_HOMO = str.maketrans({"a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у", "k": "к", "m": "м"})
# Trailing egg-grade tokens (С0/С1/С2/СО/СВ/ВС/В/Д), only after another word.
_GRADE_RE = re.compile(r"(?<=\S)\s+(с[0-9]|со|св|вс|в|д)$")
# Leading quantity + optional unit ("10 яиц", "2 кг ...").
_LEADQTY_RE = re.compile(r"^\d+[.,]?\d*\s*(кг|г|мл|л|шт|штук[аи]?)?\s+")
_BRACKET_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_QUOTED_RE = re.compile(r"[«\"'][^«»\"']*[»\"']")


def normalize_alias(name):
    """Canonical key for matching: lower, ё→е, homoglyphs, drop brand/qty/grade.

    MG_COMBINING: перед всем прочим — приведение юникода к составленной форме
    (NFC). «Яйцо» из скачанного рецепта пришло пятью символами: «Я», «и»,
    U+0306 (комбинирующая кратка), «ц», «о». Выглядит как «й», но им не
    является, и такая запись не совпадает ни с чем: не находится поиском, не
    попадает в группу дедупа, не наводится по имени ингредиента. На проде она
    жила в каталоге невидимкой (#1803) и давала отдельную строку «Яйцо» в
    каждом списке покупок — рядом с «Яйца куриные».

    NFC собирает «и»+кратку обратно в «й», и запись становится обычной.
    Одиночные значки, которым не с чем соединяться, отбрасываем: в ключе
    сравнения им делать нечего.
    """
    s = unicodedata.normalize("NFC", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.strip().lower().replace("ё", "е")
    s = s.translate(_HOMO)
    s = _BRACKET_RE.sub(" ", s)
    s = _QUOTED_RE.sub(" ", s)
    s = re.sub(r"[«»\"'()\[\]{}]", " ", s)
    s = _LEADQTY_RE.sub("", s)
    s = re.sub(r"[.,;:!?]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _GRADE_RE.sub("", s).strip()
    return s


def product_ref_index():
    """norm/alias -> {id, name, slug, cat_id}. Includes Product names + ProductAlias.

    MG_PRODFAMILY: индекс строится по общему каталогу. Им пользуются рецепты и
    импорт — то, что общее для всех; продукты отдельных семей туда попадать не
    должны, иначе ингредиент рецепта привяжется к чужой «Маминой настойке».
    """
    from .models import Product, ProductAlias
    from .visibility import catalog_q

    idx = {}
    for p in (
        Product.objects.filter(catalog_q())
        .select_related("category_fk")
        .only("id", "name", "category_fk__slug", "category_fk__id")
    ):
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


def resolve_product(name, family=None):
    """Return canonical Product for a raw name (alias → else normalized name).

    MG_PRODFAMILY: `family` задаёт область поиска — каталог плюс продукты этой
    семьи. Без неё ищем только по каталогу: синоним не должен приводить к
    продукту чужой семьи.
    """
    from .models import Product, ProductAlias
    from .visibility import visible_products_q

    n = normalize_alias(name)
    if not n:
        return None
    scope = visible_products_q(family=family)
    a = (
        ProductAlias.objects.select_related("product")
        .filter(alias_norm=n)
        .filter(product__in=Product.objects.filter(scope))
        .first()
    )
    if a is not None:
        return a.product
    for p in Product.objects.filter(scope).only("id", "name"):
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
