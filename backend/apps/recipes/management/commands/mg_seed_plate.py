"""MG_STRAT_PLATE_SEED (D-07) — авто-разметка Recipe.plate_component.

Правило (Вариант 2):
  plate_component = food_group, отфильтровано по dish_type-whitelist.
  food_group: protein->protein, grain->carb, vegetable->veg, fruit->veg.
  dish_type whitelist: main, side, salad, breakfast_dish, snack
    (исключены soup, drink, dessert, bakery, sauce — не годятся в «тарелку»).
Идемпотентно: пишет только там, где plate_component IS NULL
  (ручные правки в админке не затираются).
По умолчанию dry-run; запись только с --apply.
"""

from collections import Counter

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

FG_TO_PC = {
    "protein": "protein",
    "grain": "carb",
    "vegetable": "veg",
    "fruit": "veg",
}
DISH_WHITELIST = {"main", "side", "salad", "breakfast_dish", "snack"}


class Command(BaseCommand):
    help = "MG_STRAT_PLATE_SEED (D-07): seed Recipe.plate_component from food_group + dish_type whitelist."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="записать в БД (без флага — dry-run)")
        parser.add_argument("--show-samples", type=int, default=0, help="вывести N примеров присвоений")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        show = opts["show_samples"]

        qs = Recipe.objects.filter(is_published=True, plate_component__isnull=True).order_by("id")

        assign = Counter()
        skip_dish = Counter()  # dish_type вне whitelist
        skip_fg = Counter()  # food_group без маппинга
        to_update = []
        samples = []

        for r in qs.iterator(chunk_size=500):
            fg = r.food_group or ""
            dt = r.dish_type or ""
            pc = FG_TO_PC.get(fg)
            if pc is None:
                skip_fg[fg or "(none)"] += 1
                continue
            if dt not in DISH_WHITELIST:
                skip_dish[f"{dt or '(none)'}:{fg}"] += 1
                continue
            r.plate_component = pc
            to_update.append(r)
            assign[pc] += 1
            if show and len(samples) < show:
                samples.append((r.id, pc, fg, dt, r.title[:48]))

        if apply and to_update:
            for i in range(0, len(to_update), 500):
                Recipe.objects.bulk_update(to_update[i : i + 500], ["plate_component"])

        mode = "APPLIED" if apply else "DRY-RUN"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"[{mode}] кандидатов (NULL): {qs.count()}  присвоено: {len(to_update)}"))

        self.stdout.write("\n— Присвоено plate_component:")
        for k, v in sorted(assign.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k:8s} {v}")

        self.stdout.write("\n— Пропущено (food_group без роли):")
        for k, v in sorted(skip_fg.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k:10s} {v}")

        self.stdout.write("\n— Пропущено (dish_type вне whitelist) [dish:fg]:")
        for k, v in sorted(skip_dish.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k:24s} {v}")

        if samples:
            self.stdout.write("\n— Примеры присвоений:")
            for rid, pc, fg, dt, t in samples:
                self.stdout.write(f"    [{rid}] {pc:8s} fg={fg:9s} dt={dt:14s} {t}")
