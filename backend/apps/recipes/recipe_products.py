# MG_RECIPELINK — resolve recipe ingredients to rubricator products + categories.
import re
from decimal import Decimal, InvalidOperation


def _norm(s):
    s = (s or "").strip().lower().replace("\u0451", "\u0435")  # ё -> е
    s = re.sub(r"\s+", " ", s)
    return s


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
    for p in Product.objects.select_related("category_fk").only(
        "id", "name", "category_fk__slug", "category_fk__id"
    ):
        n = _norm(p.name)
        if n and n not in idx:
            cat = p.category_fk
            idx[n] = (p.id, cat.slug if cat else "", cat.id if cat else None)
    return idx


_SYS_CANON_CAT = (
    "Тебе дан JSON-массив объектов {i, name} — названия ингредиентов из рецептов "
    "(часто в родительном падеже, с количеством/примечаниями). Для каждого верни "
    "СТРОГО JSON-массив объектов {i, canon, slug}. Без markdown, без пояснений.\n"
    "canon: каноническое название продукта — именительный падеж, единственное "
    "число, с заглавной буквы, порядок 'Существительное признак'. Убери "
    "количество, проценты, бренд, скобки, примечания и способ приготовления "
    "(варёное, жареное, отварной). СОХРАНИ вид/сорт/цвет/форму (кокосовое, "
    "замороженный, болгарский, фета). Если это не продукт (мусор парсера, "
    "абзац текста, реклама) — canon=null.\n"
    "slug: ОДНА категория строго из списка ниже (или 'other'). Список: __LISTING__."
)


def canonicalize_and_categorize(raw_names, chunk_size=30):
    """raw_name -> (canon|None, slug). One AI pass (chunked) + one retry.
    canon=None means noise (drop). Never raises."""
    import json

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
    system = _SYS_CANON_CAT.replace("__LISTING__", listing)

    def _ask(indices):
        if client is None or _parse_json_loose is None:
            return
        for base in range(0, len(indices), chunk_size):
            grp = indices[base:base + chunk_size]
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
                if isinstance(canon, str):
                    canon = canon.strip()
                slug = str(d.get("slug") or "").strip().lower()
                if slug not in valid_slugs:
                    slug = ""
                out[names[j]] = (canon if canon else None, slug)

    all_idx = list(range(len(names)))
    _ask(all_idx)
    missing = [j for j in all_idx if names[j] not in out]
    if missing:
        _ask(missing)
    # fallback for AI failures (NOT explicit null): keep raw name, no category
    for j in all_idx:
        if names[j] not in out:
            out[names[j]] = (names[j], "")
    return out


def rebuild_recipe_links(recipe, canon_map=None, prod_index=None, cat_id_by_slug=None, force=False):
    """(Re)build RecipeProduct rows for one recipe. Idempotent (replace).
    Returns number of links created."""
    from .models import RecipeProduct

    ings = recipe.ingredients or []
    if not isinstance(ings, list):
        return 0

    existing = RecipeProduct.objects.filter(recipe=recipe)
    if existing.exists() and not force:
        return 0

    raw_names = []
    for ing in ings:
        if isinstance(ing, dict):
            nm = (ing.get("name") or "").strip()
            if nm:
                raw_names.append(nm)

    if canon_map is None:
        canon_map = canonicalize_and_categorize(raw_names)
    if prod_index is None:
        prod_index = _product_index()
    if cat_id_by_slug is None:
        cat_id_by_slug = {s: cid for s, _, cid in _allowed_categories()}

    rows = []
    seen = set()
    for ing in ings:
        if not isinstance(ing, dict):
            continue
        nm = (ing.get("name") or "").strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        canon, ai_slug = canon_map.get(nm, (nm, ""))
        if not canon:
            continue  # noise -> no link
        match = prod_index.get(_norm(canon))
        if match:
            product_id, slug, cat_id = match
        else:
            product_id, slug, cat_id = None, ai_slug, cat_id_by_slug.get(ai_slug)
        grams = ing.get("grams")
        try:
            grams = float(grams) if grams is not None else None
        except (TypeError, ValueError):
            grams = None
        rows.append(
            RecipeProduct(
                recipe=recipe,
                product_id=product_id,
                name_raw=nm[:255],
                name_canonical=(canon or "")[:255],
                category_slug=(slug or "")[:64],
                category_fk_id=cat_id,
                quantity=str(ing.get("quantity") or "")[:64],
                unit=(ing.get("unit") or "")[:50],
                grams=grams,
            )
        )

    existing.delete()
    if rows:
        RecipeProduct.objects.bulk_create(rows)
    return len(rows)


def backfill(force=False, recipe_ids=None, menu_id=None, limit=None, log=print):
    """Backfill links across recipes. Collects all distinct names, runs one AI
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

    raw_names = set()
    todo = []
    for r in recipes:
        if RecipeProduct.objects.filter(recipe=r).exists() and not force:
            continue
        todo.append(r)
        for ing in (r.ingredients or []):
            if isinstance(ing, dict):
                nm = (ing.get("name") or "").strip()
                if nm:
                    raw_names.add(nm)

    log("recipes_total=%d todo=%d distinct_names=%d" % (len(recipes), len(todo), len(raw_names)))
    canon_map = canonicalize_and_categorize(sorted(raw_names)) if raw_names else {}
    prod_index = _product_index()
    cat_id_by_slug = {s: cid for s, _, cid in _allowed_categories()}

    links = 0
    for r in todo:
        links += rebuild_recipe_links(
            r, canon_map=canon_map, prod_index=prod_index, cat_id_by_slug=cat_id_by_slug, force=True
        )

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
