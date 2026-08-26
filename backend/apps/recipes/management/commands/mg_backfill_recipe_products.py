"""MG_RECIPELINK: сборка связей рецепт→продукт (канонизация + сопоставление).

Названия ингредиентов канонизирует ИИ, поэтому перед долгим прогоном команда
сначала проверяет, что провайдер вообще отвечает. Без проверки прогон при
мёртвом ключе доходит до конца и выглядит успешным: связи строятся по сырым
названиям из текста рецепта, в падежах и с числительными. Именно так каталог
однажды наполнился «Сливами» и «Временем приготовления 40 мин».

Проход ИИ идёт целиком до того, как записана хоть одна связь, поэтому обрыв на
середине терял всё — и время, и деньги. Ответы модели теперь копятся в файле и
переиспользуются: повторный запуск спрашивает только то, чего в нём нет. Кэш
привязан к модели и к тексту промпта, так что смена любого из двух его
обесценивает — старые ответы применяться не будут.

    python manage.py mg_backfill_recipe_products
    python manage.py mg_backfill_recipe_products --force        # пересобрать всё
    python manage.py mg_backfill_recipe_products --no-ai        # осознанно без ИИ
    python manage.py mg_backfill_recipe_products --no-cache     # спросить всё заново
"""

import os

from django.conf import settings
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
            "--cache",
            default="",
            help="Файл с ответами модели. По умолчанию — canon_cache.json в MEDIA_ROOT.",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Не читать и не писать кэш: спросить модель обо всём заново.",
        )
        parser.add_argument(
            "--no-ai",
            action="store_true",
            help="Не проверять провайдера и строить связи по сырым названиям. Качество будет хуже.",
        )

    def cache_path(self, opts):
        """Где лежат ответы модели. MEDIA_ROOT — чтобы деплой их не сносил."""
        if opts["no_cache"]:
            return None
        return opts["cache"] or os.path.join(settings.MEDIA_ROOT, "canon_cache.json")

    def say(self, message):
        """Пишем и сразу выталкиваем.

        MG_LIVELOG: вывод команды уходит в пайп (docker compose exec -T), а он
        буферизуется. Пачка канонизации идёт 5-10 секунд, и без выталкивания
        строки долетают рывками — прогон выглядит зависшим ровно тогда, когда
        он просто работает. В fill_kbju_ai этот flush стоит по той же причине.
        """
        self.stdout.write(str(message))
        self.stdout.flush()

    def handle(self, *args, **opts):
        try:
            stats = backfill(
                force=opts["force"],
                menu_id=opts.get("menu"),
                recipe_ids=opts.get("recipe"),
                limit=opts.get("limit"),
                log=self.say,
                require_ai=not opts["no_ai"],
                chunk_size=opts["chunk_size"],
                cache_path=self.cache_path(opts),
            )
        except AIUnavailable as exc:
            raise CommandError(
                "ИИ-провайдер недоступен — %s\n"
                "Связи строить нечем: без канонизации в каталог поедут сырые названия из рецептов.\n"
                "Проверьте настройки: manage.py mg_ai_ping\n"
                "Если это осознанно — повторите с --no-ai." % exc
            )
        self.stdout.write(self.style.SUCCESS(str(stats)))
