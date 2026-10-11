"""Дозаполнить КБЖУ из OpenFoodFacts по штрих-коду — бесплатно и по факту.

Это первая из двух починок каталога, и запускать её надо раньше платной.
`fill_kbju_ai` просит модель ОЦЕНИТЬ КБЖУ по названию — это догадка и это
деньги. Здесь же у продукта есть штрих-код, а значит в открытой базе лежит
то, что написано на самой упаковке. Бесплатно и точнее.

Почему дыры вообще есть, хотя продукт приехал из OFF:

* **Килоджоули.** У европейских товаров этикетка обязана нести кДж, а ккал —
  нет, и в базу попадает только `energy_100g`. Разбор OFF брал исключительно
  `energy-kcal*` и для таких записей возвращал «неизвестно», хотя число есть
  и переводится точно (MG_OFFKJ в services.py). Повторный запрос забирает их.
* **Карточка пополнилась.** OFF ведут люди; товар, у которого год назад не
  было состава, сегодня его имеет.
* **Массовая загрузка.** `import_barcode_catalog` пишет КБЖУ, только если оно
  проходит проверку на правдоподобие, иначе оставляет пусто — намеренно.

Что команда НЕ делает:

* **не перезаписывает то, что уже есть.** Заполняются только пустые поля.
  Если в каталоге стоит калорийность, она остаётся, даже когда OFF не
  согласен: разбираться, кто прав, — отдельная работа, и молча менять числа
  под человеком нельзя.
* **не трогает личные продукты людей** (`owner_family` заполнен) — та же
  граница, что и у `fill_kbju_ai`.
* **не выдумывает.** Нет данных в OFF — позиция остаётся пустой и достаётся
  платной починке.

Оговорка до запуска: по умолчанию берутся только продукты, видимые в выборе.
Основная масса записей из OFF — источник `off_bulk`, он скрыт из списков
(десятки тысяч SKU), и забирать их нужно отдельным осознанным решением:
`--include-hidden`. Денег это не стоит, но идёт небыстро — один запрос к OFF
на позицию.

    docker compose exec -T backend python manage.py refill_kbju_from_off --count-only
    docker compose exec -T backend python manage.py refill_kbju_from_off --limit 50
    docker compose exec -T backend python manage.py refill_kbju_from_off --limit 50 --apply

Весь хвост — длинный прогон, и через `exec` его нельзя: тот умирает вместе с
сессией. Отдельным контейнером:

    docker compose run -d --name mg-offkbju backend python manage.py \\
        refill_kbju_from_off --apply --include-hidden
    docker logs -f mg-offkbju
    docker rm mg-offkbju            # только после того, как итог прочитан
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.fridge.models import Product
from apps.fridge.services import _normalize_off_product, fetch_off_result
from apps.fridge.visibility import HIDDEN_FROM_PICKERS

NO_NUTRITION = Q(nutrition__isnull=True) | Q(nutrition={})
NO_KCAL = Q(calories_per_100g__isnull=True)


class Command(BaseCommand):
    help = "Дозаполнить КБЖУ из OpenFoodFacts по штрих-коду (бесплатно, только пустые поля)"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="записывать (по умолчанию только показывать)")
        parser.add_argument("--limit", type=int, default=0, help="обработать только N позиций")
        parser.add_argument(
            "--include-hidden",
            action="store_true",
            help=f"взять и скрытые из выбора источники ({', '.join(HIDDEN_FROM_PICKERS)}) — их десятки тысяч",
        )
        parser.add_argument(
            "--count-only",
            action="store_true",
            help="напечатать, скольких это коснётся, и выйти, не обращаясь к OFF",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.7,
            help="пауза между запросами к OFF, секунды (по умолчанию 0.7 — около 85 запросов в минуту)",
        )

    def _targets(self, opts):
        qs = (
            Product.objects.filter(owner_family__isnull=True)
            .filter(NO_NUTRITION | NO_KCAL)
            .exclude(barcode__isnull=True)
            .exclude(barcode="")
        )
        if not opts["include_hidden"]:
            qs = qs.exclude(source__in=HIDDEN_FROM_PICKERS)
        qs = qs.order_by("id")
        limit = opts["limit"]
        return qs[:limit] if limit > 0 else qs

    def _ask_off(self, barcode: str, pause: float):
        """Спросить OFF, с отступлением при отказе.

        Отказ чаще всего означает, что мы спрашиваем слишком часто. Разумный
        ответ на это — подождать подольше, а не повторить немедленно.
        """
        for attempt, backoff in enumerate((0.0, 2.0, 6.0)):
            if backoff:
                time.sleep(backoff if pause else 0)
            raw, outcome = fetch_off_result(barcode)
            if outcome != "error":
                return raw, outcome
            if attempt == 0:
                self.stdout.write(self.style.WARNING(f"  {barcode}: OFF не ответил, жду и пробую ещё раз"))
        return {}, "error"

    def handle(self, *args, **opts):
        targets = self._targets(opts)

        # --count-only отвечает и выходит ДО первого запроса к OFF. Так же, как
        # в fill_kbju_ai: там на этом обожглись — «сухой» прогон оказался сухим
        # только для базы.
        if opts["count_only"]:
            self.stdout.write(f"Позиций со штрих-кодом и дырой в КБЖУ: {targets.count()}")
            return

        rows = list(targets)
        total = len(rows)
        if not total:
            self.stdout.write("Нечего дозаполнять.")
            return

        apply = opts["apply"]
        pause = max(0.0, opts["sleep"])
        self.stdout.write(
            f"{'ЗАПИСЬ' if apply else 'ПОКАЗ (без записи)'}: {total} позиций, пауза {pause} с между запросами."
        )

        filled_kcal = filled_macro = not_found = no_data = failed = 0
        in_a_row = 0
        for i, p in enumerate(rows, 1):
            if i > 1 and pause:
                time.sleep(pause)

            raw, outcome = self._ask_off(p.barcode, pause)
            if outcome == "error":
                failed += 1
                in_a_row += 1
                # Двадцать отказов подряд — это не «не повезло», а OFF нас
                # больше не обслуживает. Долбиться дальше и грубо, и
                # бессмысленно: итог всё равно будет враньём.
                if in_a_row >= 20:
                    self.stdout.write(
                        self.style.ERROR(
                            f"20 отказов подряд на позиции {i} из {total}. OFF не отвечает — "
                            "останавливаюсь. Обработанное сохранено, прогон можно повторить позже."
                        )
                    )
                    break
                continue
            in_a_row = 0
            if outcome == "not_found" or not raw:
                not_found += 1
                continue
            fields = _normalize_off_product(raw)
            if not fields:
                not_found += 1
                continue

            updates = []
            kcal = fields.get("calories_per_100g")
            if p.calories_per_100g is None and kcal is not None:
                p.calories_per_100g = kcal
                updates.append("calories_per_100g")
                filled_kcal += 1
            nutrition = fields.get("nutrition") or {}
            if not p.nutrition and nutrition:
                p.nutrition = nutrition
                updates.append("nutrition")
                filled_macro += 1

            if not updates:
                no_data += 1
                continue

            self.stdout.write(f"  {p.barcode:<15} {p.name[:50]:<50} {', '.join(updates)}")
            if apply:
                p.save(update_fields=updates)

            if i % 100 == 0:
                self.stdout.write(f"  …обработано {i} из {total}")

        self.stdout.write("")
        self.stdout.write(f"Обработано:            {total}")
        self.stdout.write(f"  проставлены калории: {filled_kcal}")
        self.stdout.write(f"  проставлено макро:   {filled_macro}")
        self.stdout.write(f"  нет в OFF:           {not_found}")
        self.stdout.write(f"  в OFF без КБЖУ:      {no_data}  → остаются платной починке")
        self.stdout.write(f"  не удалось спросить: {failed}  → повторный прогон возьмёт их снова")
        if not apply:
            self.stdout.write(self.style.WARNING("Ничего не записано: это показ. Повторить с --apply."))
