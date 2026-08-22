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

Запуск:
    python manage.py import_barcode_catalog                 # файл из репозитория
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
DEFAULT_FILE = Path(__file__).resolve().parents[2] / "reference" / "barcode_catalog.csv.gz"

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


def open_rows(path: Path):
    raw = gzip.open(path, "rb") if str(path).endswith(".gz") else open(path, "rb")
    with raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


class Command(BaseCommand):
    help = "Загрузить справочник товаров со штрих-кодами (для распознавания при скане)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_FILE), help="CSV или CSV.GZ с выгрузкой")
        parser.add_argument("--dry-run", action="store_true", help="только посчитать, ничего не писать")
        parser.add_argument("--limit", type=int, default=0, help="взять первые N строк (для проверки)")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            self.stderr.write(f"Файл не найден: {path}")
            return

        categories = {c.slug: c for c in ProductCategory.objects.filter(is_active=True)}
        created = updated = skipped_existing = dropped_kbju = bad_barcode = 0

        with transaction.atomic():
            for i, row in enumerate(open_rows(path)):
                if opts["limit"] and i >= opts["limit"]:
                    break

                barcode = (row.get("barcode") or row.get("gtin") or "").strip()
                name = (row.get("name") or "").strip()
                if not normalize(barcode) or not name:
                    bad_barcode += 1
                    continue

                protein, fat = _num(row.get("protein_100g")), _num(row.get("fat_100g"))
                carbs, kcal = _num(row.get("carbs_100g")), _num(row.get("kcal_100g"))
                sane = nutrition_is_sane(protein, fat, carbs, kcal)
                if not sane:
                    dropped_kbju += 1

                # Запись, добытую из OpenFoodFacts или заведённую руками, не
                # переписываем: за ней стоит человек с упаковкой в руках или
                # открытая база. Дополняем только пустое КБЖУ.
                #
                # Исключение — догадка модели по коду (source=ai). Проверить её
                # нечем, а запись сети привязана к реальному артикулу, так что
                # здесь справочник заведомо лучше и заменяет её целиком.
                existing = Product.objects.filter(lookup_q(barcode)).first()
                if existing is not None:
                    if existing.source not in (Product.Source.RETAIL, Product.Source.AI):
                        changes = []
                        if sane and existing.calories_per_100g is None and not existing.nutrition:
                            existing.calories_per_100g = kcal
                            existing.nutrition = {"proteins": protein, "fats": fat, "carbs": carbs}
                            changes += ["calories_per_100g", "nutrition"]
                        if changes and not opts["dry_run"]:
                            existing.save(update_fields=changes)
                        skipped_existing += 1
                        continue

                fields = {
                    "name": name[:255],
                    "source": Product.Source.RETAIL,
                    "default_unit": (row.get("quantity") or "").strip()[:50],
                    "calories_per_100g": kcal if sane else None,
                    "nutrition": {"proteins": protein, "fats": fat, "carbs": carbs} if sane else {},
                }
                slug = CATEGORY_BY_SECTION.get(section_of(row.get("category_path", "")))
                if slug and slug in categories:
                    fields["category_fk"] = categories[slug]

                if opts["dry_run"]:
                    created += 0 if existing else 1
                    updated += 1 if existing else 0
                    continue

                _, was_created = Product.objects.update_or_create(barcode=barcode, defaults=fields)
                created += 1 if was_created else 0
                updated += 0 if was_created else 1

            if opts["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if opts["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}добавлено {created}, обновлено {updated}, "
                f"своих не тронуто {skipped_existing}, без КБЖУ (числа не сошлись) {dropped_kbju}, "
                f"пропущено строк {bad_barcode}"
            )
        )
