"""Классификация новых рецептов-гарниров (импорт menunedeli) для генератора.

Импорт `import_menunedeli_recipes` создаёт рецепты БЕЗ `dish_type` и
`food_group` — генератор их не берёт (пул «other» в тарелку не идёт, а без
`food_group` не строится `plate_component`). Эта команда добивает разметку:

  - dish_type = "side" (гарнир; входит в whitelist mg_seed_plate — так плита
    получит из этих рецептов компонент carb/veg/protein). Ставим всем: партия
    целиком описана как гарниры, а роль на «тарелке» определяет food_group.
  - food_group — по составу ингредиентов + типу блюда, тем же классификатором,
    что и `classify_food_group` (detect_dish_type → resolve_food_group). Тип
    блюда детектируется ВНУТРЕННЕ (каша→grain, салат→vegetable и т.п.) только
    ради точного food_group; в БД dish_type всё равно "side".

После этой команды запусти `mg_seed_plate --apply` — он проставит
`plate_component` (carb/veg/protein) для стратегии «тарелка», и рецепты начнут
попадать в генерацию (стратегии 2 и 3; в стратегии 1 роли «side» нет — это by
design, как и у прежних russianfood-гарниров).

Идемпотентно: по умолчанию берёт только рецепты с `dish_type IS NULL`
(--force — переразметить всё под фильтр). Безопасно: dry-run по умолчанию,
запись по --apply, --limit N, --source-url меняет подстроку фильтра.

    docker compose exec -T backend python manage.py classify_garnishes --limit 10
    docker compose exec -T backend python manage.py classify_garnishes --apply
"""

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

from .classify_food_group import detect_dish_type, match_groups, resolve_food_group, to_grams

# Гарнир: партия импортирована как гарниры, роль на «тарелке» задаёт food_group.
DISH_TYPE = "side"


def _food_group(recipe):
    """food_group по составу + внутренне-детектированному типу блюда."""
    dish = detect_dish_type(recipe.title, recipe.categories)
    scores = defaultdict(float)
    for ing in recipe.ingredients or []:
        if not isinstance(ing, dict):
            continue
        grams = to_grams(str(ing.get("quantity", "")), str(ing.get("unit", "")))
        for g in match_groups(ing.get("name") or ""):
            scores[g] += grams
    return resolve_food_group(dish, scores)


class Command(BaseCommand):
    help = "Разметка новых рецептов-гарниров (dish_type=side + food_group). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--source-url", default="menunedeli", help="Фильтр: source_url содержит подстроку.")
        parser.add_argument("--force", action="store_true", help="Переразметить даже рецепты с уже заданным dish_type.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        src = opts["source_url"]
        force = opts["force"]

        qs = Recipe.objects.filter(source_url__icontains=src).order_by("id")
        if not force:
            qs = qs.filter(dish_type__isnull=True)

        fg_stat = Counter()
        to_update = []
        samples = []
        for r in qs.only("id", "title", "categories", "ingredients", "dish_type", "food_group").iterator():
            fg = _food_group(r)
            r.dish_type = DISH_TYPE
            r.food_group = fg
            to_update.append(r)
            fg_stat[fg] += 1
            if len(samples) < 12:
                samples.append(f"    #{r.id} [{fg:9s}] {r.title[:50]}")
            if limit and len(to_update) >= limit:
                break

        self.stdout.write(f"К разметке (source_url~{src}): {len(to_update)} рецептов (dish_type=side).")
        self.stdout.write("— food_group:")
        for k, v in fg_stat.most_common():
            self.stdout.write(f"    {k:10s} {v}")
        self.stdout.write("— примеры:")
        for s in samples:
            self.stdout.write(s)

        if apply and to_update:
            for i in range(0, len(to_update), 500):
                Recipe.objects.bulk_update(to_update[i : i + 500], ["dish_type", "food_group"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Готово. Размечено: {len(to_update)}. Далее: mg_seed_plate --apply "
                    "(plate_component для стратегии «тарелка»), затем classify_meat_fish."
                )
            )
        elif not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
