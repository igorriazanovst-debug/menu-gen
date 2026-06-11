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


# MG_RUBRICBROWSE: browse rubricator by category (same row shape as search_rubric)
def browse_rubric(category_slug: str = "", limit: int = 500):
    from apps.fridge.models import Product

    pop_rank = {"часто": 0, "средне": 1, "редко": 2, "": 3}
    qs = Product.objects.select_related("category_fk")
    slug = (category_slug or "").strip()
    if slug:
        qs = qs.filter(category_fk__slug=slug)
    rows = []
    for p in qs[:1000]:
        cat = p.category_fk
        rows.append(
            {
                "product_id": p.id,
                "name": p.name,
                "unit": p.default_unit or "",
                "category_slug": cat.slug if cat else "",
                "category_name": cat.name_ru if cat else "",
                "subcategory": getattr(p, "subcategory", "") or "",
                "_pop": pop_rank.get(getattr(p, "popularity", "") or "", 3),
            }
        )
    rows.sort(key=lambda r: (r["_pop"], r["name"]))
    for r in rows:
        r.pop("_pop", None)
    return rows[:limit]


def list_rubric_categories():
    from apps.fridge.models import ProductCategory

    return [
        {
            "slug": c.slug,
            "name_ru": c.name_ru,
            "icon": c.icon,
            "color": c.color,
            "sort_order": c.sort_order,
        }
        for c in ProductCategory.objects.filter(is_active=True).order_by("sort_order", "name_ru")
    ]


# ── MG_AICLEAN: AI normalization of menu-derived item names ─────────────────
_MG_MASS = None
_MG_VOL = None
_MG_CLOVE = None


def _mg_unit_tables():
    global _MG_MASS, _MG_VOL, _MG_CLOVE
    if _MG_MASS is None:
        from decimal import Decimal as _D
        _MG_MASS = {"г": _D(1), "кг": _D(1000)}
        _MG_VOL = {
            "мл": _D(1), "л": _D(1000),
            "ст.л.": _D(15), "ст. л.": _D(15),
            "ч.л.": _D(5), "ч. л.": _D(5),
            "стакан": _D(200),
        }
        _MG_CLOVE = {"зуб.", "зуб", "зубчик", "зубчика", "зубчиков", "зубец", "зубка"}
    return _MG_MASS, _MG_VOL, _MG_CLOVE


def _mg_norm_unit(u):
    u = (u or "").strip().lower()
    _, _, clove = _mg_unit_tables()
    return "шт" if u in clove else u


def _mg_merge_qty(contribs):
    """contribs: list of (Decimal|None qty, raw unit). Returns (unit, quantity)."""
    from decimal import Decimal
    mass, vol, _ = _mg_unit_tables()
    norm = [(q, _mg_norm_unit(u)) for (q, u) in contribs]
    numeric = [(q, u) for (q, u) in norm if q is not None]
    units_all = {u for (_, u) in norm}
    if not numeric:
        return (next(iter(units_all)) if len(units_all) == 1 else "", None)
    units_num = {u for (_, u) in numeric}
    if len(units_num) == 1:
        u = next(iter(units_num))
        return (u, sum((q for q, _ in numeric), Decimal(0)))
    dims = {}
    for q, u in numeric:
        if u in mass:
            dims["mass"] = dims.get("mass", Decimal(0)) + q * mass[u]
        elif u in vol:
            dims["vol"] = dims.get("vol", Decimal(0)) + q * vol[u]
        else:
            dims[u] = dims.get(u, Decimal(0)) + q
    dom = max(dims, key=lambda d: dims[d])
    total = dims[dom]
    if dom == "mass":
        return ("кг", (total / Decimal(1000))) if total >= 1000 else ("г", total)
    if dom == "vol":
        return ("л", (total / Decimal(1000))) if total >= 1000 else ("мл", total)
    return (dom, total)


_MG_SYS_CLEAN = (
    "Ты нормализатор названий продуктов для списка покупок. "
    "На вход JSON-массив {i, name}. Верни СТРОГО JSON-массив {i, name}.\n"
    "Правила для name:\n"
    "1) Именительный падеж, с заглавной буквы.\n"
    "2) Убери количество, числа, проценты, вес, бренд/магазин, скобки и "
    "примечания (по вкусу, для украшения, у меня...).\n"
    "3) СОХРАНИ различающий признак (вид/сорт/цвет/тип): красного лука->Лук "
    "красный; арахисовой пасты->Паста арахисовая; сыр фета->Сыр фета.\n"
    "4) Не схлопывай до общего слова, меняя смысл.\n"
    "5) Если строка не продукт (текст/комментарий/инструкция/лёд) -> name=null.\n"
    "Без markdown, без пояснений."
)

_MG_SYS_CLUSTER = (
    "Тебе дан JSON-массив названий продуктов (строки). Сведи варианты ОДНОГО "
    "продукта к единому каноническому названию. Верни СТРОГО JSON-массив "
    "{name, canon}, по одному объекту на каждое входное name.\n"
    "Правила canon:\n"
    "1) Единственное число, с заглавной буквы, единый порядок слов "
    "'Существительное признак'.\n"
    "2) УБЕРИ способ приготовления (варёное, отварной, жареное, запечённый, "
    "тушёный): 'Яйцо варёное'->'Яйцо'; 'Картофель отварной'->'Картофель'.\n"
    "3) СОХРАНИ форму/вид/сорт/цвет (замороженный, сушёный, консервированный, "
    "копчёный, кокосовое, фета, болгарский): 'Кокосовое молоко' и 'Молоко "
    "кокосовое' -> 'Молоко кокосовое'; 'Клубника замороженная' оставь.\n"
    "4) 'Яйца','Яйцо','Яйцо куриное' -> 'Яйцо'.\n"
    "Без markdown, без пояснений."
)


def ai_clean_item_names(items, chunk_size=20):
    """build_items_from_menu items -> AI-cleaned, variant-merged, deduped list.

    Pass 1: per-name canonicalization (drop non-product noise).
    Pass 2: cluster unique names to one canonical label (consistent merge).
    Then dedup by name; quantity summed (mixed units converted: mass->г/кг,
    volume->мл/л). Any AI failure falls back to raw names — never crash.
    """
    import json
    from collections import OrderedDict
    from decimal import Decimal

    if not items:
        return items

    names = [(it.get("name") or "") for it in items]

    try:
        from apps.common.ai_provider import get_ai_client
        client = get_ai_client()
    except Exception:
        client = None

    try:
        from apps.fridge.services import _parse_json_loose
    except Exception:
        _parse_json_loose = None

    # ---- pass 1: clean + drop ----
    clean = {}

    def _ask(indices):
        if client is None or _parse_json_loose is None:
            return
        for base in range(0, len(indices), chunk_size):
            grp = indices[base:base + chunk_size]
            payload = json.dumps([{"i": idx, "name": names[idx]} for idx in grp], ensure_ascii=False)
            try:
                raw = client.complete(prompt=payload, system=_MG_SYS_CLEAN, max_tokens=2000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception:
                data = None
            if isinstance(data, list):
                for d in data:
                    if isinstance(d, dict) and "i" in d:
                        try:
                            idx = int(d["i"])
                        except (TypeError, ValueError):
                            continue
                        nm = d.get("name")
                        clean[idx] = nm.strip() if isinstance(nm, str) and nm.strip() else None

    if client is not None:
        all_idx = list(range(len(names)))
        _ask(all_idx)
        missing = [i for i in all_idx if i not in clean]
        if missing:
            _ask(missing)

    stage = []  # (item, name) survivors
    for i, it in enumerate(items):
        if i in clean:
            nm = clean[i]
            if nm is None:
                continue
        else:
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
        stage.append((it, nm))

    # ---- pass 2: canonical clustering over sorted unique names ----
    canon = {}
    if client is not None and _parse_json_loose is not None:
        uniq = sorted({nm for _, nm in stage}, key=lambda s: s.lower())
        for base in range(0, len(uniq), 80):
            grp = uniq[base:base + 80]
            try:
                raw = client.complete(prompt=json.dumps(grp, ensure_ascii=False),
                                      system=_MG_SYS_CLUSTER, max_tokens=3000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception:
                data = None
            if isinstance(data, list):
                for d in data:
                    if isinstance(d, dict) and d.get("name") and isinstance(d.get("canon"), str) and d["canon"].strip():
                        canon[d["name"]] = d["canon"].strip()

    cleaned = [{**it, "name": canon.get(nm, nm)} for (it, nm) in stage]

    # ---- dedup by name; quantity merge with unit conversion ----
    agg = OrderedDict()
    for it in cleaned:
        key = it["name"].lower()
        slot = agg.get(key)
        if slot is None:
            slot = {"name": it["name"], "contribs": []}
            agg[key] = slot
        q = it.get("quantity")
        qd = None
        if q is not None:
            try:
                qd = q if isinstance(q, Decimal) else Decimal(str(q))
            except Exception:
                qd = None
        slot["contribs"].append((qd, it.get("unit") or ""))

    out = []
    for slot in agg.values():
        unit, quantity = _mg_merge_qty(slot["contribs"])
        if quantity is not None:
            try:
                quantity = quantity.quantize(Decimal("0.01"))
            except Exception:
                pass
        out.append({"name": slot["name"], "unit": unit, "quantity": quantity, "category": ""})
    return out
