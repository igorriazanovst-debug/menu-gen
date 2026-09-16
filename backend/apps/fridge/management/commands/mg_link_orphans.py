"""MG_LINKORPHAN: связи рецептов, не наводящиеся ни на один товар.

Список покупок строится из связей рецепт→продукт. У связи есть своё имя и своя
рубрика — слепок на момент сборки, — и если по этому имени товар в каталоге не
находится, позиция остаётся без товара и без рубрики. В списке это видно как
строки в «Прочем»: «Сушеных трав», «Помидор черри», «Листика шалфея».

Чистка каталога такие связи не трогает: там правятся товары, а имя лежит в
связи. Пересборка связей это чинит, но идёт больше часа и перебирает все
полторы тысячи рецептов ради хвоста — на проде таких связей 266 из 15465.

Здесь дешевле: почти все эти имена — падежи и формы числа от того, что в
каталоге уже есть («Салата» / «Салат», «Рукколы» / «Руккола», «Молотой
паприки» / «Паприка молотая»). Сводится это сравнением начал слов, без ИИ:

    ключ("Сушеных трав")   = ("суше", "трав")
    ключ("Сушёные травы")  = ("суше", "трав")

Совпало ровно с одним товаром — предлагаем синоним. Ноль или несколько —
оставляем человеку: угадывать, какое из двух «масел» имелось в виду, команда
не должна.

Пишутся только синонимы (ProductAlias). Ни товары, ни связи не меняются, и
ошибку видно в списке синонимов админки — удалить строку дешевле, чем
разбирать последствия слияния.

    docker compose exec -T backend python manage.py mg_link_orphans
    docker compose exec -T backend python manage.py mg_link_orphans --apply
"""

import collections
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.aliases import learn_alias, normalize_alias, product_ref_index, resolve_ref
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS
from apps.recipes.ingredient_noise import clean_ingredient_name

# Сколько букв слова берём в ключ. Четыре — из наблюдения за реальными парами:
# «помидор»/«помидора» расходятся с пятой буквы, «трав»/«травы» — с пятой же.
# Короче брать нельзя: «сок»/«соль» слились бы в одно.
STEM = 4


def stem_key(name):
    """Ключ сравнения: начала слов, порядок не важен.

    Наследует normalize_alias (регистр, ё, скобки, количество в начале) и
    добавляет к этому нечувствительность к падежу и числу.
    """
    base = normalize_alias(name)
    words = [w for w in re.split(r"[\s\-]+", base) if len(w) > 1]
    if not words:
        return None
    return tuple(sorted(w[:STEM] for w in words))


class Command(BaseCommand):
    help = "MG_LINKORPHAN: завести синонимы для имён связей, не находящих товар. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать синонимы (иначе только показать).")
        parser.add_argument("--show", type=int, default=60, help="Сколько строк показать в каждом разделе.")

    def handle(self, *args, **opts):
        from apps.recipes.models import RecipeProduct

        idx = product_ref_index()

        # Имена связей, по которым товар не находится. Считаем сразу, сколько
        # раз каждое встречается: это цена вопроса, а не список для красоты.
        orphans = collections.Counter()
        total = 0
        for name in RecipeProduct.objects.values_list("name_canonical", flat=True):
            total += 1
            cleaned = clean_ingredient_name(name or "")
            if cleaned and resolve_ref(cleaned, idx) is None:
                orphans[cleaned] += 1

        self.stdout.write(
            "Связей всего: %d; не наводятся на товар: %d (разных имён: %d)."
            % (total, sum(orphans.values()), len(orphans))
        )
        if not orphans:
            return

        # Каталог по ключу основ. Скрытые из подборщиков записи не берём: это
        # 30 тысяч упаковок из справочника штрих-кодов, синоним на них увёл бы
        # ингредиент рецепта на конкретный SKU.
        by_key = collections.defaultdict(list)
        for p in Product.objects.filter(owner_family__isnull=True).exclude(source__in=HIDDEN_FROM_PICKERS):
            key = stem_key(p.name)
            if key:
                by_key[key].append(p)

        plan, unmatched = [], []
        for name, count in orphans.most_common():
            found = by_key.get(stem_key(name) or (), [])
            if len(found) == 1:
                plan.append((count, name, found[0]))
            else:
                unmatched.append((count, name, len(found)))

        show = opts["show"]
        self.stdout.write("")
        self.stdout.write("Синонимы к заведению — %d имён (%d связей):" % (len(plan), sum(c for c, _, _ in plan)))
        for count, name, product in plan[:show]:
            self.stdout.write("   %3d  «%s» -> «%s» (#%d)" % (count, name, product.name, product.id))
        if len(plan) > show:
            self.stdout.write("   … и ещё %d" % (len(plan) - show))

        # Молчать о несопоставленных нельзя: это не «всё разобрано, кроме
        # мелочи», а половина работы, которую делать человеку. Часть из них —
        # товары, которых в каталоге просто нет («Утка», «Рулька»).
        self.stdout.write("")
        self.stdout.write("Не сопоставлено — %d имён (%d связей):" % (len(unmatched), sum(c for c, _, _ in unmatched)))
        for count, name, n in unmatched[:show]:
            why = "нет подходящего товара" if n == 0 else "подходит %d товаров" % n
            self.stdout.write("   %3d  «%s» — %s" % (count, name, why))
        if len(unmatched) > show:
            self.stdout.write("   … и ещё %d" % (len(unmatched) - show))

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        written = 0
        with transaction.atomic():
            for _count, name, product in plan:
                if learn_alias(name, product, source="auto") is not None:
                    written += 1
        self.stdout.write(self.style.SUCCESS("Синонимов записано: %d." % written))
