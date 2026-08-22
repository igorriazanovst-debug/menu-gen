"""MG_BARCODEDB: свой справочник штрих-кодов вместо догадок модели.

Скан искал товар в OpenFoodFacts, а когда тот не знал — просил модель опознать
код. Проверить такую догадку нечем: штрих-код не несёт в себе названия, модель
угадывает в лучшем случае по префиксу страны. Справочник закрывает эту дыру, и
проверять тут надо три вещи: что запись находится, что до сети дело не доходит
и что заведомо неверные числа в дневник не попадают.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.fridge.barcodes import normalize, variants
from apps.fridge.management.commands.import_barcode_catalog import nutrition_is_sane, section_of
from apps.fridge.models import Product, ProductCategory
from apps.fridge.visibility import catalog_q
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

CSV_HEADER = "barcode,name,quantity,protein_100g,fat_100g,carbs_100g,kcal_100g,category_path,energy_macro_flag\n"
ROW_MILK = (
    "4600000000017,Молоко Простоквашино 3.2%; 930мл,930мл,2.9,3.2,4.7,59,"
    "/category/molochnye-prodkuty-syry-i-yayca,0\n"
)
ROW_BROKEN = "4600000000024,Масло оливковое Filippo Berio,500мл,0,0,100,900,/category/bakaleya,0\n"
ROW_UPC = "011210000032,Соус Tabasco красный,350мл,0.95,0.14,2.55,13,/category/bakaleya,0\n"


@pytest.fixture
def catalog_file(tmp_path):
    path = tmp_path / "catalog.csv"
    path.write_text(CSV_HEADER + ROW_MILK + ROW_BROKEN + ROW_UPC, encoding="utf-8")
    return str(path)


@pytest.fixture
def user(db):
    u = User.objects.create_user(email="bc@example.com", password="pass12345", name="Скан")
    fam = Family.objects.create(name="Семья", owner=u)
    FamilyMember.objects.create(family=fam, user=u, role="head")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": "0", "period": "month"}
    )
    import datetime

    from django.utils import timezone

    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now(),
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    return u


def api(u):
    c = APIClient()
    c.force_authenticate(u)
    return c


def scan(u, barcode):
    return api(u).post(reverse("fridge-scan"), {"barcode": barcode}, format="json")


class TestBarcodeNormalization:
    def test_короткий_код_дополняется_до_тринадцати(self):
        """UPC-A с американской упаковки и GTIN-13 из выгрузки — один товар."""
        assert normalize("011210000032") == "0011210000032"
        assert normalize("46009333") == "0000046009333"

    def test_тринадцатизначный_не_трогаем(self):
        assert normalize("4600000000017") == "4600000000017"

    def test_мусор_не_превращается_в_код(self):
        assert normalize("") == ""
        assert normalize(None) == ""
        assert normalize("abc") == ""

    def test_варианты_покрывают_оба_написания(self):
        vs = variants("011210000032")

        assert "011210000032" in vs and "0011210000032" in vs and "11210000032" in vs


class TestSanityCheck:
    def test_нормальные_числа_проходят(self):
        assert nutrition_is_sane(2.9, 3.2, 4.7, 59) is True

    def test_масло_без_жира_на_девятьсот_ккал_не_проходит(self):
        """Ровно этот мусор лежит в выгрузке — 100 г углеводов дают 400, не 900."""
        assert nutrition_is_sane(0, 0, 100, 900) is False

    def test_нулевая_калорийность_не_проходит(self):
        assert nutrition_is_sane(0, 0, 0, 0) is False

    def test_пропуски_не_проходят(self):
        assert nutrition_is_sane(1, None, 2, 100) is False

    def test_округления_этикетки_прощаем(self):
        """Клетчатка и округления дают законный разброс — это не мусор."""
        assert nutrition_is_sane(3.0, 3.0, 5.0, 70) is True

    def test_раздел_каталога_берётся_вторым_уровнем(self):
        assert section_of("/category/molochnye-prodkuty-syry-i-yayca") == "molochnye-prodkuty-syry-i-yayca"
        assert section_of("") == ""


@pytest.mark.django_db
class TestImport:
    def test_товары_заводятся_с_кбжу(self, catalog_file):
        call_command("import_barcode_catalog", file=catalog_file)

        milk = Product.objects.get(barcode="4600000000017")
        assert milk.source == Product.Source.RETAIL
        assert float(milk.calories_per_100g) == 59
        assert milk.nutrition == {"proteins": 2.9, "fats": 3.2, "carbs": 4.7}

    def test_несходящееся_кбжу_отбрасывается_а_товар_остаётся(self, catalog_file):
        """Опознать товар по коду полезно и без цифр. Неверные цифры — вредны."""
        call_command("import_barcode_catalog", file=catalog_file)

        oil = Product.objects.get(barcode="4600000000024")
        assert oil.name.startswith("Масло оливковое")
        assert oil.calories_per_100g is None and oil.nutrition == {}

    def test_категория_берётся_из_раздела_сети(self, catalog_file, db):
        ProductCategory.objects.get_or_create(slug="dairy", defaults={"name_ru": "Молочные продукты"})

        call_command("import_barcode_catalog", file=catalog_file)

        assert Product.objects.get(barcode="4600000000017").category_fk.slug == "dairy"

    def test_повторный_запуск_не_плодит_дубли(self, catalog_file):
        call_command("import_barcode_catalog", file=catalog_file)
        call_command("import_barcode_catalog", file=catalog_file)

        assert Product.objects.filter(barcode="4600000000017").count() == 1

    def test_свою_запись_не_перетирает(self, catalog_file):
        """Запись из OFF проверял человек с упаковкой в руках — она главнее."""
        Product.objects.create(name="Молоко (моё)", barcode="4600000000017", source=Product.Source.OFF)

        call_command("import_barcode_catalog", file=catalog_file)

        product = Product.objects.get(barcode="4600000000017")
        assert product.name == "Молоко (моё)"
        assert product.source == Product.Source.OFF

    def test_догадку_модели_справочник_заменяет(self, catalog_file):
        """Догадку по коду проверить нечем, а запись сети привязана к артикулу."""
        Product.objects.create(
            name="Молоко в бутылке (догадка)",
            barcode="4600000000017",
            source=Product.Source.AI,
            calories_per_100g=999,
        )

        call_command("import_barcode_catalog", file=catalog_file)

        product = Product.objects.get(barcode="4600000000017")
        assert product.name.startswith("Молоко Простоквашино")
        assert product.source == Product.Source.RETAIL
        assert float(product.calories_per_100g) == 59

    def test_но_пустое_кбжу_своей_записи_дополняет(self, catalog_file):
        Product.objects.create(name="Молоко (моё)", barcode="4600000000017", source=Product.Source.OFF)

        call_command("import_barcode_catalog", file=catalog_file)

        assert float(Product.objects.get(barcode="4600000000017").calories_per_100g) == 59

    def test_dry_run_ничего_не_пишет(self, catalog_file):
        call_command("import_barcode_catalog", file=catalog_file, dry_run=True)

        assert Product.objects.filter(source=Product.Source.RETAIL).count() == 0


@pytest.mark.django_db
class TestScan:
    @patch("apps.fridge.services.requests.get")
    def test_товар_из_справочника_находится_без_сети(self, mock_get, user, catalog_file):
        """Ради этого всё и затевалось: ни OFF, ни модель не понадобились."""
        call_command("import_barcode_catalog", file=catalog_file)

        r = scan(user, "4600000000017")

        assert r.status_code == 200, r.data
        assert r.data["name"].startswith("Молоко Простоквашино")
        assert r.data["source"] == "local"
        assert r.data["low_confidence"] is False
        assert mock_get.call_count == 0

    @patch("apps.fridge.services.requests.get")
    def test_код_с_упаковки_находит_запись_в_другом_написании(self, mock_get, user, catalog_file):
        """Сканер вернёт 12 цифр UPC-A, в выгрузке тот же товар — с нулём впереди."""
        call_command("import_barcode_catalog", file=catalog_file)
        Product.objects.filter(barcode="011210000032").update(barcode="0011210000032")

        r = scan(user, "011210000032")

        assert r.status_code == 200, r.data
        assert r.data["name"].startswith("Соус Tabasco")
        assert mock_get.call_count == 0

    @patch("apps.fridge.services.gpt_fill_nutrition", return_value=(500.0, {"proteins": 1.0}))
    @patch("apps.fridge.services.requests.get")
    def test_отброшенное_кбжу_не_дописывается_моделью(self, mock_get, mock_gpt, user, catalog_file):
        """Иначе выброшенные числа вернулись бы, только уже выдуманные."""
        call_command("import_barcode_catalog", file=catalog_file)

        r = scan(user, "4600000000024")

        assert r.status_code == 200, r.data
        assert r.data["calories_per_100g"] is None
        assert mock_gpt.call_count == 0

    @patch("apps.fridge.services.requests.get")
    def test_справочник_не_засоряет_поиск_продуктов(self, mock_get, user, catalog_file):
        """«Молоко Простоквашино 3.2%; 930мл» в автодополнении — это шум."""
        call_command("import_barcode_catalog", file=catalog_file)

        data = api(user).get(reverse("product-search"), {"q": "простоквашино"}).data
        rows = data["results"] if isinstance(data, dict) else data

        assert rows == []
        assert not Product.objects.filter(catalog_q(), barcode="4600000000017").exists()

    @patch("apps.fridge.services.requests.get")
    def test_неизвестный_код_по_прежнему_идёт_в_off(self, mock_get, user, catalog_file):
        """Справочник — первая линия, а не единственная."""
        call_command("import_barcode_catalog", file=catalog_file)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0}
        mock_get.return_value = mock_resp

        r = scan(user, "4600999999999")

        assert r.status_code == 404
        assert mock_get.call_count > 0
