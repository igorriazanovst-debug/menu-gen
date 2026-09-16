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
флагом --apply.

MG_DEDUPLIMIT: пробной партией эту команду проверить нельзя, и это не мелочь.
Рубрика решается для каждой записи отдельно — там срез честен. Дубль решается
ПАРОЙ: ответ зависит от того, видны ли обе записи разом. Срез по id пары рвёт.
На проде --limit 200 не нашёл среди яиц ни одного дубля: «Яйца куриные» (41) и
«Яичный белок» (197) в срез попали, а «Белок» (1018) и «Яцо» (2034) — нет, и
пустой план прочитался как «дублей нет». Поэтому --limit остаётся только для
оценки стоимости и всегда печатает предупреждение.

MG_DEDUPSURVIVOR: выжившим становится не любой участник группы. Имя выжившего
переезжает во все ссылки и во все списки покупок, а слияние необратимо, поэтому
на эту роль есть допуск (can_survive), а не только предпочтение. Группа, в
которой допущенных нет, целиком пропускается и печатается отдельным списком.

    docker compose exec -T backend python manage.py dedup_products_ai
    docker compose exec -T backend python manage.py dedup_products_ai --apply
"""

import json
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.common.ai_provider import complete_with_retry
from apps.common.progress import BatchProgress
from apps.fridge.aliases import normalize_alias
from apps.fridge.dedup import has_kbju, merge_product_into
from apps.fridge.management.commands.dedup_products import qualifier
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS
from apps.recipes.ingredient_noise import is_ingredient_fragment
from apps.recipes.recipe_products import _sentence_case

PICK_SYSTEM = (
    "Тебе дан JSON-массив объектов {i, names} — группы названий продуктов из "
    "каталога. Названия внутри группы означают ОДИН и тот же продукт, но "
    "записаны по-разному. Для каждой группы верни {i, best} — то из "
    "ПЕРЕЧИСЛЕННЫХ названий, которое годится как название каталога: "
    "именительный падеж, единственное или обычное для продукта число, без "
    "опечаток, без количества, без примечаний вроде «для жарки». Отвечай "
    "ТОЛЬКО названием, дословно взятым из своего же списка names. Если ни одно "
    "не годится или названия в группе означают разные продукты — best=null. "
    "Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)

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


def can_survive(p, key):
    """MG_DEDUPSURVIVOR: годится ли имя на роль выжившего.

    Имя выжившего уезжает во все ссылки группы и во все списки покупок, а
    слияние необратимо. Поэтому это не предпочтение, а допуск: не прошедшая
    запись не выигрывает никогда, даже если в группе она одна такая.

    Два условия.

    Имя не обрывок. is_ingredient_fragment ловит и примечание, и количество:
    «Масла для жарки», «Яйца – 1 шт. с1». Без этого на проде в плане стояли
    «Масла для обжарки» -> «Масла для жарки» и «Яйца – 1шт» -> «Яйца – 1 шт.
    с1» — мусор, переезжающий в мусор, только с чужими ссылками в придачу.

    Имя совпадает с канон-формой от ИИ. Канон — та самая форма, к которой
    модель сводила группу: именительный падеж, без опечаток. Проверка имени на
    падеж или на опечатку механически ненадёжна, а это сравнение даёт ровно то
    же даром. На проде без него выживали «Сушеного молотого имбиря»,
    «Консервированного горошка», «Лимонный ок» (канон — «Лимонный сок»),
    «Подсолнечное» (канон — «Подсолнечное масло») и «Черри» (канон — «Томаты
    черри»): ни одно из них каноном не было, и выбор скатывался к min(id).

    Если в группе такого имени нет — сливать не во что, и группа пропускается
    целиком. Пропущенное слияние видно в следующем dry-run, неверное — нет.
    """
    if is_ingredient_fragment(p.name):
        return False
    return normalize_alias(p.name) == key


def _survivor_rank(p):
    """Лучший среди допущенных: сид-продукт, КБЖУ, написание, id.

    Все допущенные уже несут канон-форму имени (см. can_survive), поэтому здесь
    сравнивается остальное: курируемая запись лучше авто-созданной, запись с
    КБЖУ лучше пустой, «Зелёный лук» лучше, чем «зеленый лук».
    """
    return (
        0 if p.is_seed else 1,
        0 if has_kbju(p) else 1,
        0 if p.name == _sentence_case(p.name) else 1,
        p.id,
    )


class Command(BaseCommand):
    help = "GPT-дедуп: схлопнуть варианты названий (порядок слов/сокращения/опечатки). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить слияние (иначе только план).")
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Обработать не более N продуктов (0 = все). ВНИМАНИЕ: срез рвёт пары, см. предупреждение.",
        )
        parser.add_argument("--batch", type=int, default=20, help="Размер чанка для запроса к AI.")
        parser.add_argument("--show", type=int, default=40, help="Сколько групп показать в плане.")
        parser.add_argument(
            "--no-resolve",
            action="store_true",
            help="MG_DEDUPPICK: не спрашивать модель про группы без годного имени — просто пропустить их.",
        )

    def _say(self, line):
        """Строка хода: печатаем сразу, иначе в докере она повиснет в буфере."""
        self.stdout.write(line)
        self.stdout.flush()

    def _resolve_homeless(self, client, parse_json, homeless, size=10):
        """MG_DEDUPPICK: спросить модель, какое из имён группы годится в каталог.

        Правило допуска (can_survive) требует, чтобы имя выжившего совпадало с
        канон-формой. Оно спасает от опечаток и падежей, но у него есть своя
        цена: канон приходит в единственном числе («яйцо», «огурец»), а в
        каталоге законно лежит множественное («Яйца», «Огурцы»). Совпадения
        нет ни у одного имени — и такая группа пропускается КАЖДЫЙ раз, сколько
        ни запускай. В списке покупок это ровно то, с чего всё началось: восемь
        строк про яйца, среди них «Яцо» и «Огурцs».

        Здесь группа показывается модели целиком, и та выбирает имя из готовых.
        Запрос короткий, групп десятки, а не тысячи. Автоматической проверки за
        этим выбором нет — только запрет на имя-обрывок, — поэтому в плане эти
        группы печатаются отдельным разделом.

        Возвращает (слияния, отказы модели, не дошедшие до модели).
        """
        picked, refused, lost = self._pick_pass(client, parse_json, homeless, size, "Разбор пропущенных групп")

        # MG_AISWEEP2, тот же случай, что в основном проходе: потерянная пачка
        # — это не ответ модели, а обрыв по дороге, и меньшей пачкой та же
        # работа обычно доходит. Без второй попытки на dev так и вышло: в
        # «пропущено» встали десять групп («Креветки», «Бананы», «Баклажаны»),
        # которых модель вообще не видела, — и читались они наравне с честными
        # отказами.
        if lost:
            p2, r2, lost = self._pick_pass(client, parse_json, lost, max(3, size // 3), "Разбор групп: вторая попытка")
            picked.extend(p2)
            refused.extend(r2)
        return picked, refused, lost

    def _pick_pass(self, client, parse_json, homeless, size, label):
        """Один проход выбора имени. Возвращает (слияния, отказы, потерянные)."""
        picked, refused, lost = [], [], []
        nchunks = (len(homeless) + size - 1) // size
        self._say("")
        self._say("%s: %d, пачка %d" % (label, len(homeless), size))
        progress = BatchProgress(len(homeless), nchunks, self._say)
        for base in range(0, len(homeless), size):
            grp = homeless[base : base + size]
            payload = json.dumps(
                [{"i": i, "names": [p.name for p in members]} for i, (_key, members) in enumerate(grp)],
                ensure_ascii=False,
            )
            try:
                raw = complete_with_retry(
                    client, log=self._say, prompt=payload, system=PICK_SYSTEM, max_tokens=2000, temperature=0.0
                )
                data = parse_json(raw)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"  пачка {base // size + 1}: ошибка AI: {e}"))
                lost.extend(grp)
                progress.chunk_done(failed=True)
                continue
            if not isinstance(data, list):
                lost.extend(grp)
                progress.chunk_done(failed=True)
                continue

            best = {}
            for d in data:
                if not isinstance(d, dict) or "i" not in d:
                    continue
                try:
                    j = int(d["i"])
                except (TypeError, ValueError):
                    continue
                if 0 <= j < len(grp) and isinstance(d.get("best"), str):
                    best[j] = d["best"].strip()

            taken = 0
            for j, (_key, members) in enumerate(grp):
                name = best.get(j)
                # Модель могла ответить null («названия про разные продукты»),
                # сочинить имя, которого в группе нет, или выбрать обрывок.
                # Любой из этих случаев — не решение, и группа остаётся нерешённой.
                fit = [p for p in members if p.name == name and not is_ingredient_fragment(p.name)]
                if not fit:
                    refused.append((_key, members))
                    continue
                survivor = min(fit, key=_survivor_rank)
                dups = [p for p in members if p.id != survivor.id]
                if dups:
                    picked.append((survivor, dups))
                taken += 1
            progress.chunk_done(items=taken)
        progress.finish()
        return picked, refused, lost

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        batch = max(1, opts["batch"])
        show = opts["show"]

        try:
            from apps.common.ai_provider import get_batch_ai_client

            # MG_AIBATCH: пакетный клиент — своя модель и свой таймаут. С
            # обычным (30 с) на проде отваливалась половина пачек.
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

        # MG_DEDUPSCOPE: разбираем только общий каталог. Product.objects.all()
        # — это ещё и 32 тысячи упаковок из справочника штрих-кодов: они скрыты
        # из подборщиков, сливать в них нельзя, а каждая пачка — платный запрос.
        products = list(
            Product.objects.filter(owner_family__isnull=True).exclude(source__in=HIDDEN_FROM_PICKERS).order_by("id")
        )
        if limit > 0:
            products = products[:limit]
            # MG_DEDUPLIMIT: предупреждение обязательно. Рубрика решается для
            # каждой записи отдельно, и срез там честен. Дубль решается ПАРОЙ:
            # ответ зависит от того, видны ли обе записи разом. Срез по id пары
            # рвёт — «Яйца куриные» (41) и «Яичный белок» (197) в первые 200
            # попадают, а «Белок» (1018) и «Яцо» (2034) нет, — и команда выдаёт
            # пустой план, который читается как «дублей нет».
            self.stderr.write(
                self.style.WARNING(
                    "--limit взял первые %d записей по id. Дубли, у которых пара осталась за срезом, "
                    "НЕ найдутся: «дублей нет» здесь означает «не в этом срезе». "
                    "Для настоящего разбора запускайте без --limit." % limit
                )
            )
        self.stdout.write(f"Продуктов к анализу: {len(products)} (batch={batch}).")

        # product_id -> канон-ключ (нормализованный канон от AI)
        canon_key = {}
        answered = set()

        def sweep(items, size, label):
            """Один проход. Возвращает число потерянных пачек."""
            lost = 0
            nchunks = (len(items) + size - 1) // size
            self._say("%s: записей %d, пачка %d" % (label, len(items), size))
            progress = BatchProgress(len(items), nchunks, self._say)
            for base in range(0, len(items), size):
                grp = items[base : base + size]
                payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
                try:
                    raw = complete_with_retry(
                        client, log=self._say, prompt=payload, system=SYSTEM, max_tokens=3000, temperature=0.0
                    )
                    data = _parse_json_loose(raw)
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"  пачка {base // size + 1}: ошибка AI: {e}"))
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
                    answered.add(grp[j].id)
                    canon = d.get("canon")
                    key = normalize_alias(canon) if isinstance(canon, str) else ""
                    if key:
                        canon_key[grp[j].id] = key
                        taken += 1
                progress.chunk_done(items=taken)
            progress.finish()
            return lost

        lost = sweep(products, batch, "Проход 1")
        pending = [p for p in products if p.id not in answered]

        # MG_AISWEEP2: то же, что в раскладке рубрик. Шлюз рвёт связь тем охотнее,
        # чем длиннее ответ, и пачками поменьше та же работа обычно доходит.
        # Здесь второй проход важнее: слияние необратимо, поэтому по неполному
        # разбору команда писать откажется — и без второго прохода единственным
        # выходом был бы сорокаминутный прогон заново.
        if lost and pending:
            small = max(5, batch // 3)
            self._say("")
            sweep(pending, small, "Проход 2 (меньшими пачками)")
            pending = [p for p in products if p.id not in answered]

        failed_chunks = 1 if pending else 0
        failed_items = len(pending)

        # Группируем по канон-ключу и уточнению в скобках. MG_DEDUPBRACKET:
        # скобка разводит записи и здесь, по той же причине, что в
        # детерминированном дедупе, — «Курица (филе)» не тот же товар, что
        # «Курица», а модель сводила их к одному канону и предлагала слить
        # «Куриное филе» в «Курица (филе)».
        pmap = {p.id: p for p in products}
        groups = defaultdict(list)
        for pid, key in canon_key.items():
            p = pmap[pid]
            groups[(key, qualifier(p.name))].append(p)

        # оставляем только реальные группы (>=2 разных продукта)
        merges = []  # (survivor, [dups])
        homeless = []  # (канон, участники) — сливать не во что
        for (key, _q), members in sorted(groups.items()):
            if len(members) < 2:
                continue
            fit = [p for p in members if can_survive(p, key)]
            if not fit:
                homeless.append((key, members))
                continue
            survivor = min(fit, key=_survivor_rank)
            dups = [p for p in members if p.id != survivor.id]
            if dups:
                merges.append((survivor, dups))

        picked = []  # (survivor, [dups]) — выживший выбран вторым вопросом
        unseen = []  # группы, до которых модель не дошла: это не отказ
        if homeless and not opts["no_resolve"]:
            picked, homeless, unseen = self._resolve_homeless(client, _parse_json_loose, homeless)

        all_merges = merges + picked
        total_dups = sum(len(d) for _, d in all_merges)
        self.stdout.write(f"Групп со слиянием: {len(all_merges)}; дублей к удалению: {total_dups}.")
        for survivor, dups in merges[:show]:
            # id обязательны: в каталоге встречаются две записи с одинаковым
            # именем, и без id такая строка читается как «само в себя».
            names = ", ".join(f"«{d.name}» (#{d.id})" for d in dups)
            self.stdout.write(f"  {names} -> «{survivor.name}» (#{survivor.id})")
        if len(merges) > show:
            self.stdout.write(f"  … и ещё {len(merges) - show} групп")

        # MG_DEDUPPICK: эти строки печатаются отдельно не для красоты. В них
        # выжившего выбрала модель из готовых имён, а не правило: автоматической
        # проверки за этим выбором нет, кроме запрета на имя-обрывок. Читать их
        # надо внимательнее остальных.
        if picked:
            self.stdout.write("")
            self.stdout.write("Разобрано вторым вопросом (имя выбрала модель) — групп: %d" % len(picked))
            for survivor, dups in picked[:show]:
                names = ", ".join(f"«{d.name}» (#{d.id})" for d in dups)
                self.stdout.write(f"  {names} -> «{survivor.name}» (#{survivor.id})")
            if len(picked) > show:
                self.stdout.write(f"  … и ещё {len(picked) - show} групп")

        # MG_DEDUPSURVIVOR: о пропущенных молчать нельзя — иначе «групп со
        # слиянием: N» читается как весь найденный дубляж, а часть его просто
        # некуда сливать. Эти группы разбираются руками или чистятся
        # mg_prune_auto_products, и в следующем прогоне вернутся сюда.
        if homeless:
            self.stdout.write("")
            self.stdout.write("Пропущено групп (годного имени в группе нет): %d" % len(homeless))
            for key, members in homeless[:show]:
                names = ", ".join(f"«{p.name}» (#{p.id})" for p in members)
                self.stdout.write(f"  канон «{key}»: {names}")
            if len(homeless) > show:
                self.stdout.write(f"  … и ещё {len(homeless) - show} групп")

        # «Не дошло до модели» и «модель отказалась» — разные исходы, и мешать
        # их в одном списке нельзя. На dev в «пропущено» стояло 13 групп, но
        # десять из них были целой потерянной пачкой («Креветки», «Бананы»,
        # «Баклажаны») — модель их не видела. Читалось это как её решение.
        if unseen:
            self.stdout.write("")
            self.stdout.write("До модели не дошло групп: %d — это не отказ, а обрыв связи." % len(unseen))
            for key, members in unseen[:show]:
                names = ", ".join(f"«{p.name}» (#{p.id})" for p in members)
                self.stdout.write(f"  канон «{key}»: {names}")
            if len(unseen) > show:
                self.stdout.write(f"  … и ещё {len(unseen) - show} групп")
            self.stdout.write("  Следующий прогон спросит про них снова.")

        # MG_AIBATCH: молчать о потерянных пачках нельзя. На проде команда при
        # пяти отвалившихся чанках из десяти напечатала «Групп со слиянием: 1»,
        # и это читалось как «дублей почти нет», хотя половина названий до
        # модели просто не доехала. Неполный разбор — не итог, а полуфабрикат:
        # слить по нему — значит принять решение, не посмотрев на данные.
        if failed_chunks:
            self.stdout.flush()
            self.stderr.write(self.style.ERROR("Не разобрано названий: %d — их в плане выше НЕТ." % failed_items))
            if apply:
                self.stderr.write(
                    self.style.ERROR("Слияние отменено: сначала добейтесь полного разбора, потом --apply.")
                )
                return

        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        fridge_moved = recipe_moved = shop_moved = kbju_filled = fields_filled = deleted = 0
        with transaction.atomic():
            for survivor, dups in all_merges:
                for dup in dups:
                    s = merge_product_into(dup, survivor)
                    fridge_moved += s["fridge"]
                    recipe_moved += s["recipe"]
                    shop_moved += s["shop"]
                    kbju_filled += s["kbju"]
                    fields_filled += s["fields"]
                    deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Слияние выполнено. Удалено дублей: {deleted}; перенесено ссылок — "
                f"холодильник: {fridge_moved}, рецепты: {recipe_moved}, покупки: {shop_moved}; "
                f"КБЖУ перенесено в канон: {kbju_filled}; "
                f"прочих полей дозаполнено: {fields_filled}."
            )
        )
