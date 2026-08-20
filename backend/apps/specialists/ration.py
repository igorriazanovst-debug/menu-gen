"""MG_DIETITIAN: разбор рациона и проверка на исключения.

Нутрициологу нужен не калораж (это тренерская оптика), а состав: чего в тарелке
много, чего нет вовсе и не попадает ли туда исключённое. Всё считается по уже
проставленным полям рецепта — `food_group`, `protein_type`, `is_fatty_fish`,
`is_red_meat`, `allergens`, — на которые ссылается запись дневника.

Две честные оговорки заложены в сам ответ:

* записи «своей едой» (без рецепта) состава не имеют, и их доля возвращается
  отдельно: «овощей 12%» при половине записей вручную — это не факт, а иллюзия;
* клетчатка есть не у всех рецептов, поэтому рядом с ней идёт покрытие —
  по какой доле записей её вообще удалось посчитать.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta

from django.utils import timezone


def _pct(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def ration_analysis(member, days: int = 14, today=None) -> dict:
    """Состав съеденного за период по группам продуктов и источникам белка."""
    from apps.diary.models import DiaryEntry

    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)

    eaten = list(
        DiaryEntry.objects.filter(member=member, date__gte=start, date__lte=today, is_eaten=True).select_related(
            "recipe"
        )
    )
    with_recipe = [e for e in eaten if e.recipe_id]
    total = len(eaten)

    groups = Counter()
    protein_types = Counter()
    fatty_fish_days = set()
    red_meat_days = set()
    for entry in with_recipe:
        recipe = entry.recipe
        groups[recipe.food_group or "unknown"] += 1
        if recipe.protein_type:
            protein_types[recipe.protein_type] += 1
        if recipe.is_fatty_fish:
            fatty_fish_days.add(entry.date)
        if recipe.is_red_meat:
            red_meat_days.add(entry.date)

    titles = Counter(e.recipe.title for e in with_recipe)

    return {
        "member_id": member.id,
        "member_name": getattr(getattr(member, "user", None), "name", "") or "",
        "days": days,
        "entries_total": total,
        # Доля записей, по которым состав вообще известен. Чем она ниже, тем
        # меньше веса у всего остального в этом ответе.
        "coverage": {
            "with_recipe": len(with_recipe),
            "manual": total - len(with_recipe),
            "percent": _pct(len(with_recipe), total),
        },
        "food_groups": [
            {"group": g, "count": n, "percent": _pct(n, len(with_recipe))} for g, n in groups.most_common()
        ],
        "protein_sources": [
            {"type": t, "count": n, "percent": _pct(n, sum(protein_types.values()))}
            for t, n in protein_types.most_common()
        ],
        "fatty_fish_days": len(fatty_fish_days),
        "red_meat_days": len(red_meat_days),
        "variety": {
            "distinct_dishes": len(titles),
            "top_repeats": [{"title": t, "count": n} for t, n in titles.most_common(5) if n > 1],
        },
        "fiber": _fiber_block(with_recipe),
    }


def _fiber_block(entries) -> dict:
    """Клетчатка за период и покрытие: по скольким записям её удалось найти.

    Без покрытия число вводит в заблуждение: у половины рецептов клетчатки в
    данных нет, и сумма выйдет заниженной, а выглядеть будет как факт.
    """
    total_g = 0.0
    counted = 0
    for entry in entries:
        raw = (entry.recipe.nutrition or {}).get("fiber")
        if isinstance(raw, dict):
            raw = raw.get("value")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        try:
            qty = float(entry.quantity or 1)
        except (TypeError, ValueError):
            qty = 1.0
        total_g += value * qty
        counted += 1
    return {
        "total_g": round(total_g, 1),
        "entries_counted": counted,
        "coverage_percent": _pct(counted, len(entries)),
    }


def excluded_hits(member, days: int = 14, today=None) -> dict:
    """Где в дневнике и в активных меню встречается исключённое.

    Генератор учитывает аллергии и нелюбимое, но он не единственный путь еды в
    тарелку: ручная замена блюда, своя запись, меню, собранное до того, как
    аллерген добавили в профиль. Здесь сверяются факты, а не намерения.
    """
    from apps.common.allergens import label_for, resolve_allergy
    from apps.diary.models import DiaryEntry
    from apps.menu.models import Menu, MenuItem

    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)

    user = getattr(member, "user", None)
    raw_allergies = list(getattr(user, "allergies", None) or [])
    disliked = [str(d).strip().lower() for d in (getattr(user, "disliked_products", None) or []) if str(d).strip()]

    keys, custom = set(), []
    for value in raw_allergies:
        key = resolve_allergy(value)
        if key:
            keys.add(key)
        elif str(value).strip():
            custom.append(str(value).strip().lower())

    diary_hits = []
    for entry in DiaryEntry.objects.filter(
        member=member, date__gte=start, date__lte=today, is_eaten=True
    ).select_related("recipe"):
        title = entry.recipe.title if entry.recipe_id else entry.custom_name
        found = _match(entry.recipe, title, keys, custom, disliked)
        if found:
            diary_hits.append({"date": str(entry.date), "title": title, "reasons": found})

    menu_hits = []
    family_id = getattr(getattr(member, "family", None), "id", None)
    menus = Menu.objects.filter(family_id=family_id, status=Menu.Status.ACTIVE, end_date__gte=today)
    for item in MenuItem.objects.filter(menu__in=menus).select_related("recipe", "menu"):
        if not item.recipe_id:
            continue
        found = _match(item.recipe, item.recipe.title, keys, custom, disliked)
        if found:
            menu_hits.append(
                {
                    "menu_id": item.menu_id,
                    "day_offset": item.day_offset,
                    "title": item.recipe.title,
                    "reasons": found,
                }
            )

    return {
        "member_id": member.id,
        "member_name": getattr(user, "name", "") or "",
        "watching": {
            "allergens": sorted(label_for(k) for k in keys),
            "custom": custom,
            "disliked": disliked,
        },
        "diary": diary_hits,
        "menu": menu_hits,
    }


def _title_stems(title: str) -> list[str]:
    """Основы слов названия — по ним ищем нелюбимое и свои аллергены.

    Сравнение подстрок здесь не работает: в профиле записано «кинза», а в
    названии стоит «кинзой», и совпадения нет. Стеммер тот же, что у поиска
    по рецептам.
    """
    from apps.common.morphology import stem_prefix

    words = re.findall(r"[а-яa-z0-9]+", (title or "").lower().replace("ё", "е"))
    return [stem_prefix(w) for w in words]


def _mentions(stems: list[str], phrase: str) -> bool:
    """Упомянута ли фраза (возможно из нескольких слов) в названии."""
    from apps.common.morphology import stem_prefix

    parts = [stem_prefix(w) for w in re.findall(r"[а-яa-z0-9]+", (phrase or "").lower().replace("ё", "е"))]
    if not parts:
        return False
    return all(any(s.startswith(part) or part.startswith(s) for s in stems) for part in parts)


def _match(recipe, title, keys, custom, disliked) -> list[str]:
    """Причины, по которым блюдо не должно было попасть в тарелку."""
    from apps.common.allergens import label_for

    reasons = []
    if recipe is not None:
        for key in set(recipe.allergens or []) & keys:
            reasons.append(f"аллерген: {label_for(key)}")
    stems = _title_stems(title)
    for word in custom:
        if _mentions(stems, word):
            reasons.append(f"аллерген (свой): {word}")
    for word in disliked:
        if _mentions(stems, word):
            reasons.append(f"нелюбимое: {word}")
    return reasons


def family_ration(family, days: int = 14, today=None) -> list[dict]:
    from apps.family.models import FamilyMember

    members = FamilyMember.objects.filter(family=family).select_related("user")
    return [ration_analysis(m, days=days, today=today) for m in members]


def family_excluded(family, days: int = 14, today=None) -> list[dict]:
    from apps.family.models import FamilyMember

    members = FamilyMember.objects.filter(family=family).select_related("user")
    return [excluded_hits(m, days=days, today=today) for m in members]
