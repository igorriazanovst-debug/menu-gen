"""MG_MERGEMANUAL: слить названные записи каталога руками.

Автоматика добирает не всё, и остаток — не редкость, а норма. Детерминированный
дедуп ловит формы слова, ИИ-дедуп — перестановки и опечатки внутри группы, но
одинокая кривая запись группы не образует: «Лука» (родительный падеж) живёт в
каталоге одна, канон у неё «лук», а записи «Лук» нет вовсе — есть «Лук
репчатый». Ни одно правило такую пару не сведёт, а в списке покупок она даёт
лишнюю строку «Лука — 60.00 г».

Решение здесь человеческое: он смотрит на список и говорит, что куда. Команда
делает ровно то, что ей сказали, и ничего не решает сама — но показывает, что
именно переедет, и по умолчанию не пишет.

    docker compose exec -T backend python manage.py mg_merge_products 144 1802
    docker compose exec -T backend python manage.py mg_merge_products 144 1802 --apply

Первый номер — канон (он останется), остальные — дубли (их удалят, а ссылки
переедут на канон). Поля, которых у канона нет, он заберёт у дубля: рубрику,
КБЖУ, картинку, срок хранения (MG_MERGEKEEP).

MG_MERGERENAME: бывает, что годного имени нет ни у одной записи группы. «Агара»
и «Агар агара» — правильного «Агар-агар» в каталоге нет вовсе, и слияние без
переименования оставило бы кривое имя во всех ссылках. Для этого есть --name;
старое имя канона при этом становится его синонимом.

    docker compose exec -T backend python manage.py mg_merge_products 35477 35550 --name "Агар-агар" --apply
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.fridge.aliases import learn_alias, normalize_alias
from apps.fridge.dedup import merge_product_into
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS
from apps.recipes.ingredient_noise import is_ingredient_fragment


class Command(BaseCommand):
    help = "MG_MERGEMANUAL: слить указанные продукты в первый из них. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("canon_id", type=int, help="Номер записи, которая останется.")
        parser.add_argument(
            "dup_ids",
            type=int,
            nargs="*",
            help="Номера записей, которые сольются в канон. Можно не указывать, если задан --name.",
        )
        parser.add_argument("--apply", action="store_true", help="Выполнить слияние (иначе только показать).")
        parser.add_argument(
            "--name",
            default="",
            help="Переименовать канон после слияния. Для случая, когда годного имени нет ни у одной записи.",
        )

    def handle(self, *args, **opts):
        canon_id = opts["canon_id"]
        dup_ids = list(dict.fromkeys(opts["dup_ids"]))  # повтор номера — не две операции
        # Без дублей команда всё равно осмысленна, если задано новое имя:
        # «Варенья из кедровых шишек» — кривая запись без пары, сливать её не во
        # что, а переименовать надо.
        if not dup_ids and not (opts["name"] or "").strip():
            raise CommandError("Нечего делать: укажите номера дублей или --name.")
        if canon_id in dup_ids:
            raise CommandError("Канон #%d указан и среди дублей: слить запись саму в себя нельзя." % canon_id)

        found = {p.id: p for p in Product.objects.filter(id__in=[canon_id] + dup_ids).select_related("category_fk")}
        missing = [i for i in [canon_id] + dup_ids if i not in found]
        if missing:
            raise CommandError("Записей нет в каталоге: %s" % ", ".join("#%d" % i for i in missing))

        # Продукт семьи — чужой: он виден только её участникам, и сливать его с
        # общим каталогом значит менять чужие списки. Скрытые из подборщиков
        # записи (справочник штрих-кодов) — тоже не наше дело: их 32 тысячи, и
        # ссылок на них у людей нет.
        for p in found.values():
            if p.owner_family_id is not None:
                raise CommandError("«%s» (#%d) — продукт семьи, не общий каталог." % (p.name, p.id))
            if p.source in HIDDEN_FROM_PICKERS:
                raise CommandError("«%s» (#%d) скрыт из подборщиков (%s)." % (p.name, p.id, p.source))

        canon = found[canon_id]
        dups = [found[i] for i in dup_ids]

        # MG_MERGERENAME: последняя горсть групп из дедупа — те, где годного
        # имени нет ни у кого. «Агара» и «Агар агара»: правильного «Агар-агар»
        # в каталоге нет вовсе, и слияние без переименования оставляет кривое
        # имя во всех ссылках. Рядом «Подсолнечное» + «Масл подсолнечное» и
        # «Яйца – 1 шт. с1» + «Яйца – 1шт».
        new_name = (opts["name"] or "").strip()
        if new_name:
            if is_ingredient_fragment(new_name):
                raise CommandError("«%s» — не название продукта: в нём примечание или количество." % new_name)
            clash = (
                Product.objects.filter(owner_family__isnull=True)
                .exclude(id__in=[canon_id] + dup_ids)
                .exclude(source__in=HIDDEN_FROM_PICKERS)
            )
            key = normalize_alias(new_name)
            same = [p for p in clash if normalize_alias(p.name) == key]
            if same:
                raise CommandError(
                    "Такая запись уже есть: «%s» (#%d). Сливайте в неё, а не заводите второе имя."
                    % (same[0].name, same[0].id)
                )
            self.stdout.write("Новое имя канона: «%s» (было «%s»)" % (new_name, canon.name))

        def _describe(p):
            rubric = p.category_fk.slug if p.category_fk else "—"
            kbju = "есть" if (isinstance(p.nutrition, dict) and p.nutrition) else "нет"
            return "«%s» (#%d, рубрика %s, КБЖУ %s, источник %s)" % (p.name, p.id, rubric, kbju, p.source)

        self.stdout.write("Канон: %s" % _describe(canon))
        for p in dups:
            self.stdout.write("  дубль: %s" % _describe(p))

        # Сколько ссылок переедет — это и есть цена ошибки, и видеть её надо ДО
        # записи, а не в отчёте после.
        from apps.fridge.models import FridgeItem
        from apps.recipes.models import RecipeProduct
        from apps.shopping.models import ShoppingListItem

        for model, label in (
            (RecipeProduct, "связей рецептов"),
            (ShoppingListItem, "позиций списков"),
            (FridgeItem, "позиций холодильника"),
        ):
            n = model.objects.filter(product_id__in=[p.id for p in dups]).count()
            self.stdout.write("  %s к переносу: %d" % (label, n))

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        moved = {"recipe": 0, "shop": 0, "fridge": 0, "kbju": 0, "fields": 0}
        with transaction.atomic():
            for dup in dups:
                s = merge_product_into(dup, canon)
                for k in moved:
                    moved[k] += s[k]
            if new_name:
                # Старое имя остаётся синонимом: по нему ищут связи рецептов и
                # разбор ингредиентов, и терять его при переименовании нельзя.
                # Порядок важен — learn_alias молча ничего не делает, если имя
                # совпадает с текущим именем товара, так что сперва переименование.
                old_name = canon.name
                canon.name = new_name
                canon.save(update_fields=["name"])
                learn_alias(old_name, canon, source="merge")

        self.stdout.write(
            self.style.SUCCESS(
                "Слито записей: %d. Перенесено — рецепты: %d, покупки: %d, холодильник: %d; "
                "КБЖУ: %d; прочих полей: %d."
                % (len(dups), moved["recipe"], moved["shop"], moved["fridge"], moved["kbju"], moved["fields"])
            )
        )
