"""MG_UNITNORM: веса единиц товара — посмотреть, чего не хватает, и заполнить.

Холодильник хранит покупку: яйца в штуках, творог в упаковках, молоко в литрах.
Рецепты считают граммами. Без веса единицы эти две правды не встречаются, и
товар уходит в «не хватило», сколько бы его дома ни лежало.

Команда делает три вещи, и каждая отдельным запуском:

1. **Показать, что реально мешает.** Не весь каталог, а только те товары,
   которые прямо сейчас лежат у людей в холодильниках в неграммовых единицах.
   Остальным вес не нужен: они и так сходятся.

2. **Записать вес руками** — `--set "41=шт:55"`. Столько и будет, никаких
   догадок.

3. **Оценить весы моделью** — `--ai`. По умолчанию это DRY-RUN: печатает, что
   получилось, и ничего не пишет. Запись — только с `--apply`.

Почему не угадывать «в среднем по категории»: неверный вес не виден никому.
Человек получит не тот остаток и узнает об этом, только открыв холодильник.
Поэтому либо явная цифра, либо честная нехватка, как раньше.

    docker compose run -d --name mg-weights backend python manage.py mg_unit_weights
    docker compose run -d --name mg-weights backend python manage.py mg_unit_weights --set "41=шт:55"
    docker compose run -d --name mg-weights backend python manage.py mg_unit_weights --ai
    docker compose run -d --name mg-weights backend python manage.py mg_unit_weights --ai --apply
"""

import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from apps.fridge.models import FridgeItem, Product, ProductUnitWeight
from apps.fridge.units import norm_unit

SYSTEM = (
    "Ты — технолог общественного питания. На вход дан JSON-массив объектов "
    "{i, name, unit} — название продукта и единица, в которой его хранят. Для "
    "каждого верни средний вес ОДНОЙ такой единицы в граммах как JSON-массив "
    "объектов {i, grams}: grams — число. Для жидкостей в литрах учитывай "
    "плотность (1 л молока ≈ 1030 г). Если для этого продукта единица "
    "бессмысленна или вес непредсказуем (например «упаковка» неизвестного "
    "размера) — верни {i, unknown: true}. Отвечай ТОЛЬКО валидным JSON-массивом."
)

# Границы правдоподобия. Одна штука тяжелее десяти килограммов или легче
# десятой доли грамма — это не оценка, а промах модели: такое не пишем.
_MIN_G = Decimal("0.1")
_MAX_G = Decimal("10000")


def _mass_unit(unit):
    """Единица и так в массе — вес ей не нужен."""
    from apps.shopping.services import _mg_unit_tables

    mass, _vol, _clove = _mg_unit_tables()
    return norm_unit(unit) in mass


def missing_pairs():
    """Пары (товар, единица), которых не хватает прямо сейчас.

    Смотрим на холодильники живых семей, а не на каталог: вес нужен там, где
    продукт лежит в неграммовой единице. Всему остальному каталогу он ни к чему.
    """
    have = {(row.product_id, row.unit) for row in ProductUnitWeight.objects.all()}
    counts = defaultdict(int)
    for it in FridgeItem.objects.filter(is_deleted=False).exclude(product__isnull=True):
        u = norm_unit(it.unit)
        if not u or _mass_unit(u):
            continue
        if (it.product_id, u) in have:
            continue
        counts[(it.product_id, u)] += 1
    return counts


class Command(BaseCommand):
    help = "MG_UNITNORM: показать/заполнить вес единицы товара (шт, упаковка, л)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--set",
            action="append",
            default=[],
            metavar='"ID=единица:граммы"',
            help='Записать вес руками, например --set "41=шт:55". Можно несколько раз.',
        )
        parser.add_argument("--ai", action="store_true", help="Оценить недостающие веса моделью.")
        parser.add_argument("--apply", action="store_true", help="Записать результат --ai (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N пар (0 = все).")
        parser.add_argument("--batch", type=int, default=20, help="Размер чанка для одного запроса к AI.")

    def _say(self, line):
        self.stdout.write(line)
        self.stdout.flush()

    # ── ручная запись ────────────────────────────────────────────────────────

    def _apply_manual(self, specs):
        for spec in specs:
            try:
                left, right = spec.split("=", 1)
                unit_raw, grams_raw = right.split(":", 1)
                pid = int(left.strip())
                grams = Decimal(grams_raw.strip().replace(",", "."))
            except (ValueError, InvalidOperation):
                self.stderr.write(self.style.ERROR(f'Не разобрал «{spec}». Формат: "41=шт:55".'))
                continue
            unit = norm_unit(unit_raw)
            product = Product.objects.filter(pk=pid).first()
            if product is None:
                self.stderr.write(self.style.ERROR(f"Товара #{pid} нет."))
                continue
            if grams <= 0:
                self.stderr.write(self.style.ERROR(f"#{pid}: вес должен быть больше нуля."))
                continue
            row, created = ProductUnitWeight.objects.update_or_create(
                product=product,
                unit=unit,
                defaults={"grams": grams, "source": ProductUnitWeight.Source.MANUAL},
            )
            what = "записал" if created else "обновил"
            self._say(f"{what}: #{pid} {product.name} — 1 {unit} = {row.grams} г")

    # ── отчёт ────────────────────────────────────────────────────────────────

    def _report(self, counts):
        if not counts:
            self._say("Все товары в холодильниках сходятся с рецептами: недостающих весов нет.")
            return
        names = {p.id: p.name for p in Product.objects.filter(id__in={pid for pid, _ in counts})}
        self._say(f"Не хватает весов: {len(counts)} пар «товар + единица».")
        self._say("Столбцы: сколько позиций в холодильниках | товар | единица | команда для записи")
        for (pid, unit), n in sorted(counts.items(), key=lambda kv: -kv[1]):
            name = names.get(pid, "?")
            self._say(f'  {n:>3} | {name} (#{pid}) | {unit} | --set "{pid}={unit}:<граммы>"')

    # ── оценка моделью ───────────────────────────────────────────────────────

    def _fill_ai(self, counts, apply, batch, limit):
        try:
            from apps.common.ai_provider import check_batch_ai_available, complete_with_retry, get_batch_ai_client

            client = get_batch_ai_client()
            self._say("Проверяю провайдера…")
            check_batch_ai_available(log=self._say)
            self._say("Провайдер отвечает.")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ИИ-провайдер недоступен: {e}"))
            self.stderr.write(self.style.ERROR("Проверить настройки: manage.py mg_ai_ping"))
            return

        from apps.common.progress import BatchProgress
        from apps.fridge.services import _parse_json_loose

        names = {p.id: p.name for p in Product.objects.filter(id__in={pid for pid, _ in counts})}
        targets = [(pid, unit) for (pid, unit), _n in sorted(counts.items(), key=lambda kv: -kv[1])]
        if limit > 0:
            targets = targets[:limit]
        self._say(f"Пар к оценке: {len(targets)} (batch={batch}). {'ЗАПИСЬ' if apply else 'DRY-RUN, ничего не пишем'}.")

        written = unknown = failed = 0
        nchunks = (len(targets) + batch - 1) // batch
        progress = BatchProgress(len(targets), nchunks, self._say)

        for base in range(0, len(targets), batch):
            grp = targets[base : base + batch]
            payload = json.dumps(
                [{"i": i, "name": names.get(pid, ""), "unit": unit} for i, (pid, unit) in enumerate(grp)],
                ensure_ascii=False,
            )
            try:
                raw = complete_with_retry(
                    client, log=self._say, prompt=payload, system=SYSTEM, max_tokens=2000, temperature=0.0
                )
                data = _parse_json_loose(raw)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"  чанк {base // batch + 1}: ошибка AI: {e}"))
                failed += len(grp)
                progress.chunk_done(failed=True)
                continue
            if not isinstance(data, list):
                failed += len(grp)
                progress.chunk_done(failed=True)
                continue

            by_i = {}
            for d in data:
                if isinstance(d, dict) and "i" in d:
                    try:
                        by_i[int(d["i"])] = d
                    except (TypeError, ValueError):
                        pass

            for idx, (pid, unit) in enumerate(grp):
                d = by_i.get(idx)
                if d is None:
                    failed += 1
                    continue
                if d.get("unknown") is True:
                    unknown += 1
                    self._say(f"  не берётся: {names.get(pid, '?')} (#{pid}) — {unit}")
                    continue
                try:
                    grams = Decimal(str(d.get("grams")))
                except (InvalidOperation, TypeError, ValueError):
                    failed += 1
                    continue
                if not (_MIN_G <= grams <= _MAX_G):
                    failed += 1
                    self._say(f"  отбросил как бред: {names.get(pid, '?')} (#{pid}) — 1 {unit} = {grams} г")
                    continue
                self._say(f"  {names.get(pid, '?')} (#{pid}): 1 {unit} = {grams} г")
                if apply:
                    ProductUnitWeight.objects.update_or_create(
                        product_id=pid,
                        unit=unit,
                        defaults={"grams": grams, "source": ProductUnitWeight.Source.AI},
                    )
                written += 1
            progress.chunk_done()

        self._say("")
        self._say(f"Оценено: {written} | не берётся: {unknown} | не получилось: {failed}")
        if not apply:
            self._say("Это был dry-run. Записать: тот же запуск с --apply.")

    def handle(self, *args, **opts):
        if opts["set"]:
            self._apply_manual(opts["set"])
            self._say("")

        counts = missing_pairs()
        if opts["ai"]:
            if not counts:
                self._say("Оценивать нечего: недостающих весов нет.")
                return
            self._fill_ai(counts, opts["apply"], max(1, opts["batch"]), opts["limit"])
            return

        self._report(counts)
