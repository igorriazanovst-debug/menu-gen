"""Сколько продуктов без КБЖУ и каких — перед тем, как чинить.

Команда ничего не пишет, никуда не ходит и ничего не стоит. Она отвечает на
вопрос, с которого должна начинаться любая починка каталога: сколько дыр, у
кого они и чем их можно закрыть. Без этого выбор между бесплатным и платным
способом делается на глаз, а разница — тысячи запросов к модели.

Дыры бывают трёх видов, и лечатся они по-разному:

* **пусто совсем** — ни калорийности, ни белков-жиров-углеводов;
* **только калории** — есть ккал, но нет макронутриентов;
* **только макро** — есть белки-жиры-углеводы, но нет ккал.

Отдельно считается, у скольких из них есть штрих-код: такие чинятся
БЕСПЛАТНО повторным запросом в OpenFoodFacts (`refill_kbju_from_off`), и
тратить на них запрос к модели незачем. Остальным дорога в `fill_kbju_ai`,
и это уже деньги.

Личные продукты людей (`owner_family` заполнен) считаются отдельной строкой:
их мы не трогаем ни тем, ни другим способом — пустое поле там означает
«человек не указал», а не «посчитай за него».

    docker compose exec -T backend python manage.py mg_kbju_gaps
    docker compose exec -T backend python manage.py mg_kbju_gaps --sample 5
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS

# Пустой nutrition — это `{}` либо NULL. Выражено так же, как в fill_kbju_ai:
# два разных определения «есть КБЖУ» в одном проекте — верный способ получить
# два разных числа и не понять, какое правдивее.
NO_NUTRITION = Q(nutrition__isnull=True) | Q(nutrition={})
NO_KCAL = Q(calories_per_100g__isnull=True)


class Command(BaseCommand):
    help = "Посчитать продукты без КБЖУ: по источникам, по виду дыры, по наличию штрих-кода"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample",
            type=int,
            default=0,
            help="показать N примеров названий на каждый источник (по умолчанию не показывать)",
        )

    def handle(self, *args, **opts):
        common = Product.objects.filter(owner_family__isnull=True)
        personal = Product.objects.filter(owner_family__isnull=False)

        self.stdout.write(self.style.MIGRATE_HEADING("Общий каталог"))
        self._table(common, opts["sample"])

        gaps_personal = personal.filter(NO_NUTRITION & NO_KCAL).count()
        self.stdout.write("")
        self.stdout.write(
            f"Личные продукты людей: {personal.count()} всего, из них без КБЖУ {gaps_personal}. "
            "Ни одна из двух починок их не трогает."
        )

    def _table(self, qs, sample: int):
        total = qs.count()
        empty = qs.filter(NO_NUTRITION & NO_KCAL)
        kcal_only = qs.filter(NO_NUTRITION & ~NO_KCAL)
        macro_only = qs.filter(~NO_NUTRITION & NO_KCAL)
        gaps = qs.filter(NO_NUTRITION | NO_KCAL)

        self.stdout.write(f"  всего продуктов:        {total}")
        self.stdout.write(f"  с дырой в КБЖУ:         {gaps.count()}")
        self.stdout.write(f"    пусто совсем:         {empty.count()}")
        self.stdout.write(f"    только калории:       {kcal_only.count()}")
        self.stdout.write(f"    только макро:         {macro_only.count()}")

        with_barcode = gaps.exclude(barcode__isnull=True).exclude(barcode="").count()
        self.stdout.write("")
        self.stdout.write(f"  из них со штрих-кодом:  {with_barcode}  → бесплатно, refill_kbju_from_off")
        self.stdout.write(f"  без штрих-кода:         {gaps.count() - with_barcode}  → платно, fill_kbju_ai")

        self.stdout.write("")
        self.stdout.write("  по источникам (только записи с дырой):")
        for code, label in Product.Source.choices:
            n = gaps.filter(source=code).count()
            if not n:
                continue
            hidden = " [скрыт из выбора]" if code in HIDDEN_FROM_PICKERS else ""
            self.stdout.write(f"    {code:<10} {n:>7}  {label}{hidden}")
            if sample:
                for p in gaps.filter(source=code).order_by("id")[:sample]:
                    code_str = p.barcode or "—"
                    self.stdout.write(f"               {code_str:<15} {p.name[:60]}")
        blank = gaps.filter(Q(source__isnull=True) | Q(source="")).count()
        if blank:
            self.stdout.write(f"    {'(пусто)':<10} {blank:>7}  источник не проставлен")
