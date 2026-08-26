"""MG_AUTOPROD2: убрать из каталога машинные продукты, которые никому не нужны.

Продукты с `source=auto` заводит сборка связей рецепт→продукт: если ингредиента
в каталоге нет, она создаёт запись, иначе рецепт не найдётся в подборе «что
приготовить из холодильника».

Пока название приходило от канонизатора, это работало. Но там, где ИИ не
отвечал, в каталог уходило исходное написание из рецепта — «Сливы», «Мандарина»,
«2 яйца вареных», «Клюква для украшения». Пользователь видит их в холодильнике и
дневнике наравне с выверенными продуктами.

Причина закрыта в `recipe_products.py` (по неопознанному сегменту запись больше
не заводится), а эта команда разгребает то, что уже создано.

Под удаление попадает запись, у которой сошлось всё:

- `source=auto` — завела машина, не редактор;
- категория «Прочее» или пустая — именно так помечается ингредиент, который
  канонизатор не разобрал: категорию он не назвал, и подставилась общая;
- на неё не ссылается ничего, кроме связей рецептов: ни холодильник, ни
  дневник, ни список покупок, ни синоним из админки.

Связь рецепта переживает удаление: `RecipeProduct.product` — SET_NULL, название
и категория ингредиента хранятся в самой связи, так что список покупок не
меняется. Потеряется только сопоставление этого ингредиента с холодильником —
которого и не было: ни у кого в холодильнике нет «Мандарины».

По умолчанию — DRY-RUN. Запись — флагом --apply.

    docker compose exec -T backend python manage.py mg_prune_auto_products
    docker compose exec -T backend python manage.py mg_prune_auto_products --apply
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.fridge.models import Product

# Связь рецепта с продуктом — не пользовательские данные: её пересоберёт
# mg_backfill_recipe_products. Всё остальное, что ссылается на продукт, —
# признак того, что запись живая, и трогать её нельзя.
RECIPE_LINK = "recipes.RecipeProduct"


def user_referenced_ids(product_ids):
    """id продуктов, на которые ссылается хоть что-нибудь, кроме связей рецептов.

    Обходим входящие связи через _meta, а не списком моделей: появится новая
    ссылка на продукт — она учтётся сама, без правки этой команды.
    """
    used = set()
    for rel in Product._meta.related_objects:
        model = rel.related_model
        label = "%s.%s" % (model._meta.app_label, model.__name__)
        if label == RECIPE_LINK:
            continue
        field = rel.field.name
        used.update(model.objects.filter(**{"%s__in" % field: product_ids}).values_list("%s_id" % field, flat=True))
    used.discard(None)
    return used


def candidates():
    """Машинные продукты без категории (или в «Прочем»), не тронутые людьми."""
    rows = list(
        Product.objects.filter(
            Q(category_fk__slug="other") | Q(category_fk__isnull=True),
            source=Product.Source.AUTO,
            owner_family__isnull=True,
        ).order_by("id")
    )
    if not rows:
        return []
    used = user_referenced_ids([p.id for p in rows])
    return [p for p in rows if p.id not in used]


class Command(BaseCommand):
    help = "Удалить машинные продукты (source=auto) из «Прочего», на которые никто не ссылается. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Удалить (иначе только показать список).")
        parser.add_argument("--limit", type=int, default=60, help="Сколько названий показать.")

    def handle(self, *args, **opts):
        rows = candidates()
        total_auto = Product.objects.filter(source=Product.Source.AUTO).count()

        self.stdout.write("Продуктов source=auto всего: %d" % total_auto)
        self.stdout.write("Под удаление подходит: %d" % len(rows))
        for p in rows[: opts["limit"]]:
            self.stdout.write("  %s" % p.name)
        if len(rows) > opts["limit"]:
            self.stdout.write("  … и ещё %d" % (len(rows) - opts["limit"]))

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN. Ничего не удалено — повторите с --apply."))
            return
        if not rows:
            return

        with transaction.atomic():
            Product.objects.filter(id__in=[p.id for p in rows]).delete()
        self.stdout.write(self.style.SUCCESS("Удалено записей: %d" % len(rows)))
        self.stdout.write("Связи рецептов сохранены: название и категория ингредиента лежат в самой связи.")
