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
        fridge_names = {
            i.name.strip().lower()
            for i in FridgeItem.objects.filter(family=family, is_deleted=False)
        }

    aggregated = defaultdict(lambda: {"quantity": Decimal(0), "unit": "", "name": ""})
    for menu_item in MenuItem.objects.filter(menu=menu).select_related("recipe"):
        for ing in (menu_item.recipe.ingredients or []):
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
        for row in rows[start:]:
            if not row:
                continue
            name = row[idx["name"]].strip() if "name" in idx and idx["name"] < len(row) else ""
            if not name:
                continue
            out.append({
                "name": name,
                "quantity": _to_decimal(row[idx["quantity"]]) if "quantity" in idx and idx["quantity"] < len(row) else None,
                "unit": row[idx["unit"]].strip() if "unit" in idx and idx["unit"] < len(row) else "",
                "category": row[idx["category"]].strip() if "category" in idx and idx["category"] < len(row) else "",
            })
    else:
        for row in rows:
            if not row or not row[0].strip():
                continue
            out.append({
                "name": row[0].strip(),
                "quantity": _to_decimal(row[1]) if len(row) > 1 else None,
                "unit": row[2].strip() if len(row) > 2 else "",
                "category": row[3].strip() if len(row) > 3 else "",
            })
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
        raw = get_ai_client().complete(
            prompt=text, system=system, max_tokens=1024, temperature=0.0
        )
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
        out.append({
            "name": name,
            "quantity": _to_decimal(d.get("quantity")),
            "unit": (d.get("unit") or "").strip(),
            "category": (d.get("category") or "").strip(),
        })
    return out
