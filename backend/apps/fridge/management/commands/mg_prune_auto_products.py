"""MG_AUTOPROD2: убрать из каталога машинные записи, которые продуктами не являются.

Продукты с `source=auto` заводит сборка связей рецепт→продукт: если ингредиента
в каталоге нет, она создаёт запись, иначе рецепт не найдётся в подборе «что
приготовить из холодильника». Источник `auto` из подборщиков не скрыт, поэтому
всё, что она завела, пользователь видит в холодильнике и дневнике.

За несколько импортов туда натекло то, что ингредиентом никогда не было:
у части рецептов в состав уехала разметка страницы — «Время приготовления
40 мин», «Итальянская кухня», «Завтрак», — а ещё в каталоге осели названия
блюд («Рататуй», «Запеканка картофельная»): в исходнике они стояли в списке
ингредиентов.

Первая версия команды сносила всё машинное из «Прочего», и это было неверно:
«Прочее» — не метка ошибки, а честная категория для того, что не разложилось по
рубрикам. В той же куче оказались «Бекон копчёный», «Соль мелкая», «Морской
коктейль» — нормальные продукты. Поэтому удаление идёт по правилам:

- `metadata` (по умолчанию) — строка со страницы рецепта, а не еда: «Время
  приготовления N мин», «… кухня», названия разделов и приёмов пищи, одинокие
  прилагательные («Очищенный», «Чёрный»);
- `dish` — название совпадает с заголовком рецепта. Правило **не** включено по
  умолчанию: совпадение с рецептом не доказывает, что продукта не существует.
  На проверке из десяти находок блюдами оказались четыре («Рататуй», «Голубцы»,
  «Драники», «Картофельное пюре»), а остальные шесть — «Багет», «Маршмеллоу»,
  «Вареная сгущенка», «Томатный соус», «Карамельный соус», «Сахарная глазурь» —
  то, что покупают в магазине. Багет можно испечь и можно купить, и по названию
  рецепта одно от другого не отличить;
- `orphan` — на запись не ссылается ВООБЩЕ ничто, включая связи рецептов.
  Такое остаётся после пересборки связей: связи ушли на правильные продукты, а
  запись, заведённая прошлым прогоном по сырому названию, повисла. Именно это
  и оставил после себя мёртвый провайдер. Правило не смотрит ни на название, ни
  на категорию — только на ссылки, поэтому ошибиться в нём негде;
- `all` — всё машинное из «Прочего». Включать руками и только посмотрев список.

Остальное командой не трогается: разбирать «Икру» и «Бульон» должен редактор.

В правилах `metadata`, `dish` и `all` запись пропускается, если на неё ссылается
хоть что-то, кроме связей рецептов: холодильник, дневник, список покупок,
синоним из админки. В `orphan` не считается ссылкой вообще ничего — там и
берутся только записи без единой ссылки.

Связь рецепта удаление переживает: `RecipeProduct.product` — SET_NULL, название
и категория ингредиента хранятся в самой связи, так что список покупок не
меняется.

По умолчанию — DRY-RUN. Запись — флагом --apply.

    docker compose exec -T backend python manage.py mg_prune_auto_products
    docker compose exec -T backend python manage.py mg_prune_auto_products --apply
    docker compose exec -T backend python manage.py mg_prune_auto_products --rules metadata,dish
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.fridge.models import Product

# Связь рецепта с продуктом — не пользовательские данные: её пересоберёт
# mg_backfill_recipe_products. Всё остальное, что ссылается на продукт, —
# признак того, что запись живая, и трогать её нельзя.
RECIPE_LINK = "recipes.RecipeProduct"

# Строки со страницы рецепта, принятые за ингредиент. Список набран по тому,
# что реально лежит в каталоге, а не по догадкам.
METADATA_RE = [
    re.compile(r"^время приготовления\b"),
    re.compile(r"^\d+\s*(мин|минут|час)\w*$"),
    re.compile(r"\bкухня$"),
    re.compile(r"^(завтрак|обед|ужин|полдник|перекус|десерты|закуски|напитки|выпечка)$"),
    re.compile(r"^(выше|ниже|далее|остальное|по вкусу|по желанию|опционально|см)$"),
    # Одинокое прилагательное — это обрывок строки: «Очищенный», «Чёрный»,
    # «Вегетарианские». Продукта из одного прилагательного не бывает.
    #
    # Окончания -ое и -ее сюда не входят намеренно: «Мороженое», «Заливное»,
    # «Жаркое» — прилагательные по форме, но продукты по смыслу.
    re.compile(r"^\S+(ый|ий|ой|ая|яя|ые|ие)$"),
]


def _norm(name):
    return (name or "").strip().lower().replace("ё", "е")


def is_metadata(name):
    n = _norm(name)
    return any(rx.search(n) for rx in METADATA_RE)


def dish_titles():
    """Заголовки рецептов — нормализованные, для сверки с названиями продуктов."""
    from apps.recipes.models import Recipe

    return {_norm(t) for t in Recipe.objects.values_list("title", flat=True) if t}


def referenced_ids(product_ids, skip_recipe_links=True):
    """id продуктов, на которые хоть что-то ссылается.

    Обходим входящие связи через _meta, а не списком моделей: появится новая
    ссылка на продукт — она учтётся сама, без правки этой команды.

    `skip_recipe_links` — связь рецепта не считать: её пересобирает
    mg_backfill_recipe_products, и держаться за неё смысла нет. Для правила
    `orphan` наоборот важно учесть и её: там ищут записи, на которые не
    ссылается вообще ничто.
    """
    used = set()
    for rel in Product._meta.related_objects:
        model = rel.related_model
        label = "%s.%s" % (model._meta.app_label, model.__name__)
        if skip_recipe_links and label == RECIPE_LINK:
            continue
        field = rel.field.name
        used.update(model.objects.filter(**{"%s__in" % field: product_ids}).values_list("%s_id" % field, flat=True))
    used.discard(None)
    return used


def orphans():
    """Машинные записи, на которые не ссылается НИЧТО — даже связь рецепта.

    Появляются так: связи пересобрали, и они ушли на правильные продукты, а
    запись, заведённая прошлым прогоном по сырому названию, осталась висеть.
    Ровно это и оставил после себя мёртвый провайдер: «Мандарина» вместо
    «Мандарина» в именительном, «Время приготовления 40 мин» и прочее.

    Правило не смотрит ни на название, ни на категорию — только на ссылки,
    поэтому и ошибиться в нём негде: удаляется то, чем никто не пользуется.
    """
    rows = list(Product.objects.filter(source=Product.Source.AUTO, owner_family__isnull=True).order_by("id"))
    if not rows:
        return []
    used = referenced_ids([p.id for p in rows], skip_recipe_links=False)
    return [p for p in rows if p.id not in used]


def classify(rules):
    """-> (к удалению, остаток) среди машинных записей, не тронутых людьми."""
    if "orphan" in rules:
        return {"orphan": orphans()}, []

    rows = list(
        Product.objects.filter(
            Q(category_fk__slug="other") | Q(category_fk__isnull=True),
            source=Product.Source.AUTO,
            owner_family__isnull=True,
        ).order_by("id")
    )
    if not rows:
        return {}, []
    used = referenced_ids([p.id for p in rows])
    rows = [p for p in rows if p.id not in used]

    if "all" in rules:
        return {"all": rows}, []

    titles = dish_titles() if "dish" in rules else set()
    hit = {"metadata": [], "dish": []}
    rest = []
    for p in rows:
        if "metadata" in rules and is_metadata(p.name):
            hit["metadata"].append(p)
        elif "dish" in rules and _norm(p.name) in titles:
            hit["dish"].append(p)
        else:
            rest.append(p)
    return {k: v for k, v in hit.items() if v}, rest


class Command(BaseCommand):
    help = "Удалить машинные записи (source=auto), которые продуктами не являются. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Удалить (иначе только показать список).")
        parser.add_argument(
            "--rules",
            default="metadata",
            help="Через запятую: metadata (по умолчанию), orphan, dish, all.",
        )
        parser.add_argument("--limit", type=int, default=40, help="Сколько названий показать на правило.")

    def handle(self, *args, **opts):
        rules = {r.strip() for r in opts["rules"].split(",") if r.strip()}
        unknown = rules - {"metadata", "dish", "orphan", "all"}
        if unknown:
            self.stderr.write("Неизвестные правила: %s" % ", ".join(sorted(unknown)))
            return

        hit, rest = classify(rules)
        doomed = [p for group in hit.values() for p in group]

        self.stdout.write("Продуктов source=auto всего: %d" % Product.objects.filter(source="auto").count())
        for rule, group in hit.items():
            self.stdout.write("")
            self.stdout.write("%s — %d:" % (rule, len(group)))
            for p in group[: opts["limit"]]:
                self.stdout.write("  %s" % p.name)
            if len(group) > opts["limit"]:
                self.stdout.write("  … и ещё %d" % (len(group) - opts["limit"]))
        if rest:
            self.stdout.write("")
            self.stdout.write("Оставлено редактору — %d, например:" % len(rest))
            for p in rest[: opts["limit"]]:
                self.stdout.write("  %s" % p.name)

        self.stdout.write("")
        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: под удаление %d. Повторите с --apply." % len(doomed)))
            return
        if not doomed:
            return

        with transaction.atomic():
            Product.objects.filter(id__in=[p.id for p in doomed]).delete()
        self.stdout.write(self.style.SUCCESS("Удалено записей: %d" % len(doomed)))
        self.stdout.write("Связи рецептов сохранены: название и категория ингредиента лежат в самой связи.")
