"""MG_SAY7PUB: опубликовать рецепты say7, у которых появилась обложка.

Импорт say7 заводит рецепты НЕОПУБЛИКОВАННЫМИ — не по осторожности, а потому
что в выгрузке нет фотографий, а карточка без фото в выдаче выглядит поломкой
(см. `import_say7_recipes`). Публикация с самого начала задумана отдельным
решением: обложки появляются пачками, руками, и публиковать надо ровно тех, у
кого она уже есть.

Отсюда главное правило команды: **обложка проверяется файлом на диске, а не
наличием строки в поле.** Ссылка на несуществующий файл выглядит в админке
точно так же, как настоящая, — и опубликованный по ней рецепт вернёт ту самую
пустую карточку, ради которой всё и держали неопубликованным.

Своей считается и абсолютная ссылка на наш домен
(`https://menugen.ru/media/…`): админка при загрузке файла пишет именно такую,
и файл у неё тот же самый. На этом команда и ошиблась в первый прогон — сочла
чужими тридцать готовых обложек и не опубликовала ни одной. Разбор ссылки живёт
в `check_recipe_images.local_path`, одним местом на обе команды.

По умолчанию берутся только вторые блюда (`--dish-type main`). Салаты, десерты
и прочее остаются, пока их не назовут явно: у салата в выдаче своя цена ошибки,
и решать за него эта команда не должна.

Ничего не меняется без `--apply`. Без него печатается список целиком — и тех,
кого опубликуем, и тех, кого пропустим, с причиной.

Запуск:
    python manage.py mg_publish_say7                    # показать, ничего не менять
    python manage.py mg_publish_say7 --apply            # опубликовать
    python manage.py mg_publish_say7 --dish-type salad  # другой тип блюда
    python manage.py mg_publish_say7 --allow-external   # засчитать и чужие ссылки
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.models import Recipe

# Тот же разбор ссылки, что и у аудита картинок. Своя копия разошлась бы с ним
# незаметно: обе версии молча возвращают None, когда не разобрали.
from .check_recipe_images import local_path, own_hosts

LEGACY_PREFIX = "say7:"


def cover_state(recipe):
    """Что с обложкой: ('ok'|'external'|'missing'|'empty', пояснение)."""
    url = (recipe.image_url or "").strip()
    if not url:
        return "empty", "обложки нет"

    path = local_path(url)
    if path is None:
        return "external", f"ссылка на чужой хост: {url}"
    if not path.exists():
        return "missing", f"файла нет на диске: {path}"
    return "ok", url


class Command(BaseCommand):
    help = "Публикует рецепты say7, у которых появилась обложка (по умолчанию — вторые блюда)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dish-type",
            default="main",
            help="Тип блюда (main, salad, soup…). По умолчанию main — вторые блюда.",
        )
        parser.add_argument(
            "--allow-external",
            action="store_true",
            help="Считать обложкой и ссылку на чужой хост (проверить её файлом нельзя).",
        )
        parser.add_argument("--apply", action="store_true", help="Записать изменения. Без него — только показать.")

    def handle(self, *args, **opts):
        dish_type = opts["dish_type"]
        allowed = {"ok"} | ({"external"} if opts["allow_external"] else set())

        # Печатается всегда: от этого списка зависит, чем окажется абсолютная
        # ссылка — своей обложкой или чужим хостом. Пустая строка здесь сразу
        # объясняет отчёт, в котором «к публикации 0» при готовых картинках.
        self.stdout.write(f"Свои хосты: {', '.join(sorted(own_hosts())) or '(ни одного)'}")

        base = Recipe.objects.filter(legacy_id__startswith=LEGACY_PREFIX)
        self.stdout.write(
            f"Рецептов say7 всего: {base.count()}, из них опубликовано: {base.filter(is_published=True).count()}"
        )

        pending = base.filter(is_published=False, dish_type=dish_type).order_by("id")
        self.stdout.write(f"Неопубликованных с типом «{dish_type}»: {pending.count()}")

        ready, skipped = [], []
        for recipe in pending:
            state, note = cover_state(recipe)
            (ready if state in allowed else skipped).append((recipe, state, note))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"К публикации: {len(ready)}"))
        for recipe, state, note in ready:
            mark = "" if state == "ok" else "  (чужая ссылка, файлом не проверить)"
            self.stdout.write(f"  #{recipe.id}  {recipe.title}{mark}")

        # Пропущенные показываются целиком, а не числом: среди них бывает и то,
        # что чинится за минуту, — не доехавший при переносе файл, например.
        if skipped:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"Пропущено: {len(skipped)}"))
            for recipe, state, note in skipped:
                self.stdout.write(f"  #{recipe.id}  {recipe.title} — {note}")

        # Салаты называются отдельной строкой: их просили не трогать, и полезно
        # видеть, сколько их ждёт, не запуская команду второй раз.
        if dish_type != "salad":
            waiting = base.filter(is_published=False, dish_type="salad").count()
            if waiting:
                self.stdout.write("")
                self.stdout.write(f"Салатов ждёт публикации: {waiting} — эта команда их не трогает.")

        if not ready:
            self.stdout.write("")
            self.stdout.write("Публиковать нечего.")
            return

        if not opts["apply"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Это предпросмотр. Чтобы записать, повторите с --apply."))
            return

        with transaction.atomic():
            ids = [recipe.id for recipe, _, _ in ready]
            Recipe.objects.filter(id__in=ids).update(is_published=True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Опубликовано рецептов: {len(ids)}"))
