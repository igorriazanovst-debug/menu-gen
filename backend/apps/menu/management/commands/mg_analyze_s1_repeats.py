"""
Анализ повторяемости рецептов в стратегии 1 (s1).

Синтетически генерирует N меню (в памяти, без записи в БД) и считает,
как часто каждый рецепт попадает в результат.

Запуск:
  python manage.py mg_analyze_s1_repeats --runs 20 --days 7
  python manage.py mg_analyze_s1_repeats --runs 30 --days 7 --top 20
  python manage.py mg_analyze_s1_repeats --runs 20 --days 7 --role main

Опции:
  --runs N       Кол-во симулируемых меню (по умолч. 20)
  --days N       Кол-во дней в каждом меню (по умолч. 7)
  --top N        Вывести топ-N самых часто повторяемых (по умолч. 15)
  --role ROLE    Фильтровать по dish_type (main, side, soup, breakfast_dish, ...)
  --verbose      Показать по каждому рецепту в каких именно прогонах встречался
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from django.core.management.base import BaseCommand


class _FakeUser:
    id = 1
    email = "test@example.com"
    name = "Test"
    allergies = []
    disliked_products = []

    class _profile:
        calorie_target = None

    profile = _profile()


class _FakeMember:
    """Минимальный объект, имитирующий FamilyMember для генератора."""

    def __init__(self, pk: int = 1):
        self.id = pk
        self.name = "Test"
        self.user = _FakeUser()
        self.cheat_day = None
        self.cheat_weekday = None


class _FakeFamily:
    id = 1
    plan_code = "free"


class Command(BaseCommand):
    help = "Анализ повторяемости рецептов в стратегии s1 (синтетический тест)"

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=20, help="кол-во меню для симуляции")
        parser.add_argument("--days", type=int, default=7, help="дней в каждом меню")
        parser.add_argument("--top", type=int, default=15, help="топ-N рецептов в отчёте")
        parser.add_argument("--role", default="", help="фильтровать по dish_type")
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from apps.menu.generator import MenuGenerator
        from apps.recipes.models import Recipe

        runs = options["runs"]
        days = options["days"]
        top_n = options["top"]
        filter_role = options["role"].strip()
        verbose = options["verbose"]

        member = _FakeMember(pk=1)
        family = _FakeFamily()

        # Размер пула по каждой роли
        pool_sizes: Counter = Counter()

        repeat_counter: Counter = Counter()  # recipe_id → сколько прогонов содержат этот рецепт
        run_sets: dict = defaultdict(set)  # recipe_id → set of run indices

        total_slots = 0
        total_distinct_per_run: list[int] = []

        self.stdout.write(f"[mg_analyze_s1_repeats] runs={runs} days={days} role='{filter_role or 'all'}'")
        self.stdout.write("Загружаем пул рецептов...")

        # Один раз строим пул, чтобы понять его размер
        gen0 = MenuGenerator(
            family=family,
            members=[member],
            period_days=days,
            start_date=date.today(),
            plan_code="free",
            filters={"strategy": "1"},
        )
        all_recipes = gen0._build_recipe_pool()
        pools0 = gen0._build_pools_by_role(all_recipes)
        for role, pool in pools0.items():
            pool_sizes[role] = len(pool)
        total_pool = len(all_recipes)

        self.stdout.write(f"Всего рецептов в пуле: {total_pool}")
        self.stdout.write("Размеры пулов по ролям:")
        for role, sz in sorted(pool_sizes.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {role:<20} {sz}")
        self.stdout.write("")

        # ── математика: сколько рецептов нужно по каждой роли ────────────────────
        # d = слотов в неделю; N >= d/T, где T — допустимое пересечение соседних меню.
        # Множители: min=1×d, good(≤25%)=4×d, great(≤10%)=10×d.
        self._print_demand_table(gen0, pool_sizes)

        # Симулируем N прогонов
        for run_idx in range(runs):
            gen = MenuGenerator(
                family=family,
                members=[member],
                period_days=days,
                start_date=date.today(),
                plan_code="free",
                filters={"strategy": "1"},
            )
            try:
                items = gen.generate()
            except Exception as exc:
                self.stdout.write(f"  Прогон {run_idx+1}: ОШИБКА — {exc}")
                continue

            seen_ids: set = set()
            for item in items:
                recipe = item.get("recipe")
                if recipe is None:
                    continue
                rid = recipe.id
                role = item.get("component_role") or ""
                if filter_role and role != filter_role:
                    continue
                seen_ids.add(rid)
                run_sets[rid].add(run_idx)
                total_slots += 1

            distinct = len(seen_ids)
            total_distinct_per_run.append(distinct)

        # Строим счётчик: сколько прогонов содержат каждый рецепт
        for rid, run_set in run_sets.items():
            repeat_counter[rid] = len(run_set)

        # Загружаем заголовки топ-N рецептов
        top_ids = [rid for rid, _ in repeat_counter.most_common(top_n)]
        top_recipes = list(Recipe.objects.filter(id__in=top_ids).only("id", "title", "dish_type"))
        titles = {r.id: r.title for r in top_recipes}
        roles_map = {r.id: r.dish_type for r in top_recipes}

        # ── отчёт ───────────────────────────────────────────────────────────────
        self.stdout.write("=" * 65)
        self.stdout.write(f"РЕЗУЛЬТАТЫ  (runs={runs}, days={days})")
        self.stdout.write("=" * 65)

        avg_distinct = sum(total_distinct_per_run) / max(1, len(total_distinct_per_run))
        min_d = min(total_distinct_per_run, default=0)
        max_d = max(total_distinct_per_run, default=0)
        self.stdout.write(f"Уникальных рецептов за прогон: avg={avg_distinct:.1f}  min={min_d}  max={max_d}")
        self.stdout.write(f"Уникальных рецептов встретилось хотя бы раз: {len(repeat_counter)}")
        self.stdout.write("")

        # Распределение: сколько рецептов встречается в 1, 2, ..., N прогонах
        freq_dist: Counter = Counter(repeat_counter.values())
        self.stdout.write("Распределение по частоте появления (прогонов → кол-во рецептов):")
        for freq in sorted(freq_dist.keys(), reverse=True)[:15]:
            bar = "█" * min(freq_dist[freq], 40)
            pct = freq / runs * 100
            self.stdout.write(f"  {freq:>3}/{runs} прогонов ({pct:4.0f}%): {freq_dist[freq]:>4} рецептов  {bar}")
        self.stdout.write("")

        self.stdout.write(f"Топ-{top_n} самых повторяющихся рецептов:")
        self.stdout.write(f"  {'%':>6}  {'прог':>4}  {'роль':<16}  заголовок")
        self.stdout.write("  " + "-" * 60)
        for rid, count in repeat_counter.most_common(top_n):
            pct = count / runs * 100
            title = titles.get(rid, f"id={rid}")
            role = roles_map.get(rid, "?")
            if verbose:
                run_list = sorted(run_sets[rid])
                self.stdout.write(f"  {pct:5.0f}%  {count:>4}  {role:<16}  {title}")
                self.stdout.write(f"         прогоны: {run_list}")
            else:
                self.stdout.write(f"  {pct:5.0f}%  {count:>4}  {role:<16}  {title}")

        self.stdout.write("")

        # Резюме: есть ли проблема?
        high_repeat = sum(1 for c in repeat_counter.values() if c >= runs * 0.5)
        very_high = sum(1 for c in repeat_counter.values() if c >= runs * 0.8)
        self.stdout.write(f"Рецептов в ≥50% прогонов: {high_repeat}  (≥80%: {very_high})")

        # MG_SWEETROLE: условие про avg_distinct считается ТОЛЬКО для полного
        # прогона. Порог days*2 подобран для меню целиком (около семи блюд в
        # день); при --role в выборке остаются слоты одной роли, и у десерта их
        # ровно семь на неделю — то есть avg_distinct=7 при пороге 14, и тревога
        # горела бы всегда, даже когда повторяемости нет вовсе. Так и вышло
        # (chat-83): отчёт по десертам показал «в ≥50% прогонов: 0» и тут же
        # «ПРОБЛЕМА», что прямо противоречит само себе.
        thin_menu = (not filter_role) and (avg_distinct < days * 2)
        if very_high > 0 or thin_menu:
            self.stdout.write("⚠  ПРОБЛЕМА: высокая повторяемость обнаружена.")
        else:
            self.stdout.write("✓  Повторяемость в норме.")

    def _print_demand_table(self, gen, pool_sizes):
        """Считает недельный спрос слотов по ролям и минимально нужный размер пула."""
        from apps.menu.generator import MEAL_COMPONENTS, MEAL_PLAN_3, MEAL_PLAN_5

        def weekly_demand(meal_plan):
            demand: Counter = Counter()
            for meal_slot in meal_plan:
                for role in MEAL_COMPONENTS.get(meal_slot, ()):
                    if role == "soup" and not getattr(gen, "with_soup", True):
                        continue
                    demand[role] += 7  # 7 дней в неделе
            return demand

        d3 = weekly_demand(MEAL_PLAN_3)
        d5 = weekly_demand(MEAL_PLAN_5)

        # объединяем роли из обоих планов
        roles = sorted(set(d3) | set(d5), key=lambda r: -(d3.get(r, 0)))

        self.stdout.write("=" * 65)
        self.stdout.write("СКОЛЬКО РЕЦЕПТОВ НУЖНО ПО РОЛЯМ (N ≥ d/T)")
        self.stdout.write("  d3/d5 — слотов в неделю при плане 3 / 5 приёмов")
        self.stdout.write("  min=1×d (нет повторов в неделю), good=4×d (≤25%), great=10×d (≤10%)")
        self.stdout.write("=" * 65)
        header = f"  {'роль':<16} {'пул':>4} {'d3':>3} {'d5':>3} {'min':>4} {'good':>5} {'great':>6}  статус"
        self.stdout.write(header)
        self.stdout.write("  " + "-" * 61)
        for role in roles:
            n = pool_sizes.get(role, 0)
            demand3 = d3.get(role, 0)
            demand5 = d5.get(role, 0)
            d = max(demand3, demand5)  # худший случай (5 приёмов)
            mn, good, great = d, 4 * d, 10 * d
            if n < mn:
                status = "🔴 повторы в неделю"
            elif n < good:
                status = "🟡 мало для свежести"
            elif n < great:
                status = "🟢 ок"
            else:
                status = "🟢 отлично"
            self.stdout.write(f"  {role:<16} {n:>4} {demand3:>3} {demand5:>3} {mn:>4} {good:>5} {great:>6}  {status}")
        self.stdout.write("")
