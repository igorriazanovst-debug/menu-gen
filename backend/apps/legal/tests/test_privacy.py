"""MG_PRIVACY: политика обработки ПД в публичном API /legal/."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.legal.models import LegalInfo


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestPrivacyInApi:
    def test_own_text_wins(self, client):
        legal = LegalInfo.load()
        legal.privacy_text = "Наш собственный текст политики."
        legal.save()

        r = client.get(reverse("legal-info"))
        assert r.status_code == 200
        assert r.data["privacy_text"] == "Наш собственный текст политики."

    def test_default_text_when_empty(self, client):
        """Пустое поле → типовой текст, а не пустая страница."""
        legal = LegalInfo.load()
        legal.privacy_text = ""
        legal.company_name = "ИП Тестов Тест Тестович"
        legal.inn = "1234567890"
        legal.legal_address = "г. Москва, ул. Тестовая, 1"
        legal.email = "privacy@example.com"
        legal.save()

        r = client.get(reverse("legal-info"))
        assert r.status_code == 200
        text = r.data["privacy_text"]
        # Ключевые разделы 152-ФЗ на месте
        assert "152-ФЗ" in text
        assert "ЦЕЛИ ОБРАБОТКИ" in text
        assert "ПЕРЕДАЧА ДАННЫХ ТРЕТЬИМ ЛИЦАМ" in text
        # Реквизиты подставлены
        assert "ИП Тестов Тест Тестович" in text
        assert "1234567890" in text
        assert "privacy@example.com" in text

    def test_default_marks_missing_requisites(self, client):
        """Незаполненные реквизиты видны как подсказка, а не пустое место."""
        legal = LegalInfo.load()
        legal.privacy_text = ""
        legal.company_name = ""
        legal.inn = ""
        legal.legal_address = ""
        legal.email = ""
        legal.save()

        r = client.get(reverse("legal-info"))
        assert "заполните в админке" in r.data["privacy_text"]

    def test_privacy_is_read_only_via_api(self, client):
        """Публичный эндпоинт только читает (правка — через админку)."""
        r = client.post(reverse("legal-info"), {"privacy_text": "hack"}, format="json")
        assert r.status_code in (401, 403, 405)


@pytest.mark.django_db
class TestPrivacyCoversActualProcessing:
    """MG_PRIVACYSYNC: политика должна описывать то, что код реально делает.

    Расхождение здесь — не косметика: анкету магазина и текст политики сверяет
    модератор, а по 152-ФЗ нераскрытая передача данных третьим лицам это
    нарушение. Проверки ниже — про три случая, которых в тексте не было, хотя
    в коде они есть давно.
    """

    def text(self):
        from apps.legal.privacy_default import default_privacy_text

        legal = LegalInfo.load()
        return default_privacy_text(legal)

    def test_доступ_специалиста_описан(self):
        """Диетолог получает профили, дневник и меню семьи — молчать нельзя."""
        text = self.text()

        assert "специалист" in text.lower()
        assert "Мои специалисты" in text  # где прекратить доступ
        assert "дневник питания" in text.lower()

    def test_названы_оба_мессенджера(self):
        """Подтверждение телефона работает и через Telegram, и через Max."""
        text = self.text()

        assert "Telegram" in text
        assert "Max" in text

    def test_передача_штрихкода_описана(self):
        """Ненайденный товар ищется во внешнем справочнике продуктов."""
        text = self.text()

        assert "штрихкод" in text.lower()

    def test_платёжные_реквизиты_по_прежнему_не_наши(self):
        """Карты обрабатывает ЮKassa — это должно оставаться сказанным прямо."""
        text = self.text()

        assert "Реквизиты банковских карт Оператором не собираются" in text
