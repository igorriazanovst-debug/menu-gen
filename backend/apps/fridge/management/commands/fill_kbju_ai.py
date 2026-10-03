"""Заполнить КБЖУ продуктам без него через AI (длинный хвост из ингредиентов).

Берёт продукты с пустым nutrition и просит AI оценить КБЖУ на 100 г. Несъедобное
(бытовая химия, посуда, мусорные названия) AI помечает food=false — такие
пропускаем. Значения валидируются (правдоподобные диапазоны), иначе пропуск.

Безопасно: по умолчанию DRY-RUN (только показывает, ничего не пишет и не тратит
запись в БД); запись — флагом --apply. Идемпотентно (повторный запуск берёт
только то, что ещё без КБЖУ). --limit — обработать только N продуктов (удобно
для тестовой партии и контроля стоимости).

**DRY-RUN «сухой» для базы, но не для счёта.** Запросы к модели он делает ровно
те же, что и прогон с --apply: `--apply` управляет только записью результата.
Чтобы узнать объём, не потратив ничего, есть `--count-only` — он печатает число
и выходит, не касаясь провайдера. На этом уже попались: замер хвоста запустили
без --apply, считая его бесплатным.

MG_KBJUSCOPE: что команда НЕ берёт по умолчанию и почему.

* **Личные продукты людей** (`owner_family` заполнен) — никогда, даже с флагом.
  Это чужая запись, которую человек завёл сам; дописать в неё догадку модели
  молча — не наше дело. Человек правит её в «Моих продуктах» руками, и пустое
  поле там означает «неизвестно», а не «посчитай за меня».
* **Скрытые из выбора источники** (`ai`, `retail`, `off_bulk`) — только с
  `--include-hidden`. Это магазинные SKU: их десятки тысяч, в выборе продуктов
  они не показываются (видны лишь по сканированию штрихкода), а запрос к модели
  на каждую позицию стоит денег. Прогон по ним — отдельное осознанное решение,
  а не побочный эффект слова «все».

Отбор идёт запросом в базу, а не перебором в питоне: раньше команда тянула весь
каталог в память, чтобы выбросить из него почти всё.

    docker compose exec -T backend python manage.py fill_kbju_ai --count-only   # сколько, бесплатно
    docker compose exec -T backend python manage.py fill_kbju_ai --limit 50          # dry-run, 50 шт
    docker compose exec -T backend python manage.py fill_kbju_ai --limit 50 --apply

Весь хвост — длинный прогон, и его нельзя запускать через `exec`: тот умирает
вместе с сессией. Отдельным контейнером:

    docker compose run -d --name mg-kbju backend python manage.py fill_kbju_ai --apply
    docker logs -f mg-kbju
    docker rm mg-kbju            # только после того, как итог прочитан
"""

import json

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.common.ai_provider import complete_with_retry
from apps.common.progress import BatchProgress
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS  # MG_KBJUSCOPE

SYSTEM = (
    "Ты — нутрициолог. На вход дан JSON-массив объектов {i, name} — названия "
    "продуктов питания. Для каждого верни КБЖУ на 100 г съедобной части как "
    "JSON-массив объектов {i, kcal, protein, fat, carb}: kcal — целое число "
    "(ккал), protein/fat/carb — граммы (число, можно дробное). Если позиция НЕ "
    "еда (бытовая химия, посуда, упаковка, бессмысленное название) — верни "
    "{i, food: false}. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)


def _has_kbju(p):
    return isinstance(p.nutrition, dict) and len(p.nutrition) > 0


def _plausible(kcal, prot, fat, carb):
    """Грубая валидация: отсечь явный бред."""
    try:
        kcal = float(kcal)
        prot = float(prot)
        fat = float(fat)
        carb = float(carb)
    except (TypeError, ValueError):
        return None
    if not (0 <= kcal <= 1000):
        return None
    if not all(0 <= x <= 100 for x in (prot, fat, carb)):
        return None
    return round(kcal), round(prot, 1), round(fat, 1), round(carb, 1)


class Command(BaseCommand):
    help = "Заполнить КБЖУ продуктам без него через AI. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать результат (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N продуктов (0 = все).")
        parser.add_argument("--batch", type=int, default=20, help="Размер чанка для одного запроса к AI.")
        # MG_KBJUCOUNT: узнать объём, ничего не потратив.
        parser.add_argument(
            "--count-only",
            action="store_true",
            help="Только сказать, сколько позиций под прогон. К модели не обращается.",
        )
        # MG_KBJUSCOPE: магазинные SKU — отдельное решение, см. заголовок файла.
        parser.add_argument(
            "--include-hidden",
            action="store_true",
            help="Взять и скрытые из выбора источники (ai, retail, off_bulk) — десятки тысяч позиций.",
        )

    def _say(self, line):
        """Строка хода: печатаем сразу, иначе в докере она повиснет в буфере."""
        self.stdout.write(line)
        self.stdout.flush()

    def _targets(self, opts):
        """Кого обрабатывать. MG_KBJUSCOPE — границы описаны в заголовке файла.

        Отбор запросом в базу, а не перебором в питоне: раньше в память тянулся
        весь каталог, чтобы выбросить из него почти всё. Пустой nutrition — это
        `{}` либо NULL; та же проверка, что и в _has_kbju, только выраженная SQL.
        """
        qs = Product.objects.filter(owner_family__isnull=True).filter(Q(nutrition__isnull=True) | Q(nutrition={}))
        if not opts["include_hidden"]:
            qs = qs.exclude(source__in=HIDDEN_FROM_PICKERS)
        rows = list(qs.order_by("id"))
        limit = opts["limit"]
        return rows[:limit] if limit > 0 else rows

    def handle(self, *args, **opts):
        apply = opts["apply"]
        batch = max(1, opts["batch"])

        # MG_KBJUCOUNT: сначала считаем, потом тратим.
        #
        # Отбор и его число печатаются ДО провайдера, и с --count-only команда
        # на этом и заканчивается. Иначе узнать «сколько там позиций» было
        # нечем: прогон без --apply спрашивает модель на каждую пачку точно так
        # же, как с ним, и «сухой» он только для базы, а не для счёта. На этом
        # уже попались: замер хвоста запустили без --apply, считая его
        # бесплатным.
        targets = self._targets(opts)
        scope = "весь каталог" if opts["include_hidden"] else "видимый каталог (без магазинных SKU)"
        self.stdout.write(f"Продуктов без КБЖУ к обработке: {len(targets)} — {scope}, batch={batch}.")
        if opts["count_only"]:
            self.stdout.write("Только подсчёт: к модели не обращались, ничего не записано.")
            return
        if not targets:
            return

        try:
            from apps.common.ai_provider import get_batch_ai_client

            # MG_AIBATCH: пакетный клиент — своя модель и свой таймаут.
            client = get_batch_ai_client()
            # MG_AIPING: фабрика только собирает клиента и ловит пустой ключ.
            # Неверный ключ виден лишь по ответу сервиса — без запроса команда
            # уходила в прогон и ловила 401 на каждой пачке.
            from apps.common.ai_provider import check_batch_ai_available

            self._say("Проверяю провайдера…")
            check_batch_ai_available(log=self._say)
            self._say("Провайдер отвечает.")
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

        filled = not_food = failed = 0
        samples = []
        nchunks = (len(targets) + batch - 1) // batch

        # MG_PROGRESS: длинный прогон не должен выглядеть зависшим. Строка
        # хода общая со всеми пачечными командами — со временем и остатком.
        progress = BatchProgress(len(targets), nchunks, self._say)
        for base in range(0, len(targets), batch):
            grp = targets[base : base + batch]
            payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
            try:
                raw = complete_with_retry(
                    client, log=self._say, prompt=payload, system=SYSTEM, max_tokens=3000, temperature=0.0
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

            taken = 0
            by_i = {}
            for d in data:
                if isinstance(d, dict) and "i" in d:
                    try:
                        by_i[int(d["i"])] = d
                    except (TypeError, ValueError):
                        pass

            for idx, p in enumerate(grp):
                d = by_i.get(idx)
                if d is None:
                    failed += 1
                    continue
                if d.get("food") is False:
                    not_food += 1
                    continue
                vals = _plausible(d.get("kcal"), d.get("protein"), d.get("fat"), d.get("carb"))
                if vals is None:
                    failed += 1
                    continue
                kcal, prot, fat, carb = vals
                if apply:
                    p.calories_per_100g = kcal
                    p.nutrition = {"calories": kcal, "proteins": prot, "fats": fat, "carbs": carb}
                    p.save(update_fields=["calories_per_100g", "nutrition"])
                if len(samples) < 20:
                    samples.append(f"  {p.name}: {kcal} ккал / Б{prot} Ж{fat} У{carb}")
                filled += 1
                taken += 1
            progress.chunk_done(items=taken)

        progress.finish()

        for s in samples:
            self.stdout.write(s)
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Заполнено: {filled}; не еда (пропущено): {not_food}; " f"не удалось распознать: {failed}."
            )
        )
