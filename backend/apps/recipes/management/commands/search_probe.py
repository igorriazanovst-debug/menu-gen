"""MG_MORPHSEARCH: что именно найдёт поиск по такому запросу.

Поиск строится регулярным выражением и уходит в СУБД (``~*`` в Postgres,
REGEXP в SQLite). Локальные тесты идут на SQLite, поэтому на живой базе полезно
посмотреть своими глазами: какое выражение получилось и что оно нашло.

Лежит в recipes, а не в common: common — не приложение Django, команды оттуда
не подхватываются.

    python manage.py search_probe тушеная супы яйца
    python manage.py search_probe --model product молоко
"""

from django.core.management.base import BaseCommand, CommandError

from apps.common.morphology import ru_stem
from apps.common.search import search_q, search_regex

MODELS = {
    "recipe": ("apps.recipes.models", "Recipe", ["title"]),
    "product": ("apps.fridge.models", "Product", ["name"]),
}


class Command(BaseCommand):
    help = "Показать, во что превращается поисковый запрос и что он находит."

    def add_arguments(self, parser):
        parser.add_argument("terms", nargs="+", help="слова запроса")
        parser.add_argument("--model", default="recipe", choices=sorted(MODELS))
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **opts):
        module_path, class_name, fields = MODELS[opts["model"]]
        module = __import__(module_path, fromlist=[class_name])
        model = getattr(module, class_name)

        for term in opts["terms"]:
            self.stdout.write("")
            self.stdout.write(f"{term} → основа «{ru_stem(term)}», выражение {search_regex(term)}")
            try:
                qs = model.objects.filter(search_q(model, fields, term))
                total = qs.count()
            except Exception as e:  # СУБД может не принять выражение — это и проверяем
                raise CommandError(f"СУБД отвергла запрос: {e}") from e

            self.stdout.write(f"  найдено: {total}")
            for value in qs.values_list(fields[0], flat=True)[: opts["limit"]]:
                self.stdout.write(f"    {value}")
