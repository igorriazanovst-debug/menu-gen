"""MG_CATFIX: разложить по рубрикам то, что осело в «Прочем».

Половина каталога лежит в «Прочем»: 598 записей из 1204 на dev, и 593 из них
используются в рецептах. В списке покупок это видно прямо — «Кальмар»,
«Гребешки», «Бекон сырокопчёный», «Зелёное яблоко», «Крахмал», «Кунжут»,
«Грецкий орех» стоят одной кучей под заголовком «Прочее». Это не мусор, а
нормальные продукты без проставленной рубрики, и чинить тут нечего, кроме
самой рубрики.

Почему моделью, а не правилами. Рубрику задаёт смысл слова, а не его форма:
«Кальмар» — рыба и морепродукты, «Эритрит» — сладости, «Паста для том ям» —
соусы. Список из шестисот названий по правилам не разложить, а ошибка здесь
дёшева и обратима: рубрика меняется одним UPDATE и ничего не удаляет.

Что команда НЕ делает: не переименовывает и не сливает записи. Падежи и
опечатки («Тимьяна», «Лавровых листа», «Чипссы») разбирает dedup_products_ai —
у каждой команды своё дело. Эта только проставляет рубрику, в том числе и
записям с кривыми именами: «Тимьяна» в приправах лучше, чем «Тимьяна» в куче.

Разбирается только общий каталог, видимый в подборщиках: справочник штрих-кодов
(32 тысячи упаковок) скрыт, его рубрики никто не видит, а каждая пачка — платный
запрос.

Потерянные пачки не отменяют запись — в отличие от слияния, где то же правило
остаётся в силе. Строгость отвечает цене ошибки: слияние необратимо, а рубрика
меняется одним UPDATE, и целью команда берёт только записи из «Прочего» — значит
недоразобранные сами станут целью следующего запуска. Сколько их, команда
говорит вслух: «разложено 539» без этого числа читалось бы как «остальное и не
нуждалось».

Потерянные пачки сперва переспрашиваются меньшими порциями: шлюз рвёт связь тем
охотнее, чем длиннее ответ.

По умолчанию — DRY-RUN.

    docker compose exec -T backend python manage.py mg_fix_categories --limit 100
    docker compose exec -T backend python manage.py mg_fix_categories
    docker compose exec -T backend python manage.py mg_fix_categories --apply
"""

import json
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.common.ai_provider import complete_with_retry
from apps.common.progress import BatchProgress
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS

SYSTEM = (
    "Тебе дан JSON-массив объектов {i, name} — названия продуктов питания из "
    "каталога. Для каждого верни JSON-массив объектов {i, slug}: slug — ОДНА "
    "рубрика строго из списка ниже. Если название не подходит ни под одну "
    "рубрику или это вообще не еда — верни slug='other'. Не придумывай рубрик "
    "вне списка. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений.\n"
    "Названия бывают в падеже или с опечаткой («Тимьяна», «Лавровых листа», "
    "«Чипссы») — рубрику всё равно определяй по смыслу слова.\n"
    # MG_NUTSCAT: без этой строки модель на пробной сотне отправила в sweets
    # девять записей подряд — «Орехи», «Миндаль», «Арахис», «Фисташки»,
    # «Фундук», «Кедровые орешки». Рубрики nuts тогда ещё не было, и она брала
    # ближайшую; теперь есть, но подсказать надо: орехи сладкие на вкус, и без
    # указания соблазн отнести их к сладостям остаётся.
    "Орехи, семечки и сухофрукты — рубрика nuts, даже если они сладкие на вкус.\n"
    # Там же разъехались сахарозаменители: «Подсластитель» и «Эритрит» ушли в
    # sweets, а «Стевия» — в condiments. Это один и тот же товар по назначению.
    "Сахарозаменители (стевия, эритрит, подсластитель) — рубрика sweets.\n"
    # MG_CATREADY: готовая еда — то, что покупают приготовленным: «Говяжий язык
    # отварной», «Куриная грудка гриль», «Готовое пюре».
    "Блюда и полуфабрикаты, которые покупают уже приготовленными (отварной язык, "
    "грудка гриль, готовое пюре, бульон) — рубрика ready.\n"
    "Список рубрик: __LISTING__"
)


def targets(limit=0, recheck=()):
    """Записи каталога без рубрики или в «Прочем».

    MG_CATRECHECK: `recheck` добавляет к ним записи из названных рубрик. Нужно,
    когда правило раскладки поменялось: разложенное командой уже не в «Прочем»,
    и без этого пересмотреть его нечем. Пересмотр платный, поэтому рубрики
    называются поимённо, а не «всё подряд».
    """
    where = Q(category_fk__slug="other") | Q(category_fk__isnull=True)
    if recheck:
        where |= Q(category_fk__slug__in=list(recheck))
    qs = (
        Product.objects.filter(where)
        .filter(owner_family__isnull=True)
        .exclude(source__in=HIDDEN_FROM_PICKERS)
        .order_by("id")
    )
    return list(qs[:limit] if limit > 0 else qs)


class Command(BaseCommand):
    help = "MG_CATFIX: проставить рубрики записям каталога из «Прочего». По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать рубрики (иначе только показать).")
        parser.add_argument("--limit", type=int, default=0, help="Разобрать не более N записей (0 = все).")
        parser.add_argument("--batch", type=int, default=25, help="Размер пачки для запроса к модели.")
        parser.add_argument("--show", type=int, default=60, help="Сколько строк плана показать.")
        parser.add_argument(
            "--recheck",
            default="",
            help="MG_CATRECHECK: пересмотреть и записи из этих рубрик, через запятую (напр. vegetables,meat).",
        )

    def _say(self, line):
        """Строка хода: печатаем сразу, иначе в докере она повиснет в буфере."""
        self.stdout.write(line)
        self.stdout.flush()

    def handle(self, *args, **opts):
        from apps.recipes.recipe_products import _allowed_categories

        apply_ = opts["apply"]
        batch = max(1, opts["batch"])
        show = opts["show"]

        cats = [(slug, ru, cid) for slug, ru, cid in _allowed_categories()]
        cat_id_by_slug = {slug: cid for slug, _ru, cid in cats}
        ru_by_slug = {slug: ru for slug, ru, _cid in cats}
        listing = ", ".join("%s (%s)" % (s, ru) for s, ru, _ in cats)
        system = SYSTEM.replace("__LISTING__", listing)

        try:
            from apps.common.ai_provider import check_batch_ai_available, get_batch_ai_client

            client = get_batch_ai_client()
            # MG_PROGRESS: до этой строки команда молчала, а проверка с тремя
            # попытками и таймаутом в две минуты может думать долго. Молчание в
            # начале читается как зависание ровно так же, как молчание в середине.
            self._say("Проверяю провайдера…")
            check_batch_ai_available(log=self._say)
            self._say("Провайдер отвечает.")
        except Exception as exc:
            self.stderr.write(self.style.ERROR("ИИ-провайдер недоступен: %s" % exc))
            self.stderr.write(self.style.ERROR("Проверить настройки: manage.py mg_ai_ping"))
            return

        try:
            from apps.fridge.services import _parse_json_loose
        except Exception:
            self.stderr.write(self.style.ERROR("Парсер JSON недоступен (_parse_json_loose)."))
            return

        recheck = tuple(x.strip() for x in opts["recheck"].split(",") if x.strip())
        unknown = [x for x in recheck if x not in cat_id_by_slug]
        if unknown:
            self.stderr.write(self.style.ERROR("Неизвестные рубрики в --recheck: %s" % ", ".join(unknown)))
            return
        if recheck:
            self.stdout.write("Пересматриваем также рубрики: %s" % ", ".join(recheck))

        rows = targets(opts["limit"], recheck)
        self.stdout.write("Записей к разбору: %d (пачка=%d)." % (len(rows), batch))
        if not rows:
            return

        decided = {}  # product_id -> slug, когда рубрика найдена
        # «Ответ получен» и «рубрика найдена» — разные вещи: на «other» модель
        # ответила, и переспрашивать её во втором проходе значит платить дважды
        # за один и тот же ответ.
        answered = set()

        def sweep(items, size, label):
            """Один проход по списку. Возвращает число потерянных пачек."""
            lost = 0
            nchunks = (len(items) + size - 1) // size
            self._say("%s: записей %d, пачка %d" % (label, len(items), size))
            progress = BatchProgress(len(items), nchunks, self._say)
            for base in range(0, len(items), size):
                grp = items[base : base + size]
                payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
                try:
                    raw = complete_with_retry(
                        client, log=self._say, prompt=payload, system=system, max_tokens=3000, temperature=0.0
                    )
                    data = _parse_json_loose(raw)
                except Exception as exc:
                    self.stderr.write(self.style.WARNING("  пачка %d: ошибка ИИ: %s" % (base // size + 1, exc)))
                    lost += 1
                    progress.chunk_done(failed=True)
                    continue
                if not isinstance(data, list):
                    lost += 1
                    progress.chunk_done(failed=True)
                    continue
                taken = 0
                for d in data:
                    if not isinstance(d, dict) or "i" not in d:
                        continue
                    try:
                        j = int(d["i"])
                    except (TypeError, ValueError):
                        continue
                    if not (0 <= j < len(grp)):
                        continue
                    slug = (d.get("slug") or "").strip()
                    answered.add(grp[j].id)
                    # Рубрика вне списка — ответ модели, а не решение: пропускаем.
                    if slug and slug != "other" and slug in cat_id_by_slug:
                        decided[grp[j].id] = slug
                        taken += 1
                progress.chunk_done(items=taken)
            progress.finish()
            return lost

        lost = sweep(rows, batch, "Проход 1")
        pending = [p for p in rows if p.id not in answered]

        # MG_AISWEEP2: второй проход меньшими пачками. Шлюз рвёт соединение тем
        # охотнее, чем длиннее ответ, — на проде из 24 пачек по 25 названий две
        # потерялись целиком. Сдаваться на этом рано: та же работа пачками по
        # десять обычно доходит, а стоит она столько же.
        if lost and pending:
            small = max(5, batch // 3)
            self._say("")
            sweep(pending, small, "Проход 2 (меньшими пачками)")
            pending = [p for p in rows if p.id not in answered]

        # При пересмотре модель часто подтверждает нынешнюю рубрику. Такие
        # записи в плане только мешают читать: показывать надо то, что меняется.
        now = {p.id: (p.category_fk.slug if p.category_fk_id else "") for p in rows}
        plan = [(p, decided[p.id]) for p in rows if p.id in decided and decided[p.id] != now.get(p.id)]
        failed = len(pending)

        by_slug = Counter(slug for _p, slug in plan)
        self.stdout.write("")
        self.stdout.write("Разложить по рубрикам — %d:" % len(plan))
        for slug, n in by_slug.most_common():
            self.stdout.write("   %-14s %-22s %d" % (slug, ru_by_slug.get(slug, ""), n))

        self.stdout.write("")
        for p, slug in plan[:show]:
            self.stdout.write("   %-8s %-40s → %s" % (p.id, p.name[:40], ru_by_slug.get(slug, slug)))
        if len(plan) > show:
            self.stdout.write("   ... скрыто ещё %d" % (len(plan) - show))

        no_rubric = len(rows) - len(plan) - failed
        self.stdout.write("")
        self.stdout.write("Остаётся в «Прочем» — %d: модель рубрики не нашла." % no_rubric)

        # MG_CATPARTIAL: недоразобранное НЕ отменяет запись — в отличие от
        # слияния, где то же правило остаётся в силе.
        #
        # Строгость должна отвечать цене ошибки. Слияние необратимо: оно
        # удаляет записи и переносит ссылки, и решать по неполному плану там
        # нельзя. Простановка рубрики обратима одним UPDATE, и команда вдобавок
        # идемпотентна — целью она берёт только записи из «Прочего», поэтому
        # недоразобранные сами станут целью следующего запуска.
        #
        # На проде первое правило обошлось так: 14 минут работы и оплаченные
        # запросы, две потерянные пачки из 24 — и в базу не легло ни одной из
        # 539 верных рубрик. Отказ стоил дороже, чем частичная запись.
        if failed:
            self.stderr.write(
                self.style.WARNING(
                    "Не разобрано записей: %d — их в плане выше НЕТ. "
                    "Запустите команду ещё раз: целью она возьмёт как раз их." % failed
                )
            )

        if not apply_:
            self.stdout.write("")
            self.stdout.write("DRY-RUN. Ничего не изменено. Записать: --apply")
            return

        with transaction.atomic():
            for p, slug in plan:
                Product.objects.filter(id=p.id).update(category_fk_id=cat_id_by_slug[slug])

        self.stdout.write("")
        self.stdout.write("Рубрик проставлено: %d" % len(plan))
