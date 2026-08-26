"""MG_RECIPELINK: сборка связей рецепт→продукт (канонизация + сопоставление).

Названия ингредиентов канонизирует ИИ, поэтому перед долгим прогоном команда
сначала проверяет, что провайдер вообще отвечает. Без проверки прогон при
мёртвом ключе доходит до конца и выглядит успешным: связи строятся по сырым
названиям из текста рецепта, в падежах и с числительными. Именно так каталог
однажды наполнился «Сливами» и «Временем приготовления 40 мин».

    python manage.py mg_backfill_recipe_products
    python manage.py mg_backfill_recipe_products --force        # пересобрать всё
    python manage.py mg_backfill_recipe_products --no-ai        # осознанно без ИИ
"""

from django.core.management.base import BaseCommand, CommandError

from apps.common.ai_provider import AIUnavailable
from apps.recipes.recipe_products import backfill


class Command(BaseCommand):
    help = "MG_RECIPELINK: backfill RecipeProduct links (canonicalize + match + categorize)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--menu", type=int, default=None)
        parser.add_argument("--recipe", type=int, nargs="*", default=None)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=30,
            help="Сколько названий слать в одной пачке. Меньше — дольше, но реже упирается в таймаут.",
        )
        parser.add_argument(
            "--no-ai",
            action="store_true",
            help="Не проверять провайдера и строить связи по сырым названиям. Качество будет хуже.",
        )

    def handle(self, *args, **opts):
        try:
            stats = backfill(
                force=opts["force"],
                menu_id=opts.get("menu"),
                recipe_ids=opts.get("recipe"),
                limit=opts.get("limit"),
                log=lambda m: self.stdout.write(str(m)),
                require_ai=not opts["no_ai"],
                chunk_size=opts["chunk_size"],
            )
        except AIUnavailable as exc:
            raise CommandError(
                "ИИ-провайдер недоступен — %s\n"
                "Связи строить нечем: без канонизации в каталог поедут сырые названия из рецептов.\n"
                "Проверьте настройки: manage.py mg_ai_ping\n"
                "Если это осознанно — повторите с --no-ai." % exc
            )
        self.stdout.write(self.style.SUCCESS(str(stats)))
