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

Правило — эвристика, и план читает человек. Поэтому есть два флага: --skip
выкидывает из плана строку («Сала» — родительный от «Сало», а совпало с
«Салат»), --alias задаёт пару, которую правило не нашло («Помидор черри» и
«Томаты черри» начинаются с разных слов).

    docker compose exec -T backend python manage.py mg_link_orphans
    docker compose exec -T backend python manage.py mg_link_orphans --skip Сала --apply
    docker compose exec -T backend python manage.py mg_link_orphans --alias "Помидор черри=969"
"""

import collections
import re

from django.core.management.base import BaseCommand, CommandError
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
        parser.add_argument(
            "--skip",
            action="append",
            default=[],
            help="Убрать имя из плана: «--skip Сала». Можно повторять.",
        )
        parser.add_argument(
            "--alias",
            action="append",
            default=[],
            help="Своя пара, которую правило не нашло: «--alias 'Помидор черри=969'». Можно повторять.",
        )

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

        # MG_LINKSKIP: план читает человек, и выкинуть из него строку он должен
        # уметь. Морфологию без словаря правило не берёт: «Сала» — родительный
        # от «Сало», но «сала» совпало с началом «салат», а «сало» с ключом
        # «сало» в кандидаты не попало. Чинить тут нечего — это цена эвристики,
        # и цена приемлемая ровно потому, что план просматривают.
        skip = {normalize_alias(s) for s in opts["skip"]}

        # MG_LINKMANUAL: обратный случай — связь очевидна человеку, а правилу
        # нет: «Помидор черри» и «Томаты черри» (22 связи на проде) начинаются
        # с разных слов. Указать пару руками надо уметь, иначе самый частый
        # случай остаётся неразобранным.
        manual = {}
        for pair in opts["alias"]:
            name, _, pid = pair.rpartition("=")
            if not name or not pid.strip().isdigit():
                raise CommandError("Пара задаётся как «Имя=НОМЕР», получено: %r" % pair)
            product = Product.objects.filter(id=int(pid)).first()
            if product is None:
                raise CommandError("Товара #%s нет в каталоге (пара «%s»)." % (pid.strip(), name))
            manual[normalize_alias(name)] = (name.strip(), product)

        plan, unmatched, skipped = [], [], []
        for name, count in orphans.most_common():
            norm = normalize_alias(name)
            if norm in skip:
                skipped.append((count, name))
                continue
            if norm in manual:
                plan.append((count, name, manual[norm][1]))
                continue
            found = by_key.get(stem_key(name) or (), [])
            if len(found) == 1:
                plan.append((count, name, found[0]))
            else:
                unmatched.append((count, name, len(found)))

        # Пары, которых среди сирот не нашлось: имя могло измениться или уже
        # разобраться. Молчать нельзя — человек считает, что задал связь.
        seen = {normalize_alias(n) for _c, n, _p in plan}
        for norm, (name, product) in manual.items():
            if norm not in seen:
                self.stderr.write(
                    self.style.WARNING(
                        "Пара «%s» -> «%s»: такого имени среди связей нет, строка пропущена." % (name, product.name)
                    )
                )

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

        if skipped:
            self.stdout.write("")
            self.stdout.write("Выкинуто из плана флагом --skip — %d:" % len(skipped))
            for count, name in skipped:
                self.stdout.write("   %3d  «%s»" % (count, name))

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не изменено. Для записи: --apply"))
            return

        written = 0
        with transaction.atomic():
            for _count, name, product in plan:
                if learn_alias(name, product, source="auto") is not None:
                    written += 1
        self.stdout.write(self.style.SUCCESS("Синонимов записано: %d." % written))
