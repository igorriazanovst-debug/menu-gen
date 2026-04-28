"""
Классификатор флагов is_red_meat / is_fatty_fish.

Эвристика — поиск по ингредиентам (имеет приоритет), затем по title.
Флаги проставляются ТОЛЬКО для food_group='protein' (метод тарелки).
"""
from __future__ import annotations
import re
from django.core.management.base import BaseCommand
from apps.recipes.models import Recipe


# ── словари ─────────────────────────────────────────────────────────────────

RED_MEAT_KEYWORDS = (
    # русский
    "говядин", "телятин", "телёнок", "телятник",
    "свинин", "баранин", "ягнятин", "ягнёнок",
    "конин", "оленин", "кабан", "лосятин",
    "ребр",  # рёбрышки
    "стейк",
    "вырезк",  # вырезка (обычно говяжья/свиная)
    "филе мраморн", "мраморн",
    "ростбиф", "бефстроганов", "бифштекс",
    # английский
    "beef", "veal", "pork", "lamb", "mutton",
    "venison", "bison",
)

# исключения из red_meat — фразы, которые НЕ red_meat (даже если совпало по ключу)
RED_MEAT_EXCLUDE = (
    "куриная вырезка", "вырезка из курицы", "вырезка курицы",
    "вырезка индейки", "индейки вырезк",
    "филе курицы", "куриное филе",
    "филе индейки",
)

FATTY_FISH_KEYWORDS = (
    # русский
    "лосос", "сёмг", "семг", "форел", "тунец", "тунц",
    "скумбри", "сельд", "сельдь", "иваси",
    "сард", "сардин",
    "горбуш", "кет",  # кета
    "нерк", "чавыч", "кижуч",
    "палтус",
    "угорь", "угря", "угря",
    "анчоус",
    # английский
    "salmon", "tuna", "mackerel", "herring", "sardine",
    "trout", "halibut", "anchovy", "eel",
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _norm(s) -> str:
    return (s or "").lower().strip()


def _matches_any(text: str, keywords: tuple) -> bool:
    return any(kw in text for kw in keywords)


def _is_red_meat_text(text: str) -> bool:
    if not text:
        return False
    if any(ex in text for ex in RED_MEAT_EXCLUDE):
        return False
    return _matches_any(text, RED_MEAT_KEYWORDS)


def _is_fatty_fish_text(text: str) -> bool:
    if not text:
        return False
    return _matches_any(text, FATTY_FISH_KEYWORDS)


def _classify(recipe: Recipe):
    """Возвращает (is_red_meat: bool, is_fatty_fish: bool)."""
    # собираем все имена ингредиентов в одну строку
    ing_names = []
    for ing in (recipe.ingredients or []):
        if isinstance(ing, dict):
            ing_names.append(_norm(ing.get("name")))
    ing_text = " ".join(ing_names)

    title = _norm(recipe.title)
    cats  = " ".join(_norm(c) for c in (recipe.categories or []))

    haystack = " ".join((ing_text, title, cats))

    return (
        _is_red_meat_text(haystack),
        _is_fatty_fish_text(haystack),
    )


# ── command ─────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Классифицирует рецепты по флагам is_red_meat / is_fatty_fish"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="только показать план")
        parser.add_argument("--reset",   action="store_true", help="сбросить флаги перед классификацией")
        parser.add_argument("--only-protein", action="store_true",
                            help="ограничиться food_group=protein (по умолчанию — все)")

    def handle(self, *args, **opts):
        dry      = opts["dry_run"]
        reset    = opts["reset"]
        only_pro = opts["only_protein"]

        qs = Recipe.objects.all()
        if only_pro:
            qs = qs.filter(food_group="protein")

        total = qs.count()
        self.stdout.write(f"Рецептов к обработке: {total}")

        if reset and not dry:
            updated = qs.update(is_red_meat=False, is_fatty_fish=False)
            self.stdout.write(f"Сброшено флагов у {updated} рецептов")

        red_count = fish_count = changed = 0
        to_update = []

        for r in qs.iterator(chunk_size=500):
            new_red, new_fish = _classify(r)
            old_red, old_fish = bool(r.is_red_meat), bool(r.is_fatty_fish)
            if new_red != old_red or new_fish != old_fish:
                changed += 1
                if dry and changed <= 30:
                    self.stdout.write(
                        f"  [{r.id}] {r.title[:60]:60} "
                        f"red:{old_red}->{new_red}  fish:{old_fish}->{new_fish}"
                    )
                if not dry:
                    r.is_red_meat   = new_red
                    r.is_fatty_fish = new_fish
                    to_update.append(r)
            if new_red:  red_count  += 1
            if new_fish: fish_count += 1

            if not dry and len(to_update) >= 500:
                Recipe.objects.bulk_update(to_update, ["is_red_meat", "is_fatty_fish"])
                to_update = []

        if not dry and to_update:
            Recipe.objects.bulk_update(to_update, ["is_red_meat", "is_fatty_fish"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Итого: red_meat={red_count}  fatty_fish={fish_count}  changed={changed}  dry={dry}"
        ))
