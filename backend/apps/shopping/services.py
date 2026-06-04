# MG_SHOP001_services — list builders + AI/CSV importers
import csv
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from apps.fridge.models import FridgeItem
from apps.menu.models import Menu, MenuItem


def _to_decimal(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def build_items_from_menu(menu: Menu, family, subtract_fridge: bool):
    """Aggregate recipe ingredients across a menu.
    subtract_fridge=True → drop items already present in fridge (1.2)."""
    fridge_names = set()
    if subtract_fridge:
        fridge_names = {i.name.strip().lower() for i in FridgeItem.objects.filter(family=family, is_deleted=False)}

    aggregated = defaultdict(lambda: {"quantity": Decimal(0), "unit": "", "name": ""})
    for menu_item in MenuItem.objects.filter(menu=menu).select_related("recipe"):
        for ing in menu_item.recipe.ingredients or []:
            name = (ing.get("name") or "").strip()
            if not name:
                continue
            if subtract_fridge and name.lower() in fridge_names:
                continue
            key = name.lower()
            qty = _to_decimal(ing.get("quantity")) or Decimal(0)
            aggregated[key]["quantity"] += qty
            aggregated[key]["unit"] = ing.get("unit") or ""
            aggregated[key]["name"] = name

    return [
        {
            "name": v["name"],
            "quantity": (v["quantity"] or None) if v["quantity"] != 0 else None,
            "unit": v["unit"],
        }
        for v in aggregated.values()
    ]


def parse_csv(text: str):
    """CSV template: name,quantity,unit,category (header optional) (1.3)."""
    out = []
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return out
    start = 0
    header = [c.strip().lower() for c in rows[0]]
    if "name" in header:
        idx = {h: header.index(h) for h in ("name", "quantity", "unit", "category") if h in header}
        start = 1

        def cell(row, key):
            i = idx.get(key)
            if i is None or i >= len(row):
                return None
            return row[i]

        for row in rows[start:]:
            if not row:
                continue
            raw_name = cell(row, "name")
            name = (raw_name or "").strip()
            if not name:
                continue
            raw_qty = cell(row, "quantity")
            raw_unit = cell(row, "unit")
            raw_cat = cell(row, "category")
            out.append(
                {
                    "name": name,
                    "quantity": _to_decimal(raw_qty) if raw_qty is not None else None,
                    "unit": (raw_unit or "").strip(),
                    "category": (raw_cat or "").strip(),
                }
            )
    else:
        for row in rows:
            if not row or not row[0].strip():
                continue
            out.append(
                {
                    "name": row[0].strip(),
                    "quantity": _to_decimal(row[1]) if len(row) > 1 else None,
                    "unit": row[2].strip() if len(row) > 2 else "",
                    "category": row[3].strip() if len(row) > 3 else "",
                }
            )
    return out


def parse_text_with_ai(text: str):
    """Parse free-form shopping text into structured items via AI (1.3)."""
    from apps.common.ai_provider import AIRequestError, get_ai_client
    from apps.fridge.services import _parse_json_loose

    system = (
        "Ты парсер списка покупок. На вход — произвольный текст со списком продуктов. "
        "Верни строго JSON-массив объектов вида "
        '[{"name":"...","quantity":число_или_null,"unit":"...","category":""}]. '
        "Без пояснений, без markdown."
    )
    try:
        raw = get_ai_client().complete(prompt=text, system=system, max_tokens=1024, temperature=0.0)
    except AIRequestError:
        return None

    data = _parse_json_loose(raw)
    if not isinstance(data, list):
        return None

    out = []
    for d in data:
        if not isinstance(d, dict):
            continue
        name = (d.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "quantity": _to_decimal(d.get("quantity")),
                "unit": (d.get("unit") or "").strip(),
                "category": (d.get("category") or "").strip(),
            }
        )
    return out


# ── MG_RUBRIC002: product rubricator search + AI classify ───────────────────
def search_rubric(query: str, limit: int = 20):
    """Search the Product rubricator by name (icontains), ranked by popularity.
    Returns list of dicts {product_id, name, unit, category_slug, category_name,
    subcategory}. Empty query -> []."""
    from apps.fridge.models import Product

    q = (query or "").strip()
    if len(q) < 1:
        return []

    pop_rank = {"часто": 0, "средне": 1, "редко": 2, "": 3}
    qs = Product.objects.select_related("category_fk").filter(name__icontains=q)[:200]
    rows = []
    for p in qs:
        cat = p.category_fk
        rows.append(
            {
                "product_id": p.id,
                "name": p.name,
                "unit": p.default_unit or "",
                "category_slug": cat.slug if cat else "",
                "category_name": cat.name_ru if cat else "",
                "subcategory": getattr(p, "subcategory", "") or "",
                "_starts": 0 if p.name.lower().startswith(q.lower()) else 1,
                "_pop": pop_rank.get(getattr(p, "popularity", "") or "", 3),
            }
        )
    rows.sort(key=lambda r: (r["_starts"], r["_pop"], r["name"]))
    for r in rows:
        r.pop("_starts", None)
        r.pop("_pop", None)
    return rows[:limit]


def classify_new_product(name: str):
    """For a product NOT in the rubricator, ask AI for a category slug.
    Returns dict {category_slug, category_name} (slug may be 'other')."""
    from apps.fridge.models import ProductCategory
    from apps.fridge.services import gpt_pick_category_slug

    slug = gpt_pick_category_slug(name) or "other"
    cat = ProductCategory.objects.filter(slug=slug).first()
    if cat is None:
        cat = ProductCategory.objects.filter(slug="other").first()
    return {
        "category_slug": cat.slug if cat else "other",
        "category_name": cat.name_ru if cat else "Прочее",
    }


def ensure_product(name: str, category_slug: str = "", unit: str = ""):
    """Find a Product by name; if absent, create it under the given category
    (or AI-classified if slug missing). Returns the Product instance."""
    from apps.fridge.models import Product, ProductCategory
    from apps.fridge.services import gpt_pick_category_slug

    name = (name or "").strip()
    if not name:
        return None
    existing = Product.objects.filter(name__iexact=name).select_related("category_fk").first()
    if existing:
        return existing

    slug = (category_slug or "").strip().lower()
    if not slug:
        slug = gpt_pick_category_slug(name) or "other"
    cat = ProductCategory.objects.filter(slug=slug).first()
    if cat is None:
        cat = ProductCategory.objects.filter(slug="other").first()
    return Product.objects.create(
        name=name,
        category_fk=cat,
        category=cat.name_ru if cat else "",
        default_unit=unit or "",
        is_seed=False,
        nutrition={},
    )
