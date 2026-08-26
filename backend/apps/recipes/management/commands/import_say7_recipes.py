"""MG_SAY7: импорт выгрузки рецептов say7 с классификацией.

В источнике есть только состав, шаги, КБЖУ на 100 г и категория сайта — из
одиннадцати рубрик вроде «Вторые блюда» и «Разное». Всего, чем живёт генератор
меню (тип блюда, вес порции, приёмы пищи, диет-флаги, способ приготовления),
там нет. Поэтому импорт не перекладывает поля, а классифицирует.

Что выводится здесь, при разборе строки:

  dish_type          из рубрики сайта, для смешанных — по названию
                     («Десерты, напитки» → dessert, но «Глинтвейн» → drink)
  portion_g          вес готового блюда ÷ порции — без него рецепт не попадёт
                     ни в коридор калорий, ни в «Тарелку»
  КБЖУ на порцию     из КБЖУ на 100 г и веса порции
  suitable_for       из типа блюда
  cook_time_min      из текста шагов («варить 15 минут»)
  cooking_method     по глаголам в шагах
  диет-флаги         по составу
  oil_tsp            по граммам масла в составе

Что оставлено готовым классификаторам (они уже написаны и знают правила):

  food_group         classify_food_group
  allergens          mg_classify_allergens
  is_red_meat/fish   classify_meat_fish
  plate_component    mg_seed_plate

Всё импортируется НЕОПУБЛИКОВАННЫМ: у рецептов нет фотографий, а карточка без
фото в выдаче выглядит поломкой. Публиковать — отдельным решением, руками.

Запуск:
    python manage.py import_say7_recipes --dry-run
    python manage.py import_say7_recipes
    python manage.py import_say7_recipes --limit 50
"""

from __future__ import annotations

import gzip
import json
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.models import Recipe

# .../recipes/management/commands/файл → parents[2] это сам recipes
REFERENCE_DIR = Path(__file__).resolve().parents[2] / "reference"
DEFAULT_FILE = REFERENCE_DIR / "say7_recipes.jsonl.gz"

LEGACY_PREFIX = "say7:"

# ── тип блюда ───────────────────────────────────────────────────────────────
# Рубрики сайта → наши типы. Две рубрики смешанные, их доуточняем по названию.
CATEGORY_TO_DISH = {
    "Вторые блюда": "main",
    "Рыба и морепродукты": "main",
    "Первые блюда": "soup",
    "Салаты": "salad",
    "Выпечка": "bakery",
    "Несладкая выпечка": "bakery",
    "Торты и пирожные": "dessert",
    "Десерты, напитки": "dessert",
    "Блины, оладьи, сырники": "breakfast_dish",
    "Закуски и бутерброды": "snack",
    "Разное": "sauce",
}

# «Десерты, напитки» — одна рубрика на две наши. Отличаем по названию.
DRINK_WORDS = (
    "глинтвейн",
    "компот",
    "морс",
    "коктейль",
    "напиток",
    "лимонад",
    "смузи",
    "кисель",
    "квас",
    "какао",
    "пунш",
    "сангрия",
    "чай ",
    "кофе ",
)
# «Разное» — почти сплошь соусы и кремы, но не всё.
NOT_SAUCE_WORDS = ("лапша", "тесто", "украшение", "хлеб")


def dish_type_for(category: str, name: str) -> str:
    base = CATEGORY_TO_DISH.get((category or "").strip(), "main")
    low = (name or "").lower()
    if base == "dessert" and any(w in low for w in DRINK_WORDS):
        return "drink"
    if base == "sauce" and any(w in low for w in NOT_SAUCE_WORDS):
        return "snack"
    return base


# Приёмы пищи по типу блюда. Пусто там, где блюдо уместно везде — генератор
# сам разберётся, а вранья лучше избежать.
SUITABLE_BY_DISH = {
    "soup": ["lunch", "dinner"],
    "main": ["lunch", "dinner"],
    "salad": ["lunch", "dinner"],
    "side": ["lunch", "dinner"],
    "breakfast_dish": ["breakfast", "snack"],
    "snack": ["snack"],
    "dessert": ["snack"],
    "drink": ["breakfast", "snack"],
    "bakery": ["breakfast", "snack"],
    "sauce": [],
}

# ── единицы измерения ───────────────────────────────────────────────────────
# В выгрузке единицы записаны латинскими кодами парсера: g, ml, piece, tsp.
# Это не то, что читает человек, и не то, с чем работает остальной проект:
# список покупок складывает количества по таблице единиц (apps/shopping/
# services.py, _MG_UNIT_SYN), а кода «g» в ней нет — «700 g» и «300 г» для неё
# разные единицы, и в списке они окажутся двумя строками.
#
# Токены справа — канонические, ровно те, что использует shopping.
UNIT_RU = {
    "g": "г",
    "gr": "г",
    "kg": "кг",
    "ml": "мл",
    "l": "л",
    "piece": "шт",
    "pcs": "шт",
    "pc": "шт",
    "tsp": "ч.л.",
    "tbsp": "ст.л.",
    "cup": "стакан",
}


def normalize_units(ingredients: list) -> list:
    """Единицы — по-русски. Незнакомый код оставляем как есть: врать хуже."""
    out = []
    for ing in ingredients:
        if not isinstance(ing, dict):
            continue
        unit = (ing.get("unit") or "").strip()
        out.append({**ing, "unit": UNIT_RU.get(unit.lower(), unit)})
    return out


# ── способ приготовления ────────────────────────────────────────────────────
# Порядок важен: у блюда обычно несколько действий, и берём самое
# характерное — «запечь» важнее «нарезать».
METHOD_WORDS = (
    ("grilled", ("гриль", "мангал", "шашлык")),
    ("steamed", ("на пару", "пароварк")),
    ("baked", ("духовк", "запеч", "запек", "выпека", "выпеч", "противень")),
    ("stewed", ("тушить", "тушен", "тушён", "потуш")),
    ("fried", ("жарить", "обжар", "поджар", "сковород")),
    ("boiled", ("варить", "отвар", "кипят", "сварить", "проварить")),
)


def cooking_method_for(steps: list) -> str:
    text = " ".join(steps).lower()
    for method, words in METHOD_WORDS:
        if any(w in text for w in words):
            return method
    return ""


def cook_time_for(steps: list) -> int:
    """Суммарное время из шагов, минуты.

    Складываем все упомянутые интервалы: «обжарить 5 минут», «запекать 40».
    Это оценка снизу — часть времени в шагах не названа, — но она заведомо
    честнее, чем пусто: по этому полю работает фильтр «быстрые рецепты».
    """
    total = 0
    for s in steps:
        low = s.lower()
        for m in re.finditer(r"(\d+)(?:\s*[-–—]\s*(\d+))?\s*(минут|мин\b|час)", low):
            a, b, unit = m.group(1), m.group(2), m.group(3)
            value = (int(a) + int(b)) / 2 if b else int(a)
            total += value * (60 if unit == "час" else 1)
    return min(int(total), 32000)  # PositiveSmallIntegerField


# ── диет-флаги по составу ───────────────────────────────────────────────────
MEAT_FISH = (
    "говядин",
    "свинин",
    "баранин",
    "телятин",
    "куриц",
    "курин",
    "индейк",
    "утк",
    "утин",
    "гус",
    "фарш",
    "бекон",
    "ветчин",
    "колбас",
    "сосиск",
    "сало",
    "печен",
    "язык",
    "рыб",
    "лосос",
    "форел",
    "треск",
    "сельд",
    "тунец",
    "креветк",
    "кальмар",
    "мидии",
    "краб",
    "икра",
    "анчоус",
    "бульон куриный",
    "бульон мясной",
)
DAIRY = (
    "молок",
    "сливк",
    "сметан",
    "творог",
    "сыр",
    "кефир",
    "йогурт",
    "масло сливочное",
    "сгущен",
    "ряженк",
    "простокваш",
    "маскарпоне",
    "моцарелл",
    "сулугуни",
    "брынз",
    "пломбир",
    "мороженое",
)
EGG = ("яйц", "яич", "желток", "белок кури", "меланж")
HONEY = ("мёд", "мед ")
GLUTEN = (
    "мука пшенич",
    "мука ",
    "хлеб",
    "батон",
    "лаваш",
    "макарон",
    "паста ",
    "спагетти",
    "лапш",
    "манк",
    "булгур",
    "кускус",
    "перлов",
    "овсян",
    "сухар",
    "панировк",
    "тесто",
    "печенье",
    "вафл",
    "отруб",
    "ячнев",
    "пшенич",
    "рожь",
    "ржан",
    "солод",
    "пиво",
)
SUGAR = (
    "сахар",
    "сгущен",
    "мёд",
    "мед ",
    "сироп",
    "патока",
    "джем",
    "варень",
    "шоколад",
    "карамел",
    "глазур",
    "пудра сахарная",
)
OIL = ("масло", "жир ", "смалец", "маргарин")


def _has(names: str, words) -> bool:
    return any(w in names for w in words)


def _is_meat(name: str) -> bool:
    """Мясо или рыба ли это.

    Яйца проверяются РАНЬШЕ мяса: «яйцо куриное» содержит «курин», и без этой
    оговорки омлет оказывался мясным блюдом и выпадал из вегетарианских меню.
    """
    if _has(name, EGG):
        return False
    return _has(name, MEAT_FISH)


def _any_ingredient(ingredients: list, predicate) -> bool:
    return any(predicate((i.get("name") or "").lower()) for i in ingredients)


def diet_flags(ingredients: list) -> dict:
    names = " | ".join((i.get("name") or "").lower() for i in ingredients)
    meat = _any_ingredient(ingredients, _is_meat)
    dairy = _has(names, DAIRY)
    egg = _has(names, EGG)
    honey = _has(names, HONEY)
    gluten = _has(names, GLUTEN)
    return {
        "is_vegetarian": not meat,
        "is_vegan": not (meat or dairy or egg or honey),
        "is_gluten_free": not gluten,
        "is_lactose_free": not dairy,
        "has_added_sugar": _has(names, SUGAR),
    }


def protein_type_for(ingredients: list) -> str:
    names = " | ".join((i.get("name") or "").lower() for i in ingredients)
    animal = _any_ingredient(ingredients, _is_meat) or _has(names, DAIRY) or _has(names, EGG)
    plant = _has(names, ("фасол", "нут", "чечевиц", "горох", "соя", "тофу", "орех", "семеч"))
    if animal and plant:
        return "mixed"
    if animal:
        return "animal"
    if plant:
        return "plant"
    return ""


def oil_tsp_for(ingredients: list):
    """Чайные ложки масла. 1 ч. л. ≈ 5 г — на глаз масло почти всегда недооценивают."""
    grams = sum(float(i.get("grams") or 0) for i in ingredients if _has((i.get("name") or "").lower(), OIL))
    if grams <= 0:
        return None
    return Decimal(str(round(min(grams / 5.0, 99.9), 1)))


# ── разбор строки ───────────────────────────────────────────────────────────
def portion_grams(row: dict):
    """Вес порции: вес готового блюда ÷ число порций."""
    total = row.get("yield_weight_g") or row.get("cooked_weight_g") or 0
    servings = row.get("servings_min") or row.get("servings_max") or 0
    try:
        total, servings = float(total), float(servings)
    except (TypeError, ValueError):
        return None
    if total <= 0 or servings <= 0:
        return None
    portion = round(total / servings)
    # Порция в 5 граммов или в три килограмма — это ошибка исходных данных,
    # а не блюдо. Лучше пусто: пустое поле видно, неверное — нет.
    return portion if 20 <= portion <= 1500 else None


def _dec(value, digits=1):
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), digits)))
    except (TypeError, ValueError):
        return None


def open_rows(path: Path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


class Command(BaseCommand):
    help = "Импорт рецептов say7 с классификацией (без публикации)."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="JSONL или JSONL.GZ; по умолчанию — из reference/")
        parser.add_argument("--dry-run", action="store_true", help="только посчитать, ничего не писать")
        parser.add_argument("--limit", type=int, default=0, help="взять первые N строк")
        parser.add_argument(
            "--publish",
            action="store_true",
            help="опубликовать сразу (по умолчанию НЕТ: у рецептов нет фотографий)",
        )

    def handle(self, *args, **opts):
        path = Path(opts["file"]) if opts["file"] else DEFAULT_FILE
        if not path.exists():
            self.stderr.write(f"Файл не найден: {path}")
            return

        stats = dict(created=0, updated=0, skipped=0, no_portion=0, no_steps=0)
        by_dish = {}

        with transaction.atomic():
            for i, row in enumerate(open_rows(path)):
                if opts["limit"] and i >= opts["limit"]:
                    break
                result = self._one(row, opts)
                stats[result] += 1
                if result in ("created", "updated"):
                    d = dish_type_for(row.get("category", ""), row.get("name", ""))
                    by_dish[d] = by_dish.get(d, 0) + 1
                if not portion_grams(row):
                    stats["no_portion"] += 1
                if not row.get("steps"):
                    stats["no_steps"] += 1

            if opts["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if opts["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Добавлено {stats['created']}, обновлено {stats['updated']}, "
                f"пропущено (чужие) {stats['skipped']}"
            )
        )
        self.stdout.write(f"  без веса порции: {stats['no_portion']}, без шагов: {stats['no_steps']}")
        self.stdout.write("  по типам блюд: " + ", ".join(f"{k} {v}" for k, v in sorted(by_dish.items())))
        if not opts["publish"]:
            self.stdout.write(
                "  Все рецепты НЕ опубликованы: у них нет фотографий. "
                "Публиковать — вручную, после того как фото появятся."
            )
        self.stdout.write(
            "  Дальше прогоните классификаторы: classify_food_group, mg_classify_allergens, "
            "classify_meat_fish, mg_seed_plate, mg_backfill_recipe_products."
        )

    def _one(self, row: dict, opts) -> str:
        title = (row.get("name") or "").strip()
        if not title:
            return "skipped"

        legacy = f"{LEGACY_PREFIX}{row.get('site_id')}"
        existing = Recipe.objects.filter(legacy_id=legacy).first()
        if existing is None:
            # Рецепт с таким названием уже есть — не наш. Заводить второй значит
            # показать человеку дубль, а перезаписывать чужой нельзя тем более:
            # у него может быть фотография и он может быть опубликован, а мы
            # затрём и то и другое (импорт снимает публикацию).
            #
            # Своими считаем ТОЛЬКО записи с нашим legacy_id. Пустой legacy_id —
            # это рецепт, заведённый руками в админке, и он чужой.
            if Recipe.objects.filter(title__iexact=title).exists():
                return "skipped"

        ingredients = normalize_units(row.get("ingredients") or [])
        steps_raw = row.get("steps") or []
        steps = [{"text": t, "order": n} for n, t in enumerate(steps_raw, 1)]

        dish = dish_type_for(row.get("category", ""), title)
        portion = portion_grams(row)
        k100 = _dec(row.get("kcal_100g"))
        p100, f100, c100 = (_dec(row.get(k)) for k in ("protein_100g", "fat_100g", "carbs_100g"))

        # КБЖУ порции — произведение, а не отдельные данные: считаем, только
        # если известен вес порции.
        per_portion = {}
        if portion and k100 is not None:
            factor = Decimal(portion) / Decimal(100)
            per_portion = {
                "kcal": _dec(k100 * factor),
                "proteins": _dec(p100 * factor) if p100 is not None else None,
                "fats": _dec(f100 * factor) if f100 is not None else None,
                "carbs": _dec(c100 * factor) if c100 is not None else None,
            }

        servings = row.get("servings_min") or row.get("servings_max")
        servings = int(servings) if servings and 0 < float(servings) < 100 else None

        fields = dict(
            title=title[:512],
            legacy_id=legacy,
            source=Recipe.Source.PARSED,
            is_custom=False,
            is_published=bool(opts["publish"]),
            ingredients=ingredients,
            steps=steps,
            dish_type=dish,
            categories=[dish],
            suitable_for=SUITABLE_BY_DISH.get(dish, []),
            servings=servings,
            servings_normalized=servings,
            portion_g=portion,
            serving_size_label=(row.get("yield_text") or "")[:64],
            kcal_per_100g=k100,
            proteins_per_100g=p100,
            fats_per_100g=f100,
            carbs_per_100g=c100,
            nutrition={
                "calories": float(k100) if k100 is not None else None,
                "proteins": float(p100) if p100 is not None else None,
                "fats": float(f100) if f100 is not None else None,
                "carbs": float(c100) if c100 is not None else None,
            },
            cooking_method=cooking_method_for(steps_raw),
            cook_time_min=cook_time_for(steps_raw) or None,
            protein_type=protein_type_for(ingredients),
            oil_tsp=oil_tsp_for(ingredients),
            **diet_flags(ingredients),
            **{k: v for k, v in per_portion.items() if v is not None},
        )

        if opts["dry_run"]:
            return "updated" if existing else "created"

        # MG_SAY7LINK: связи рецепт→продукт здесь НЕ пересобираем.
        #
        # На сохранение рецепта висит сигнал, который ставит задачу пересборки,
        # а она ходит в ИИ на каждый рецепт отдельно. На полутора тысячах строк
        # это полторы тысячи обращений к платному провайдеру — вместо примерно
        # сорока, если тот же состав канонизировать пачками.
        #
        # Пачками это и делает mg_backfill_recipe_products: собирает все
        # уникальные сегменты состава разом, отправляет по 30 штук и только
        # потом строит связи. Он и указан в подсказке после импорта.
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing._mg_skip_link_rebuild = True
            existing.save()
            return "updated"

        obj = Recipe(**fields)
        obj._mg_skip_link_rebuild = True
        obj.save()
        return "created"
