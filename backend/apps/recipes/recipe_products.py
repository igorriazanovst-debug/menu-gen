# MG_RECIPELINK / MG_RECIPELINK2 — resolve recipe ingredients to rubricator products + categories.
import re
from decimal import Decimal, InvalidOperation


def _norm(s):
    s = (s or "").strip().lower().replace("\u0451", "\u0435")  # ё -> е
    s = re.sub(r"\s+", " ", s)
    return s


def _cap(s):
    s = (s or "").strip()
    return (s[:1].upper() + s[1:]) if s else s


# MG_RECIPELINK2: deterministic canon cleanup.
_NULLISH = {"", "null", "none", "nan", "n/a", "-", "—", "–"}
_PCT_RE = re.compile(r"\s*\d+(?:[.,]\d+)?\s*%")


def _clean_canon(s):
    """Strip trailing fat-percentage, normalize nullish AI answers to None."""
    s = _PCT_RE.sub("", (s or "")).strip(" ,;-—–")
    s = re.sub(r"\s+", " ", s)
    if _norm(s) in _NULLISH:
        return None
    return _cap(s)


# MG_RECIPELINK2: curated synonym -> rubricator product display name. Extend here.
_PRODUCT_ALIASES = {
    "томат": "Помидоры",
    "томаты": "Помидоры",
    "помидор": "Помидоры",
}


def _slug_or_other(slug, cat_id_by_slug):
    s = (slug or "").strip() or "other"
    return s, cat_id_by_slug.get(s)


# MG_RECIPELINK2: mechanical split of compound / alternative ingredient strings.
# Separators: comma, semicolon, slash, "или"/"либо"/"и" as standalone words.
# Parentheses are unwrapped (their content becomes split candidates).
_SPLIT_RE = re.compile(r"\s*(?:[,;/]|\bили\b|\bлибо\b|\bи\b)\s*", re.IGNORECASE)


def _split_segments(name):
    s = (name or "").replace("(", " ").replace(")", " ")
    parts = _SPLIT_RE.split(s)
    segs = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" .,-—")
        if len(p) >= 2:
            segs.append(p)
    if segs:
        return segs
    base = (name or "").strip()
    return [base] if base else []


def _to_decimal(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _allowed_categories():
    """[(slug, name_ru, cat_id)] for active categories."""
    from apps.fridge.models import ProductCategory

    return [
        (c.slug, c.name_ru, c.id)
        for c in ProductCategory.objects.filter(is_active=True).order_by("sort_order", "name_ru")
    ]


def _product_index():
    """norm(name) -> (product_id, category_slug, category_id)."""
    from apps.fridge.models import Product

    idx = {}
    for p in Product.objects.select_related("category_fk").only("id", "name", "category_fk__slug", "category_fk__id"):
        n = _norm(p.name)
        if n and n not in idx:
            cat = p.category_fk
            idx[n] = (p.id, cat.slug if cat else "", cat.id if cat else None)
    return idx


def _product_names():
    """Distinct rubricator product display names (for AI resolution)."""
    from apps.fridge.models import Product

    seen = set()
    out = []
    for p in Product.objects.only("id", "name").order_by("name"):
        nm = (p.name or "").strip()
        n = _norm(nm)
        if nm and n not in seen:
            seen.add(n)
            out.append(nm)
    return out


_SYS_CANON_CAT = (
    "Тебе дан JSON-массив объектов {i, name} — названия ингредиентов из рецептов "
    "(часто в родительном падеже, с количеством/примечаниями). Для каждого верни "
    "СТРОГО JSON-массив объектов {i, canon, slug, product}. Без markdown, без пояснений.\n"
    "canon: каноническое название продукта — ИМЕНИТЕЛЬНЫЙ падеж, ЕДИНСТВЕННОЕ "
    "число, ОБЯЗАТЕЛЬНО с заглавной буквы, порядок 'Существительное признак'. "
    "Убери количество, проценты жирности, бренд, скобки, примечания, способ "
    "приготовления (варёное, жареное, отварной) и вкусовые/маркетинговые уточнения "
    "('без вкуса', 'со вкусом ...', 'несладкий', 'обезжиренный'). СОХРАНИ "
    "вид/сорт/цвет/форму (кокосовое, замороженный, болгарский, черри, фета). "
    "Если это не продукт (мусор парсера, абзац текста, реклама) — canon=null.\n"
    "product: если ингредиент обозначает ТОТ ЖЕ продукт, что есть в СПИСКЕ ТОВАРОВ "
    "ниже (учитывая синонимы, число, регистр, падеж: напр. 'томаты' и 'помидоры' — "
    "один товар) — верни ТОЧНОЕ название из списка. Иначе product=null. Список "
    "товаров: __PRODUCTS__.\n"
    "slug: ОДНА категория строго из списка ниже (или 'other'). Список: __LISTING__."
)


def canonicalize_and_categorize(raw_names, chunk_size=30, log=None):
    """segment -> (canon|None, slug, product_name|None). One AI pass (chunked) + one retry.
    canon=None means noise (drop). Never raises."""
    import json

    _log = log if callable(log) else (lambda *a, **k: None)
    out = {}
    names = list(dict.fromkeys([n for n in raw_names if (n or "").strip()]))
    if not names:
        return out

    try:
        from apps.common.ai_provider import get_ai_client

        client = get_ai_client()
    except Exception:
        client = None
    try:
        from apps.fridge.services import _parse_json_loose
    except Exception:
        _parse_json_loose = None

    cats = _allowed_categories()
    valid_slugs = {s for s, _, _ in cats}
    listing = ", ".join("%s (%s)" % (s, ru) for s, ru, _ in cats)
    products_listing = ", ".join(_product_names())
    system = _SYS_CANON_CAT.replace("__PRODUCTS__", products_listing).replace("__LISTING__", listing)

    def _ask(indices, phase="canon"):
        if client is None or _parse_json_loose is None:
            return
        nchunks = (len(indices) + chunk_size - 1) // chunk_size
        for ci, base in enumerate(range(0, len(indices), chunk_size), 1):
            grp = indices[base : base + chunk_size]
            _log("  %s chunk %d/%d (segments %d)" % (phase, ci, nchunks, len(grp)))
            payload = json.dumps([{"i": j, "name": names[j]} for j in grp], ensure_ascii=False)
            try:
                raw = client.complete(prompt=payload, system=system, max_tokens=3000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception:
                data = None
            if not isinstance(data, list):
                continue
            for d in data:
                if not isinstance(d, dict) or "i" not in d:
                    continue
                try:
                    j = int(d["i"])
                except (TypeError, ValueError):
                    continue
                if j < 0 or j >= len(names):
                    continue
                canon = d.get("canon")
                canon = _clean_canon(canon) if isinstance(canon, str) else None
                slug = str(d.get("slug") or "").strip().lower()
                if slug not in valid_slugs:
                    slug = ""
                product = d.get("product")
                if isinstance(product, str):
                    product = product.strip() or None
                else:
                    product = None
                out[names[j]] = (canon if canon else None, slug, product)

    all_idx = list(range(len(names)))
    _ask(all_idx, "canon")
    missing = [j for j in all_idx if names[j] not in out]
    if missing:
        _ask(missing, "retry")
    # fallback for AI failures (NOT explicit null): keep raw name, no category, no product
    for j in all_idx:
        if names[j] not in out:
            out[names[j]] = (_cap(names[j]), "", None)
    return out


def _resolve_segment(canon, ai_slug, prod_name, prod_index, cat_id_by_slug, ref_index=None):  # MG_PRODALIAS
    """-> (product_id, canon_display, slug, cat_id). Honors decisions:
    name from rubricator product; category from product if present, else AI slug;
    curated synonym alias folds variants to a rubricator product; empty slug -> 'other'."""
    alias = _PRODUCT_ALIASES.get(_norm(canon))
    if alias and not prod_name:
        prod_name = alias
    pm = prod_index.get(_norm(prod_name)) if prod_name else None
    if pm:
        product_id, pslug, pcat_id = pm
        if pcat_id:
            return product_id, _cap(prod_name), pslug, pcat_id
        slug, cid = _slug_or_other(ai_slug, cat_id_by_slug)
        return product_id, _cap(prod_name), slug, cid
    # AI gave no/unknown product -> try direct exact match on canon
    dm = prod_index.get(_norm(canon)) if canon else None
    if dm:
        product_id, dslug, dcat_id = dm
        if dcat_id:
            return product_id, _cap(canon), dslug, dcat_id
        slug, cid = _slug_or_other(ai_slug, cat_id_by_slug)
        return product_id, _cap(canon), slug, cid
    # MG_PRODALIAS: alias-aware last resort fold to canonical Product.
    if ref_index is not None:
        from apps.fridge.aliases import normalize_alias

        for cand in (prod_name, canon):
            if not cand:
                continue
            ref = ref_index.get(normalize_alias(cand))
            if ref:
                rslug = ref["slug"] or _slug_or_other(ai_slug, cat_id_by_slug)[0]
                rcid = ref["cat_id"] or cat_id_by_slug.get(rslug)
                return ref["id"], _cap(ref["name"]), rslug, rcid
    slug, cid = _slug_or_other(ai_slug, cat_id_by_slug)
    return None, _cap(canon), slug, cid


# MG_T04C: guard for inline auto-creation of missing products from recipes.
def _is_seedable(canon_disp, cat_id):
    s = (canon_disp or "").strip()
    if len(s) < 2 or _norm(s) in _NULLISH:
        return False
    if re.match(r"^\d+([.,]\d+)?$", _norm(s)):
        return False
    return cat_id is not None


def rebuild_recipe_links(
    recipe, canon_map=None, prod_index=None, cat_id_by_slug=None, force=False, ref_index=None,
    create_missing=False,  # MG_T04C
):  # MG_PRODALIAS
    """(Re)build RecipeProduct rows for one recipe. Idempotent (replace).
    MG_RECIPELINK2: each ingredient name is split into segments -> N links.
    Returns number of links created."""
    from .models import RecipeProduct

    ings = recipe.ingredients or []
    if not isinstance(ings, list):
        return 0

    existing = RecipeProduct.objects.filter(recipe=recipe)
    if existing.exists() and not force:
        return 0

    segments = []
    for ing in ings:
        if isinstance(ing, dict):
            nm = (ing.get("name") or "").strip()
            if nm:
                segments.extend(_split_segments(nm))

    if canon_map is None:
        canon_map = canonicalize_and_categorize(segments)
    if prod_index is None:
        prod_index = _product_index()
    if cat_id_by_slug is None:
        cat_id_by_slug = {s: cid for s, _, cid in _allowed_categories()}
    if ref_index is None:  # MG_PRODALIAS
        from apps.fridge.aliases import product_ref_index

        ref_index = product_ref_index()

    rows = []
    seen = set()  # dedup by norm(canon) within one recipe
    for ing in ings:
        if not isinstance(ing, dict):
            continue
        nm = (ing.get("name") or "").strip()
        if not nm:
            continue
        grams = ing.get("grams")
        try:
            grams = float(grams) if grams is not None else None
        except (TypeError, ValueError):
            grams = None
        quantity = str(ing.get("quantity") or "")[:64]
        unit = (ing.get("unit") or "")[:50]
        for seg in _split_segments(nm):
            canon, ai_slug, prod_name = canon_map.get(seg, (_cap(seg), "", None))
            if not canon:
                continue  # noise -> no link
            product_id, canon_disp, slug, cat_id = _resolve_segment(
                canon, ai_slug, prod_name, prod_index, cat_id_by_slug, ref_index=ref_index
            )
            if product_id is None and create_missing and _is_seedable(canon_disp, cat_id):  # MG_T04C
                from apps.fridge.models import Product

                obj, _created = Product.objects.get_or_create(
                    name=canon_disp, defaults={"category_fk_id": cat_id, "source": "auto"}
                )
                product_id = obj.id
            key = _norm(canon_disp)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(
                RecipeProduct(
                    recipe=recipe,
                    product_id=product_id,
                    name_raw=seg[:255],
                    name_canonical=(canon_disp or "")[:255],
                    category_slug=(slug or "")[:64],
                    category_fk_id=cat_id,
                    quantity=quantity,
                    unit=unit,
                    grams=grams,  # same grams to each alternative (decision)
                )
            )

    existing.delete()
    if rows:
        RecipeProduct.objects.bulk_create(rows)
    return len(rows)


def backfill(force=False, recipe_ids=None, menu_id=None, limit=None, log=print):
    """Backfill links across recipes. Collects all distinct SEGMENTS, runs one AI
    canonicalization, builds product index once, then per-recipe rebuild."""
    from apps.menu.models import MenuItem
    from apps.recipes.models import Recipe

    from .models import RecipeProduct

    qs = Recipe.objects.all().only("id", "ingredients")
    if menu_id is not None:
        rids = list(MenuItem.objects.filter(menu_id=menu_id).values_list("recipe_id", flat=True))
        qs = qs.filter(id__in=rids)
    if recipe_ids:
        qs = qs.filter(id__in=recipe_ids)
    if limit:
        qs = qs[:limit]
    recipes = list(qs)

    segments = set()
    todo = []
    for r in recipes:
        if RecipeProduct.objects.filter(recipe=r).exists() and not force:
            continue
        todo.append(r)
        for ing in r.ingredients or []:
            if isinstance(ing, dict):
                nm = (ing.get("name") or "").strip()
                if nm:
                    segments.update(_split_segments(nm))

    log("recipes_total=%d todo=%d distinct_segments=%d" % (len(recipes), len(todo), len(segments)))
    log(">>> AI canonicalization (chunked, slow provider) ...")
    canon_map = canonicalize_and_categorize(sorted(segments), log=log) if segments else {}
    log(">>> AI done; building links ...")
    prod_index = _product_index()
    cat_id_by_slug = {s: cid for s, _, cid in _allowed_categories()}
    from apps.fridge.aliases import product_ref_index  # MG_PRODALIAS

    ref_index = product_ref_index()

    links = 0
    for n, r in enumerate(todo, 1):
        links += rebuild_recipe_links(
            r,
            canon_map=canon_map,
            prod_index=prod_index,
            cat_id_by_slug=cat_id_by_slug,
            force=True,
            ref_index=ref_index,
            create_missing=True,  # MG_T04C
        )
        if n % 25 == 0 or n == len(todo):
            log("  rebuilt %d/%d recipes (links=%d)" % (n, len(todo), links))

    total = RecipeProduct.objects.count()
    matched = RecipeProduct.objects.filter(product__isnull=False).count()
    with_cat = RecipeProduct.objects.exclude(category_slug="").count()
    return {
        "recipes_processed": len(todo),
        "links_created": links,
        "links_total": total,
        "linked_to_product": matched,
        "with_category": with_cat,
    }
