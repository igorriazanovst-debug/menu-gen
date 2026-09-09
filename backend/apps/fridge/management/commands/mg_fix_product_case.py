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
* **Столкновение** — под новым именем продукт уже есть: «Сыр Пармезан» и «Сыр
  пармезан» лежат рядом. Переименовать тут нельзя: у `Product.name` нет
  unique-ограничения, и база молча получит две одинаковые строки — это хуже
  разнобоя в регистре. Такие сливаются через `merge_product_into`: ссылки
  холодильника, меню, списка покупок и рецептов переезжают на выжившую запись.
  Синоним при этом не заводится, и правильно: имена различались только
  регистром, а поиск по синонимам и так регистронезависим. Слияние удаляет
  запись, поэтому включается отдельным ключом `--merge`, а не заодно с
  `--apply`.

Канон при слиянии выбирается по одному правилу: он должен быть единственным и
общим (`owner_family IS NULL`). Если под новым именем нашлось несколько записей
или чужая семейная — пара пропускается и печатается в отчёте: разбирать такое
механически нельзя.

По умолчанию — dry-run, полный список без сокращений.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.dedup import merge_product_into
from apps.fridge.models import Product
from apps.recipes.recipe_products import _sentence_case


def plan(source):
    """-> (переименования, слияния, пропуски). Ничего не меняет."""
    rows = Product.objects.filter(owner_family__isnull=True)
    if source != "all":
        rows = rows.filter(source=source)
    rows = [p for p in rows.order_by("name") if p.name != _sentence_case(p.name)]

    renames, merges, skipped = [], [], []
    for p in rows:
        target = _sentence_case(p.name)
        others = list(Product.objects.filter(name=target).exclude(id=p.id)[:2])
        if not others:
            renames.append((p, target))
        elif len(others) == 1 and others[0].owner_family_id is None:
            merges.append((p, others[0]))
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
        for p, target in renames:
            self.stdout.write("  %6d  %r -> %r" % (p.id, p.name, target))

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
            for p, target in renames:
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
