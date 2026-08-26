"""GPT-дедуп каталога: схлопнуть варианты названий одного продукта.

Детерминированный dedup_products не ловит дубли с перестановкой слов,
сокращениями и опечатками («Йогурт греческий» / «Греческий йогурт» /
«Греч. йогурт»). Здесь AI приводит каждое имя к каноничной форме, продукты
с совпавшим каноном группируются, и группа сливается в один продукт тем же
безопасным способом (merge_product_into), что и детерминированный дедуп.

ВАЖНО: AI инструктируется СОХРАНЯТЬ различающие признаки (жирность, вид/сорт:
греческий, обезжиренный, копчёный, говяжий и т.п.) — разные виды одного
продукта НЕ объединяются.

Безопасно: по умолчанию DRY-RUN (печатает план «варианты -> канон»); запись —
флагом --apply. --limit / --batch — для тестовой партии и контроля стоимости.

    docker compose exec -T backend python manage.py dedup_products_ai --limit 200
    docker compose exec -T backend python manage.py dedup_products_ai --apply
"""

import json
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.aliases import normalize_alias
from apps.fridge.dedup import has_kbju, merge_product_into
from apps.fridge.models import Product

SYSTEM = (
    "Тебе дан JSON-массив объектов {i, name} — названия продуктов питания из "
    "каталога. Для каждого верни КАНОНИЧЕСКОЕ имя в JSON-массиве {i, canon}. "
    "Канон — то же название, приведённое к единой форме: нормализуй порядок "
    "слов, раскрой сокращения, исправь опечатки, единственное число, убери "
    "лишние слова. КРИТИЧНО: сохраняй различающие признаки (жирность %, вид и "
    "сорт: греческий, обезжиренный, копчёный, говяжий, пшеничная и т.п.) — "
    "РАЗНЫЕ виды одного продукта НЕЛЬЗЯ сводить к одному канону. Если это не "
    "продукт (блюдо, фраза, мусор) — верни canon равным исходному name. "
    "Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)


def _survivor_rank(p, key):
    """Лучший выживший в группе: сначала курируемый сид-продукт и наличие КБЖУ
    (чистое имя/категория), и только потом совпадение имени с канон-формой от AI.
    Иначе выжил бы ugly авто-вариант (напр. «лук зеленый» вместо «Зелёный лук»)."""
    return (
        0 if p.is_seed else 1,
        0 if has_kbju(p) else 1,
        0 if normalize_alias(p.name) == key else 1,
        p.id,
    )


class Command(BaseCommand):
    help = "GPT-дедуп: схлопнуть варианты названий (порядок слов/сокращения/опечатки). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить слияние (иначе только план).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N продуктов (0 = все).")
        parser.add_argument("--batch", type=int, default=20, help="Размер чанка для запроса к AI.")
        parser.add_argument("--show", type=int, default=40, help="Сколько групп показать в плане.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        batch = max(1, opts["batch"])
        show = opts["show"]

        try:
            from apps.common.ai_provider import get_ai_client

            client = get_ai_client()
            # MG_AIPING: фабрика только собирает клиента и ловит пустой ключ.
            # Неверный ключ виден лишь по ответу сервиса — без запроса команда
            # уходила в прогон и ловила 401 на каждой пачке.
            from apps.common.ai_provider import check_ai_available

            check_ai_available()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ИИ-провайдер недоступен: {e}"))
            self.stderr.write(self.style.ERROR("Проверить настройки: manage.py mg_ai_ping"))
            return
        try:
            from apps.fridge.services import _parse_json_loose
        except Exception:
            _parse_json_loose = None
        if _parse_json_loose is None:
            self.stderr.write(self.style.ERROR("Парсер JSON недоступен (_parse_json_loose)."))
            return

        products = list(Product.objects.all().order_by("id"))
        if limit > 0:
            products = products[:limit]
        self.stdout.write(f"Продуктов к анализу: {len(products)} (batch={batch}).")

        # product_id -> канон-ключ (нормализованный канон от AI)
        canon_key = {}
        nchunks = (len(products) + batch - 1) // batch
        for base in range(0, len(products), batch):
            grp = products[base : base + batch]
            self.stdout.write(f"  AI чанк {base // batch + 1}/{nchunks}…")
            self.stdout.flush()
            payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
            try:
                raw = client.complete(prompt=payload, system=SYSTEM, max_tokens=3000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"  чанк {base // batch + 1}: ошибка AI: {e}"))
                data = None
            if not isinstance(data, list):
                continue
            for d in data:
                if not isinstance(d, dict) or "i" not in d:
                    continue
                try:
                    j = int(d["i"])
                except (TypeError, ValueError):
                    continue
                if not (0 <= j < len(grp)):
                    continue
                canon = d.get("canon")
                key = normalize_alias(canon) if isinstance(canon, str) else ""
                if key:
                    canon_key[grp[j].id] = key

        # группируем по канон-ключу
        pmap = {p.id: p for p in products}
        groups = defaultdict(list)
        for pid, key in canon_key.items():
            groups[key].append(pmap[pid])

        # оставляем только реальные группы (>=2 разных продукта)
        merges = []  # (survivor, [dups])
        for key, members in groups.items():
            if len(members) < 2:
                continue
            survivor = min(members, key=lambda p: _survivor_rank(p, key))
            dups = [p for p in members if p.id != survivor.id]
            if dups:
                merges.append((survivor, dups))

        total_dups = sum(len(d) for _, d in merges)
        self.stdout.write(f"Групп со слиянием: {len(merges)}; дублей к удалению: {total_dups}.")
        for survivor, dups in merges[:show]:
            names = ", ".join(f"«{d.name}»" for d in dups)
            self.stdout.write(f"  {names} -> «{survivor.name}»")
        if len(merges) > show:
            self.stdout.write(f"  … и ещё {len(merges) - show} групп")

        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        fridge_moved = recipe_moved = shop_moved = kbju_filled = deleted = 0
        with transaction.atomic():
            for survivor, dups in merges:
                for dup in dups:
                    s = merge_product_into(dup, survivor)
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
