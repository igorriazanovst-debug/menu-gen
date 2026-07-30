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
