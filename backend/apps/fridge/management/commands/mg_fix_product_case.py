"""MG_CANONCASE2: привести регистр названий в каталоге к виду «Лук репчатый».

Названия машинных записей (`source=auto`) заводит канонизация ингредиентов, а
модель охотно отвечает Title Case: «Сушеная Травка», «Сыр Чеддер». В коде это
починили 26 августа (`_sentence_case`), но починка коснулась только новых
названий — уже лежавшие в каталоге остались как были.

Команда правит лежащее. Правило регистра берётся из самой канонизации, чтобы
разовая правка и ежедневная работа не разошлись: импортируется `_sentence_case`,
а не переписывается здесь заново.

Два случая разведены намеренно.

* **Переименование** — новое имя в каталоге свободно. Просто правится `name`.
* **Столкновение** — под новым именем в каталоге уже есть живой продукт.
  Переименовать тут нельзя: у `Product.name` нет unique-ограничения, и база
  молча получит две одинаковые строки — это хуже разнобоя в регистре. Такие
  сливаются через `merge_product_into`: ссылки холодильника, меню, списка
  покупок и рецептов переезжают на выжившую запись. Синоним при этом не
  заводится, и правильно: имена различались только регистром, а поиск по
  синонимам и так регистронезависим. Слияние удаляет запись, поэтому включается
  отдельным ключом `--merge`, а не заодно с `--apply`.

Что считать столкновением — здесь единственное неочевидное место, и первая
версия ошиблась в нём на проде. Она считала занятым любое совпадение имени и
собралась слить четыре сыра в записи из выгрузки OpenFoodFacts: «Сыр пармезан»
со штрих-кодом, без категории и КБЖУ, с нулём ссылок. А у машинных записей, что
уехали бы в них, было 9 и 8 связей рецептов, холодильник и три позиции в списке
покупок — и все они переехали бы на записи, скрытые из подборщиков
(`visibility.HIDDEN_FROM_PICKERS`): сыры пропали бы из выбора продукта и из
подбора ингредиентов.

Поэтому имя занимают только записи из ОБЩЕГО каталога и видимые в подборщиках.
Штрих-кодные (`retail`, `off_bulk`) и догадки модели по коду (`ai`) опознаются
по коду, а не по названию, в списках их нет — имени они не занимают, и
одноимённая запись рядом с ними никому не мешает. Продукты семьи — тоже своё
пространство имён: чужой каталог им не указ. Такие соседи в отчёте показываются
отдельной строкой, чтобы решение было видно, а не подразумевалось.

Если живых претендентов на имя больше одного — пара пропускается и печатается в
отчёте: разбирать такое механически нельзя.

По умолчанию — dry-run, полный список без сокращений.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.dedup import merge_product_into
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS
from apps.recipes.recipe_products import _sentence_case


def _rivals(product, name):
    """Записи, которые действительно занимают имя. См. шапку файла."""
    return list(
        Product.objects.filter(name=name, owner_family__isnull=True)
        .exclude(id=product.id)
        .exclude(source__in=HIDDEN_FROM_PICKERS)[:2]
    )


def _same_name(product, name):
    """Все одноимённые соседи — и те, кто имя занимает, и те, кто нет."""
    return list(Product.objects.filter(name=name).exclude(id=product.id))


def plan(source):
    """-> (переименования, слияния, пропуски). Ничего не меняет."""
    rows = Product.objects.filter(owner_family__isnull=True)
    if source != "all":
        rows = rows.filter(source=source)
    rows = [p for p in rows.order_by("name") if p.name != _sentence_case(p.name)]

    renames, merges, skipped = [], [], []
    for p in rows:
        target = _sentence_case(p.name)
        rivals = _rivals(p, target)
        twins = [t for t in _same_name(p, target) if t.id not in {r.id for r in rivals}]
        if not rivals:
            renames.append((p, target, twins))
        elif len(rivals) == 1:
            merges.append((p, rivals[0]))
        else:
            skipped.append((p, target))
    return renames, merges, skipped


class Command(BaseCommand):
    help = "Привести регистр названий продуктов к виду каталога. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Переименовать (иначе только показать).")
        parser.add_argument(
            "--merge",
            action="store_true",
            help="Вместе с --apply: слить записи, чьё новое имя уже занято (удаляет дубль).",
        )
        parser.add_argument("--source", default="auto", help="auto (по умолчанию), manual, import… или all.")

    def handle(self, *args, **opts):
        source, apply_, merge = opts["source"], opts["apply"], opts["merge"]
        renames, merges, skipped = plan(source)

        total = Product.objects.filter(owner_family__isnull=True)
        if source != "all":
            total = total.filter(source=source)
        self.stdout.write("Продуктов source=%s всего: %d" % (source, total.count()))

        self.stdout.write("")
        self.stdout.write("Переименовать — %d:" % len(renames))
        for p, target, twins in renames:
            self.stdout.write("  %6d  %r -> %r" % (p.id, p.name, target))
            for t in twins:
                # Сосед, который имени не занимает. Печатается, чтобы решение
                # было видно глазами: именно на этом месте команда ошибалась.
                where = "семья %s" % t.owner_family_id if t.owner_family_id else "source=%s" % t.source
                self.stdout.write("            рядом уже есть %d %r (%s) — имени не занимает" % (t.id, t.name, where))

        self.stdout.write("")
        self.stdout.write("Слить с существующей записью — %d:" % len(merges))
        for p, canon in merges:
            self.stdout.write("  %6d  %r -> в %d %r" % (p.id, p.name, canon.id, canon.name))

        if skipped:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Пропущено (имя занято неоднозначно) — %d:" % len(skipped)))
            for p, target in skipped:
                self.stdout.write("  %6d  %r -> %r" % (p.id, p.name, target))

        self.stdout.write("")
        if not apply_:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: переименований %d, слияний %d. Повторите с --apply%s."
                    % (len(renames), len(merges), " --merge" if merges else "")
                )
            )
            return

        with transaction.atomic():
            for p, target, _twins in renames:
                Product.objects.filter(id=p.id).update(name=target)
            self.stdout.write(self.style.SUCCESS("Переименовано: %d" % len(renames)))

            if not merge:
                if merges:
                    self.stdout.write(self.style.WARNING("Слияния не тронуты — %d. Добавьте --merge." % len(merges)))
                return

            moved = 0
            for p, canon in merges:
                stats = merge_product_into(p, canon)
                links = sum(v for k, v in stats.items() if k != "kbju")
                moved += links
                self.stdout.write(
                    "  слито %d %r -> %d %r, ссылок перенесено: %d" % (p.id, p.name, canon.id, canon.name, links)
                )
            self.stdout.write(self.style.SUCCESS("Слито записей: %d, ссылок перенесено: %d" % (len(merges), moved)))
