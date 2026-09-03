"""MG_SUITABLE: привести `suitable_for` в соответствие с ролями генератора.

Что сломано
-----------

`suitable_for` отвечает на вопрос «для каких приёмов пищи годится блюдо», и по
нему генератор отсеивает кандидатов: если список не пуст и не содержит текущего
приёма, рецепт не берётся (`_pick_for_role` в apps/menu/generator.py).

Беда в том, что разметка и раскладка приёмов разошлись. Импорт say7 помечал
десерты как `["snack"]`, а выпечку как `["breakfast", "snack"]` — но роль
«десерт» и роль «выпечка» существуют ТОЛЬКО в обеде, а перекус берёт блюда с
`dish_type='snack'`, а не десерты. Получился рецепт, помеченный годным туда,
куда он попасть не может, и негодным туда, где у него единственный слот.

Насколько это дорого обошлось (замер на проде, chat-83): из 45 десертов
достижимы 5, из 35 выпечек — 2. Остальные брались только по запасному пути,
когда достижимые уже израсходованы. В отчёте `mg_analyze_s1_repeats` это
выглядело как «пять рецептов в 20 прогонах из 20» — и как нехватка пула, хотя
пул был, просто до слота не доходил.

Что делает команда
------------------

Для каждого рецепта с НЕПУСТЫМ `suitable_for` проверяет, есть ли в нём хоть
один приём, где его роль вообще встречается. Если пересечения нет — добавляет
недостающие приёмы, ничего не удаляя.

Пустой `suitable_for` не трогаем: для генератора он означает «годится везде», и
фильтр такие рецепты пропускает без вопросов.

Таблица «роль → приёмы» НЕ выписана здесь руками, а выводится из
`MEAL_COMPONENTS` и `MEAL_TYPE_DB` самого генератора. Это принципиально: копия
разошлась бы с оригиналом ровно так же, как разошлась разметка импорта, — и
второй раз это заметили бы опять по повторяемости меню, а не по ошибке.

По умолчанию сухой прогон; запись только с --apply.

    python manage.py mg_fix_suitable_for
    python manage.py mg_fix_suitable_for --show-samples 20
    python manage.py mg_fix_suitable_for --apply
"""

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from apps.menu.generator import MEAL_COMPONENTS, MEAL_TYPE_DB
from apps.recipes.models import Recipe


def needed_meals_by_role() -> dict[str, set[str]]:
    """Роль → приёмы, в которых она реально встречается у генератора."""
    need: dict[str, set[str]] = defaultdict(set)
    for meal_slot, roles in MEAL_COMPONENTS.items():
        db_meal_type = MEAL_TYPE_DB[meal_slot]
        for role in roles:
            need[role].add(db_meal_type)
    return dict(need)


class Command(BaseCommand):
    help = "MG_SUITABLE: дописать в suitable_for приёмы, в которых роль рецепта вообще встречается"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="записать в БД (без флага — сухой прогон)")
        parser.add_argument("--show-samples", type=int, default=0, help="вывести N примеров правок")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        samples_left = opts["show_samples"]
        need = needed_meals_by_role()

        by_role = Counter()
        total = 0
        samples = []

        for dish_type, meals in sorted(need.items()):
            qs = Recipe.objects.filter(dish_type=dish_type).only("id", "title", "suitable_for", "dish_type")
            for recipe in qs.iterator():
                current = list(recipe.suitable_for or [])
                if not current:
                    # Пусто — «годится везде», фильтр такие пропускает.
                    continue
                if set(current) & meals:
                    continue

                updated = current + sorted(m for m in meals if m not in current)
                by_role[dish_type] += 1
                total += 1
                if samples_left > 0:
                    samples.append((recipe.id, dish_type, current, updated, recipe.title))
                    samples_left -= 1
                if apply:
                    recipe.suitable_for = updated
                    recipe.save(update_fields=["suitable_for"])

        prefix = "[APPLIED]" if apply else "[DRY-RUN]"
        self.stdout.write(f"\n{prefix} рецептов с недостижимой разметкой: {total}")

        self.stdout.write("\n— Роль → приёмы, где она встречается у генератора:")
        for role, meals in sorted(need.items()):
            self.stdout.write(f"    {role:16} {sorted(meals)}")

        if by_role:
            self.stdout.write("\n— Правится по ролям:")
            for role, count in by_role.most_common():
                self.stdout.write(f"    {role:16} {count:4}")
        else:
            self.stdout.write("\n— Править нечего: у всех рецептов разметка достижима.")

        if samples:
            self.stdout.write("\n— Примеры:")
            for rid, dish_type, was, now, title in samples:
                self.stdout.write(f"    [{rid}] {dish_type:14} {was} → {now}  {title[:50]}")

        if not apply and total:
            self.stdout.write("\nЭто сухой прогон. Записать — тот же вызов с --apply.")
