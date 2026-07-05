"""Дедупликация каталога продуктов: слить дубли в канонический продукт.

Дубли возникают из-за авто-создания продуктов из ингредиентов рецептов
(«Огурец» без КБЖУ рядом с сид-«Огурцы» с КБЖУ) и из-за форм слова.

Канон определяется так:
  1) если имя продукта зарегистрировано как ВЫВЕРЕННЫЙ синоним (ProductAlias
     с source != auto) — канон берётся из алиаса («Огурец» -> «Огурцы»).
     Авто-синонимы (source=auto) из канонизации ингредиентов НЕ используются —
     они шумные и сливали разные продукты;
  2) иначе продукты с одинаковым нормализованным именем считаются дублями
     одной группы, канон выбирается по приоритету: есть КБЖУ > is_seed > min id.

Слияние (жёсткое): все ссылки (FridgeItem / RecipeProduct / ShoppingListItem /
ProductAlias) перепривязываются на канон, КБЖУ при необходимости копируется
в канон, имя дубля записывается синонимом, дубль удаляется.

По умолчанию — DRY-RUN (только показывает план). Запись — флагом --apply.

    docker compose exec -T backend python manage.py dedup_products            # dry-run
    docker compose exec -T backend python manage.py dedup_products --apply
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.aliases import normalize_alias
from apps.fridge.dedup import has_kbju, merge_product_into
from apps.fridge.models import Product, ProductAlias


def _canon_rank(p):
    """Меньше — лучше канон: с КБЖУ, потом is_seed, потом меньший id."""
    return (0 if has_kbju(p) else 1, 0 if p.is_seed else 1, p.id)


class Command(BaseCommand):
    help = "Слить дубли продуктов в канонический (жёсткое слияние). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить слияние (иначе только показать план).")
        parser.add_argument("--limit", type=int, default=30, help="Сколько примеров слияний показать.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]

        products = list(Product.objects.all().only("id", "name", "is_seed", "nutrition", "calories_per_100g"))
        pmap = {p.id: p for p in products}
        # ВАЖНО: для слияния доверяем ТОЛЬКО выверенным синонимам (manual/merge).
        # Авто-синонимы (source=auto) из канонизации ингредиентов шумные и сливали
        # разные продукты (напр. «Мука пшеничная» -> «Мука») — их не используем.
        alias_index = {a.alias_norm: a.product_id for a in ProductAlias.objects.exclude(source="auto")}

        # группы по нормализованному имени -> выбранный канон группы
        by_norm = defaultdict(list)
        for p in products:
            by_norm[normalize_alias(p.name)].append(p)
        canon_of_norm = {k: min(g, key=_canon_rank) for k, g in by_norm.items()}

        # дубль -> канон (один уровень)
        raw_map = {}
        for p in products:
            key = normalize_alias(p.name)
            canon = None
            tgt = alias_index.get(key)
            if tgt is not None and tgt in pmap and tgt != p.id:
                canon = pmap[tgt]
            else:
                c = canon_of_norm.get(key)
                if c is not None and c.id != p.id:
                    canon = c
            if canon is not None and canon.id != p.id:
                raw_map[p.id] = canon.id

        # резолвим цепочки (дубль -> канон -> канон), защита от циклов
        def resolve(pid, _seen=None):
            _seen = _seen or set()
            while pid in raw_map and pid not in _seen:
                _seen.add(pid)
                pid = raw_map[pid]
            return pid

        merges = {}  # dup_id -> final_canon_id
        for dup_id in raw_map:
            final = resolve(dup_id)
            if final != dup_id:
                merges[dup_id] = final

        # сгруппируем для отчёта
        groups = defaultdict(list)
        for dup_id, canon_id in merges.items():
            groups[canon_id].append(dup_id)

        self.stdout.write(f"Продуктов всего: {len(products)}; групп со слиянием: {len(groups)}; дублей: {len(merges)}.")
        shown = 0
        for canon_id, dups in groups.items():
            if shown >= limit:
                break
            names = ", ".join(f"«{pmap[d].name}»" for d in dups)
            self.stdout.write(f"  {names} -> «{pmap[canon_id].name}»")
            shown += 1
        if len(groups) > shown:
            self.stdout.write(f"  … и ещё {len(groups) - shown} групп")

        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        fridge_moved = recipe_moved = shop_moved = kbju_filled = deleted = 0
        with transaction.atomic():
            for dup_id, canon_id in merges.items():
                s = merge_product_into(pmap[dup_id], pmap[canon_id])
                fridge_moved += s["fridge"]
                recipe_moved += s["recipe"]
                shop_moved += s["shop"]
                kbju_filled += s["kbju"]
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Слияние выполнено. Удалено дублей: {deleted}; перенесено ссылок — "
                f"холодильник: {fridge_moved}, рецепты: {recipe_moved}, покупки: {shop_moved}; "
                f"КБЖУ перенесено в канон: {kbju_filled}."
            )
        )
