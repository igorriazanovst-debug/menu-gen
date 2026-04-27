"""
Автоклассификация существующих рецептов.

Запуск:
  docker compose exec backend python manage.py shell -c "exec(open('/app/scripts/classify_recipes.py').read())"

Проходит по всем Recipe и проставляет:
  - food_group     по словарю ключевых слов в title + ingredients
  - protein_type   animal / plant / mixed
  - grain_type     whole / refined
  - is_fatty_fish  лосось/скумбрия/сельдь/семга/форель
  - is_red_meat    говядина/баранина/свинина/утка
  - suitable_for   по эвристикам (время готовки, ключевые слова)

Поля, уже заполненные пользователем (не пустые), НЕ перезаписываются.
Передай FORCE=True в начало скрипта, чтобы перезаписывать всё.
"""
from __future__ import annotations
import re
from typing import Iterable

from apps.recipes.models import Recipe


FORCE = False  # True = перезаписывать уже заполненные поля


# ─── словари ключевых слов ──────────────────────────────────────────────────

ANIMAL_PROTEIN = {
    # мясо
    "говядин", "телятин", "свинин", "баранин", "ягнят", "оленин",
    "курин", "куриц", "куриная", "куриное", "кур ", "цыплён", "цыплят",
    "индейк", "утк", "гус", "перепел", "крольчат", "кролик",
    "фарш", "котлет",
    # рыба и морепродукты
    "рыб", "лосос", "сёмг", "семг", "форел", "скумбри", "сельд", "селёдк", "тунец",
    "треск", "хек", "минта", "судак", "щук", "карп", "окун", "сом",
    "креветк", "кальмар", "мидии", "мид", "осьминог", "краб",
    # яйца, молочка-белок
    "яйц", "яичн", "омлет",
    "творог", "сыр", "брынз", "феты", "греческий йогурт", "греч. йогурт",
}

PLANT_PROTEIN = {
    "фасол", "горох", "нут", "чечевиц", "маш", "соя", "соев", "тофу",
    "темпе", "сейтан",
    "арахис", "миндал", "грецк", "кешью", "фундук", "фисташ", "пекан",
    "тыквенн семечк", "семечк",
}

FATTY_FISH = {
    "лосос", "сёмг", "семг", "скумбри", "сельд", "селёдк", "форел",
    "тунец", "сардин", "макрель",
}

RED_MEAT = {
    "говядин", "телятин", "свинин", "баранин", "ягнят", "оленин",
    "утк", "гус",
}

VEGETABLES = {
    "огурц", "помидор", "томат", "капуст", "брокколи", "цветная капуст",
    "морков", "свёкл", "свекл", "лук", "чеснок", "сельдер", "редис",
    "перец", "болгарск перец", "паприк", "баклажан", "кабачк", "цуккини",
    "тыкв", "шпинат", "руккол", "салат лист", "латук", "айсберг",
    "зелень", "укроп", "петрушк", "базилик", "кинз", "мят",
    "грибы", "шампиньон", "вешенк", "лисичк", "белый гриб",
    "спарж", "артишок",
}

FRUITS = {
    "яблок", "груш", "банан", "апельсин", "мандарин", "лимон", "лайм",
    "персик", "нектарин", "абрикос", "сливы", "слив", "вишн", "черешн",
    "ягод", "клубник", "землянич", "малин", "ежевик", "черник", "голубик",
    "смородин", "крыжовник", "виноград", "арбуз", "дын", "ананас",
    "манго", "киви", "хурм", "гранат", "инжир", "финик",
}

DAIRY = {
    "молок", "сметан", "кефир", "ряженк", "айран", "сливки", "сливок",
    "масло сливочн", "сливочн масл", "сыр ", "сырн", "творог",
    "йогурт", "ряжен",
}

OILS = {
    "масло растит", "растит масл", "масло оливков", "оливков масл",
    "подсолнечн масл", "масло подсолн", "льнян масл", "масло льнян",
    "кокосов масл", "масло кокос", "топлёное масл", "масло топлён",
    "ги ", "сало", "смалец",
}

# зерновые / крупы
WHOLE_GRAINS = {
    "гречк", "греч кр", "греч.", "греч ",
    "булгур", "кинв", "киноа", "кускус", "перловк", "перлов кр",
    "ячмень", "ячневая", "овсян", "овсянка", "овсяные хлопья",
    "пшениц цельнозернов", "цельнозерн", "цельная пшениц",
    "коричнев рис", "бурый рис", "дикий рис", "красный рис",
    "ржаная мук", "ржан мук", "обойн мук", "обойная мук",
    "цельнозерн мук", "цельнозернов мук",
}

REFINED_GRAINS = {
    "рис ", "белый рис", "круглозерн рис", "длиннозерн рис",
    "манн крупа", "манная крупа", "манн", "манка",
    "макарон", "паст", "спагетт", "лапш", "вермишель",
    "мука высш", "пшеничн мук", "белая мук", "хлеб ", "хлебцы",
    "багет", "батон", "булочк", "лаваш",
    "крахмал",
}

GRAINS_GENERAL = WHOLE_GRAINS | REFINED_GRAINS

# ─── helpers ────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return (s or "").lower()

def _haystack(recipe: Recipe) -> str:
    parts: list[str] = [_norm(recipe.title or "")]
    ings = recipe.ingredients or []
    if isinstance(ings, list):
        for it in ings:
            if isinstance(it, dict):
                parts.append(_norm(it.get("name", "")))
            elif isinstance(it, str):
                parts.append(_norm(it))
    return " | ".join(parts)

def _has_any(text: str, words: Iterable[str]) -> bool:
    return any(w in text for w in words)

def _has_word(text: str, words: Iterable[str]) -> bool:
    """То же, но слова с пробелами проверяются как подстроки."""
    return any(w in text for w in words)


# ─── основная классификация ────────────────────────────────────────────────

def classify(recipe: Recipe) -> dict:
    """Возвращает словарь полей для update без сохранения."""
    text = _haystack(recipe)
    out: dict = {}

    has_animal  = _has_any(text, ANIMAL_PROTEIN)
    has_plant   = _has_any(text, PLANT_PROTEIN)
    has_veg     = _has_any(text, VEGETABLES)
    has_fruit   = _has_any(text, FRUITS)
    has_dairy   = _has_any(text, DAIRY)
    has_oil     = _has_any(text, OILS)
    has_whole   = _has_any(text, WHOLE_GRAINS)
    has_refined = _has_any(text, REFINED_GRAINS)
    has_grain   = has_whole or has_refined or _has_any(text, GRAINS_GENERAL)

    # food_group — по доминанте. Приоритет:
    #   protein > grain > vegetable > fruit > dairy > oil > other
    if has_animal or has_plant:
        out["food_group"] = "protein"
    elif has_grain:
        out["food_group"] = "grain"
    elif has_veg:
        out["food_group"] = "vegetable"
    elif has_fruit:
        out["food_group"] = "fruit"
    elif has_dairy:
        out["food_group"] = "dairy"
    elif has_oil:
        out["food_group"] = "oil"
    else:
        out["food_group"] = "other"

    # protein_type
    if out["food_group"] == "protein":
        if has_animal and has_plant:
            out["protein_type"] = "mixed"
        elif has_animal:
            out["protein_type"] = "animal"
        elif has_plant:
            out["protein_type"] = "plant"

    # grain_type
    if out["food_group"] == "grain":
        if has_whole and not has_refined:
            out["grain_type"] = "whole"
        elif has_refined and not has_whole:
            out["grain_type"] = "refined"
        elif has_whole and has_refined:
            out["grain_type"] = "whole"  # цельнозерновые приоритетнее
        else:
            out["grain_type"] = "refined"

    # флаги
    out["is_fatty_fish"] = _has_any(text, FATTY_FISH)
    out["is_red_meat"]   = _has_any(text, RED_MEAT)

    # suitable_for — эвристика по категориям и meal_type
    suitable: list[str] = []
    cats = " ".join((recipe.categories or [])).lower() if isinstance(recipe.categories, list) else ""
    title_low = (recipe.title or "").lower()

    if (
        "завтрак" in cats or "завтрак" in title_low
        or _has_any(title_low, {"каш", "омлет", "сырник", "блины", "блин", "оладь", "гранола", "мюсли", "тост"})
    ):
        suitable.append("breakfast")

    if "обед" in cats or "обед" in title_low or _has_any(title_low, {"суп", "борщ", "щи", "солянк", "уха"}):
        suitable.append("lunch")

    if "ужин" in cats or "ужин" in title_low:
        suitable.append("dinner")

    if (
        "перекус" in cats or "снек" in cats or "снэк" in cats
        or _has_any(title_low, {"печенье", "батончик", "смузи", "коктейль", "перекус"})
    ):
        suitable.append("snack")

    # если food_group=protein и нет завтрака — кладём lunch+dinner по умолчанию
    if not suitable:
        if out["food_group"] in {"protein", "grain", "vegetable"}:
            suitable = ["lunch", "dinner"]
        elif out["food_group"] == "fruit":
            suitable = ["breakfast", "snack"]
        elif out["food_group"] == "dairy":
            suitable = ["breakfast", "snack"]

    out["suitable_for"] = suitable

    return out


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def run(force: bool = FORCE):
    qs = Recipe.objects.all()
    total = qs.count()
    print(f"Найдено рецептов: {total}")

    stats = {
        "updated": 0,
        "by_food_group": {},
        "fatty_fish": 0,
        "red_meat": 0,
        "no_change": 0,
    }

    for r in qs.iterator():
        new_vals = classify(r)
        changed_fields = []

        for field, new_val in new_vals.items():
            current = getattr(r, field, None)
            if force or _is_empty(current):
                if current != new_val:
                    setattr(r, field, new_val)
                    changed_fields.append(field)

        if changed_fields:
            r.save(update_fields=changed_fields)
            stats["updated"] += 1
            fg = new_vals.get("food_group", "other")
            stats["by_food_group"][fg] = stats["by_food_group"].get(fg, 0) + 1
            if new_vals.get("is_fatty_fish"):
                stats["fatty_fish"] += 1
            if new_vals.get("is_red_meat"):
                stats["red_meat"] += 1
        else:
            stats["no_change"] += 1

    print()
    print("─" * 50)
    print(f"Обновлено рецептов:    {stats['updated']}")
    print(f"Без изменений:         {stats['no_change']}")
    print(f"Жирная рыба:           {stats['fatty_fish']}")
    print(f"Красное мясо:          {stats['red_meat']}")
    print()
    print("Распределение по food_group:")
    for fg, n in sorted(stats["by_food_group"].items(), key=lambda x: -x[1]):
        print(f"  {fg:12s} {n}")
    print("─" * 50)


if __name__ == "__main__":
    run()
else:
    # при exec(open(...).read()) запустится сразу
    run()
