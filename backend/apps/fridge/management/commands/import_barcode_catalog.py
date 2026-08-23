"""MG_BARCODEDB: загрузка справочника товаров со штрих-кодами.

Зачем. Скан упаковки искал товар в OpenFoodFacts, а когда тот не знал — просил
модель «опознать» код. Догадка по штрих-коду проверяется ничем: код не несёт в
себе названия, так что модель по сути угадывает по стране-производителю. Свой
справочник закрывает ровно эту дыру: 6 тысяч российских товаров с КБЖУ, каждый
со своим кодом.

Что с качеством. В выгрузке КБЖУ заполнено у всех, но у части записей числа не
сходятся: оливковое масло с нулевым жиром и 900 ккал, бедро цыплёнка на 810 ккал.
Часть таких помечена источником (energy_macro_flag), часть — нет, поэтому
проверяем сами: калорийность должна примерно совпадать с 4Б+9Ж+4У. Не сходится —
запись берём, а КБЖУ отбрасываем: опознать товар по коду полезно и без цифр,
а неверные цифры молча уедут в дневник и меню и будут выглядеть как факт.

Выгрузки приходят от разных сетей и с разными заголовками колонок, поэтому
имена колонок сопоставляются по словарю синонимов, а не по точному совпадению:
у одних `barcode`, у других «GTIN», у третьих «Ккал/100г».

Запуск:
    python manage.py import_barcode_catalog                 # все файлы из репозитория
    python manage.py import_barcode_catalog --file /путь.csv --dry-run
"""

from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fridge.barcodes import lookup_q, normalize
from apps.fridge.models import Product, ProductCategory

# .../fridge/management/commands/файл → parents[2] это сам fridge
REFERENCE_DIR = Path(__file__).resolve().parents[2] / "reference"


def default_files():
    """Все выгрузки, лежащие в репозитории. Их несколько — сети разные."""
    return sorted(REFERENCE_DIR.glob("barcode_catalog*.csv*"))


# Заголовки колонок у сетей свои. Сопоставляем по словарю: ключ — как назвали в
# файле (без регистра и пробелов), значение — наше поле.
COLUMN_ALIASES = {
    "barcode": "barcode", "gtin": "barcode", "штрихкод": "barcode", "штрих-код": "barcode",
    "name": "name", "наименование": "name", "название": "name", "товар": "name",
    "quantity": "quantity", "объем": "quantity", "объём": "quantity", "фасовка": "quantity",
    "protein_100g": "protein", "белки/100г": "protein", "белки": "protein",
    "fat_100g": "fat", "жиры/100г": "fat", "жиры": "fat",
    "carbs_100g": "carbs", "углеводы/100г": "carbs", "углеводы": "carbs",
    "kcal_100g": "kcal", "ккал/100г": "kcal", "калорийность": "kcal", "ккал": "kcal",
    "category_path": "category", "категория": "category", "раздел": "category",
}


def canonical_row(row: dict) -> dict:
    """Строка файла → наши поля. Неизвестные колонки просто игнорируем."""
    out = {}
    for key, value in row.items():
        field = COLUMN_ALIASES.get(str(key or "").strip().lower())
        if field and out.get(field) in (None, ""):
            out[field] = value
    return out


# EAN-13, начинающийся с 2, — внутренний код магазина: такие печатают весы на
# развес и наклейки собственного производства. Один и тот же код в разных сетях
# означает разные товары, поэтому в общий справочник им нельзя: «Абрикосы в
# корзине» из одной сети опознались бы как чужой сыр в другой.
def is_instore_code(code: str) -> bool:
    digits = normalize(code)
    return bool(digits) and digits.lstrip("0").startswith("2")


# Раздел каталога сети → наша категория. Только очевидные соответствия: пустая
# категория лечится потом (её доопределит обычный разбор при скане), а неверная
# отправит творог в «мясо» и там и останется.
CATEGORY_BY_SECTION = {
    "myasnye": "meat",
    "rybnye": "fish",
    "molochnye-prodkuty-syry-i-yayca": "dairy",
    "siry": "cheese",
    "zamorozhennye-produkty": "frozen",
    "bezalkogolnye-napitki": "drinks",
    "chaj-kofe-kakao": "drinks",
    "alkogolnaya-produkciya": "drinks",
    "bakaleya": "grains",
    "hlebobulochnye-izdeliya": "bakery",
    "konditerskie-izdeliya": "sweets",
    "konservy": "canned",
}


def _num(value):
    try:
        out = float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return out


def nutrition_is_sane(protein, fat, carbs, kcal) -> bool:
    """Сходится ли калорийность с макронутриентами.

    Допуск широкий: клетчатка, спирт и округления в этикетках дают законный
    разброс. Ловим не погрешность, а мусор вроде «жир 0, углеводы 100, 900 ккал».
    """
    if None in (protein, fat, carbs, kcal):
        return False
    if kcal <= 0:
        return False
    if min(protein, fat, carbs) < 0 or max(protein, fat, carbs) > 100:
        return False
    calculated = 4 * protein + 9 * fat + 4 * carbs
    return abs(calculated - kcal) <= max(30.0, 0.35 * kcal)


def section_of(category_path: str) -> str:
    parts = [p for p in (category_path or "").split("/") if p]
    return parts[1] if len(parts) > 1 else ""


# Разделы у сетей называются по-разному и вложены по-разному, поэтому вторая
# попытка — по ключевым словам в самом конкретном уровне («Творог и творожные
# продукты» → молочные). Список нарочно короткий: неверная категория отправит
# творог в мясо и там останется, а пустую доопределит обычный разбор при скане.
CATEGORY_BY_KEYWORD = (
    ("яйц", "eggs"),
    ("сыр", "cheese"),
    ("творог", "dairy"),
    ("молок", "dairy"),
    ("сметан", "dairy"),
    ("йогурт", "dairy"),
    ("колбас", "sausages"),
    ("сосиск", "sausages"),
    ("мяс", "meat"),
    ("птиц", "meat"),
    ("рыб", "fish"),
    ("морепродукт", "fish"),
    ("заморож", "frozen"),
    ("хлеб", "bakery"),
    ("выпечк", "bakery"),
    ("консерв", "canned"),
    ("крупа", "grains"),
    ("крупы", "grains"),
    ("макарон", "grains"),
    ("мука", "grains"),
    ("масл", "oils"),
    ("соус", "sauces"),
    ("кетчуп", "sauces"),
    ("майонез", "sauces"),
    ("специ", "condiments"),
    ("припров", "condiments"),
    ("приправ", "condiments"),
    ("конфет", "sweets"),
    ("шокол", "sweets"),
    ("печень", "sweets"),
    ("пряник", "sweets"),
    ("десерт", "sweets"),
    ("напит", "drinks"),
    ("вода", "drinks"),
    ("сок", "drinks"),
    ("кофе", "drinks"),
    ("чай", "drinks"),
    ("вино", "drinks"),
    ("пиво", "drinks"),
)


def category_slug_for(raw_category: str) -> str:
    """Наш slug категории по разделу сети. Пусто — если не уверены."""
    raw = str(raw_category or "")
    by_section = CATEGORY_BY_SECTION.get(section_of(raw))
    if by_section:
        return by_section
    # Самый конкретный уровень пути: «Каталог > … > Творог и творожные продукты».
    tail = max(raw.replace("/", ">").split(">"), key=len, default="").strip().lower()
    for word, slug in CATEGORY_BY_KEYWORD:
        if word in tail:
            return slug
    return ""


def open_rows(path: Path):
    raw = gzip.open(path, "rb") if str(path).endswith(".gz") else open(path, "rb")
    with raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


class Command(BaseCommand):
    help = "Загрузить справочники товаров со штрих-кодами (для распознавания при скане)."

    def add_arguments(self, parser):
        parser.add_argument("--file", action="append", help="CSV или CSV.GZ; можно указать несколько раз")
        parser.add_argument("--dry-run", action="store_true", help="только посчитать, ничего не писать")
        parser.add_argument("--limit", type=int, default=0, help="взять первые N строк каждого файла")

    def handle(self, *args, **opts):
        paths = [Path(f) for f in (opts["file"] or [])] or default_files()
        missing = [p for p in paths if not p.exists()]
        if missing:
            self.stderr.write("Файл не найден: " + ", ".join(str(p) for p in missing))
            return
        if not paths:
            self.stderr.write("Нечего загружать: не задан --file и нет выгрузок в reference/")
            return

        categories = {c.slug: c for c in ProductCategory.objects.filter(is_active=True)}
        totals = dict(created=0, updated=0, skipped_existing=0, dropped_kbju=0, bad_row=0, instore=0)

        with transaction.atomic():
            for path in paths:
                stats = self._load(path, categories, opts)
                for key in totals:
                    totals[key] += stats[key]
                self.stdout.write(f"  {path.name}: " + self._line(stats))

            purged = self._purge_instore(opts)
            if opts["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}ИТОГО: " + self._line(totals)))
        if purged:
            self.stdout.write(f"  убрано ранее загруженных внутренних кодов: {purged}")

    @staticmethod
    def _line(s):
        return (
            f"добавлено {s['created']}, обновлено {s['updated']}, своих не тронуто {s['skipped_existing']}, "
            f"без КБЖУ (числа не сошлись) {s['dropped_kbju']}, внутренних кодов пропущено {s['instore']}, "
            f"негодных строк {s['bad_row']}"
        )

    def _load(self, path: Path, categories: dict, opts) -> dict:
        stats = dict(created=0, updated=0, skipped_existing=0, dropped_kbju=0, bad_row=0, instore=0)

        for i, raw in enumerate(open_rows(path)):
            if opts["limit"] and i >= opts["limit"]:
                break
            row = canonical_row(raw)

            barcode = str(row.get("barcode") or "").strip()
            name = str(row.get("name") or "").strip()
            if not normalize(barcode) or not name:
                stats["bad_row"] += 1
                continue
            if is_instore_code(barcode):
                stats["instore"] += 1
                continue

            protein, fat = _num(row.get("protein")), _num(row.get("fat"))
            carbs, kcal = _num(row.get("carbs")), _num(row.get("kcal"))
            sane = nutrition_is_sane(protein, fat, carbs, kcal)
            if not sane:
                stats["dropped_kbju"] += 1

            # Запись, добытую из OpenFoodFacts или заведённую руками, не
            # переписываем: за ней стоит человек с упаковкой в руках или
            # открытая база. Дополняем только пустое КБЖУ.
            #
            # Исключение — догадка модели по коду (source=ai). Проверить её
            # нечем, а запись сети привязана к реальному артикулу, так что
            # здесь справочник заведомо лучше и заменяет её целиком.
            existing = Product.objects.filter(lookup_q(barcode)).first()
            if existing is not None and existing.source not in (Product.Source.RETAIL, Product.Source.AI):
                changes = []
                if sane and existing.calories_per_100g is None and not existing.nutrition:
                    existing.calories_per_100g = kcal
                    existing.nutrition = {"proteins": protein, "fats": fat, "carbs": carbs}
                    changes += ["calories_per_100g", "nutrition"]
                if changes and not opts["dry_run"]:
                    existing.save(update_fields=changes)
                stats["skipped_existing"] += 1
                continue

            fields = {
                "name": name[:255],
                "source": Product.Source.RETAIL,
                "default_unit": str(row.get("quantity") or "").strip()[:50],
                "calories_per_100g": kcal if sane else None,
                "nutrition": {"proteins": protein, "fats": fat, "carbs": carbs} if sane else {},
            }
            slug = category_slug_for(row.get("category"))
            if slug and slug in categories:
                fields["category_fk"] = categories[slug]

            if opts["dry_run"]:
                stats["updated" if existing else "created"] += 1
                continue

            _, was_created = Product.objects.update_or_create(barcode=barcode, defaults=fields)
            stats["created" if was_created else "updated"] += 1

        return stats

    def _purge_instore(self, opts) -> int:
        """Убрать внутренние коды, загруженные до того, как мы стали их отсеивать.

        Только записи справочника: заведённое руками и находки из OFF не трогаем,
        даже если код внутренний — там за записью стоит человек.
        """
        doomed = [
            p.id
            for p in Product.objects.filter(source=Product.Source.RETAIL).only("id", "barcode")
            if is_instore_code(p.barcode)
        ]
        if doomed and not opts["dry_run"]:
            Product.objects.filter(id__in=doomed).delete()
        return len(doomed)
