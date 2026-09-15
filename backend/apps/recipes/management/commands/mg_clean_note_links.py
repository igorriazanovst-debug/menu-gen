"""MG_NOTENOISE: вычистить примечания из уже накопленных связей рецепт→продукт.

Фильтр в коде (apps/recipes/ingredient_noise.py) закрывает новые связи и новые
записи каталога. Но на проде уже лежит то, что натекло раньше: 94 связи с
названиями вроде «Зелень по вкусу», «Специи по вкусу», «Масло для обжарки», и
27 записей каталога, заведённых по таким же названиям. Список покупок при
сборке их теперь пропускает, однако сами строки остаются в базе и продолжают
болтаться в подборщиках продуктов и в связях рецептов.

Команда правит связи:

- «Зелень по вкусу» → «Зелень», и привязка ищется заново по чистому названию:
  прежняя вела на мусорную запись каталога, заведённую по самому примечанию;
- «по вкусу», «для подачи» — от названия не остаётся ничего, связь удаляется:
  продукта в ней не было;
- привязка на мусорную запись каталога снимается, даже если новая не нашлась.
  Иначе связь так и держала бы товар, которого не должно существовать, и
  `mg_prune_auto_products --rules orphan` не смог бы его убрать.

Сам каталог командой НЕ трогается: записи, оставшиеся без единой ссылки, убирает
уже написанная для этого команда, и там правило про ссылки строже:

    docker compose exec -T backend python manage.py mg_clean_note_links
    docker compose exec -T backend python manage.py mg_clean_note_links --apply
    docker compose exec -T backend python manage.py mg_prune_auto_products --rules orphan
    docker compose exec -T backend python manage.py mg_prune_auto_products --rules orphan --apply

По умолчанию — DRY-RUN: печатается, что изменится, и ничего не пишется.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.ingredient_noise import clean_ingredient_name
from apps.recipes.models import RecipeProduct


def _product_is_noise(name):
    """Запись каталога заведена по примечанию, а не по продукту."""
    s = (name or "").strip()
    if not s:
        return False
    return clean_ingredient_name(s) != s


def plan():
    """-> (к удалению, к правке). Ничего не пишет."""
    from apps.fridge.aliases import product_ref_index, resolve_ref
    from apps.fridge.models import Product

    pidx = product_ref_index()
    noisy_products = {p.id: p.name for p in Product.objects.only("id", "name").iterator() if _product_is_noise(p.name)}

    drop, fix = [], []
    for rp in RecipeProduct.objects.select_related(None).iterator():
        old = (rp.name_canonical or "").strip()
        cleaned = clean_ingredient_name(old)
        link_is_noise = rp.product_id in noisy_products
        if cleaned == old and not link_is_noise:
            continue
        if not cleaned:
            drop.append((rp.id, rp.recipe_id, old, rp.product_id))
            continue

        ref = resolve_ref(cleaned, pidx) if cleaned else None
        new_pid = rp.product_id
        new_name = cleaned
        new_slug = rp.category_slug
        new_cat = rp.category_fk_id
        if ref is not None:
            new_pid = ref["id"]
            new_name = ref["name"]
            if ref["slug"]:
                new_slug = ref["slug"]
                new_cat = ref["cat_id"]
        elif link_is_noise:
            # Чистое название ни с чем не сошлось, а старая привязка вела на
            # мусор — держаться за неё нельзя, иначе мусор не удалить.
            new_pid = None

        if (new_name, new_pid, new_slug, new_cat) == (old, rp.product_id, rp.category_slug, rp.category_fk_id):
            continue
        fix.append((rp.id, rp.recipe_id, old, new_name, rp.product_id, new_pid, new_slug, new_cat))
    return drop, fix


class Command(BaseCommand):
    help = "Убрать примечания рецептов из связей рецепт→продукт. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать (иначе только показать).")
        parser.add_argument("--limit", type=int, default=60, help="Сколько строк показать в каждом списке.")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        drop, fix = plan()

        self.stdout.write("Связей рецепт→продукт всего: %d" % RecipeProduct.objects.count())

        self.stdout.write("")
        self.stdout.write("Удалить (название было примечанием целиком) — %d:" % len(drop))
        for rp_id, recipe_id, old, pid in drop[:limit]:
            self.stdout.write("   рецепт %-7s %-42s product_id=%s" % (recipe_id, old[:42], pid))
        if len(drop) > limit:
            self.stdout.write("   ... скрыто ещё %d" % (len(drop) - limit))

        self.stdout.write("")
        self.stdout.write("Переименовать — %d:" % len(fix))
        for rp_id, recipe_id, old, new, old_pid, new_pid, slug, cat in fix[:limit]:
            self.stdout.write(
                "   рецепт %-7s %-34s → %-28s product_id: %s → %s" % (recipe_id, old[:34], new[:28], old_pid, new_pid)
            )
        if len(fix) > limit:
            self.stdout.write("   ... скрыто ещё %d" % (len(fix) - limit))

        if not opts["apply"]:
            self.stdout.write("")
            self.stdout.write("DRY-RUN. Ничего не изменено. Записать: --apply")
            return

        with transaction.atomic():
            if drop:
                RecipeProduct.objects.filter(id__in=[d[0] for d in drop]).delete()
            for rp_id, _recipe_id, _old, new, _old_pid, new_pid, slug, cat in fix:
                RecipeProduct.objects.filter(id=rp_id).update(
                    name_canonical=new[:255], product_id=new_pid, category_slug=(slug or "")[:64], category_fk_id=cat
                )

        self.stdout.write("")
        self.stdout.write("Удалено связей: %d" % len(drop))
        self.stdout.write("Переименовано связей: %d" % len(fix))
        self.stdout.write(
            "Записи каталога, оставшиеся без ссылок, убирает: manage.py mg_prune_auto_products --rules orphan"
        )
