"""MG_PHONEVERIFY: тесты подтверждения телефона и регистрации по нему.

Провайдер мессенджера замокан — реальный Telegram API не дёргается. Проверяем:
нормализацию номера, сверку контакта (свой/чужой/несовпал), эндпоинты
start/status/register и вход по паролю после регистрации.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users import phone_verify as pv_mod
from apps.users.messengers.handler import handle_update
from apps.users.models import PhoneVerification, User


@pytest.fixture
def client():
    return APIClient()


# ── нормализация ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+7 (912) 345-67-89", "+79123456789"),
        ("89123456789", "+79123456789"),
        ("9123456789", "+79123456789"),
        ("+79123456789", "+79123456789"),
        ("+8 912 345 67 89", "+79123456789"),
    ],
)
def test_normalize_phone(raw, expected):
    assert pv_mod.normalize_phone(raw) == expected


def test_phones_match():
    assert pv_mod.phones_match("89123456789", "+7 912 345 67 89")
    assert not pv_mod.phones_match("89123456789", "89120000000")


# ── логика сверки контакта ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestApplyContact:
    def _pv(self, phone="+79123456789"):
        return pv_mod.create_verification(phone, "telegram")

    def test_own_matching_contact_verified(self):
        pv = self._pv()
        res = pv_mod.apply_shared_contact(pv, contact_phone="89123456789", contact_user_id="42", from_user_id="42")
        assert res == "verified"
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.VERIFIED
        assert pv.verified_at is not None

    def test_foreign_contact_rejected(self):
        pv = self._pv()
        res = pv_mod.apply_shared_contact(pv, contact_phone="89123456789", contact_user_id="99", from_user_id="42")
        assert res == "rejected"
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.PENDING  # остаётся ждать

    def test_own_but_mismatch(self):
        pv = self._pv()
        res = pv_mod.apply_shared_contact(pv, contact_phone="89990001122", contact_user_id="42", from_user_id="42")
        assert res == "mismatch"
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.MISMATCH
        assert pv.messenger_phone == "+79990001122"


# ── обработчик апдейтов (провайдер-абстракция, Telegram-формат) ───────────────


class _FakeProvider:
    """Мок провайдера: копит исходящие вызовы, парсит Telegram-подобный update."""

    name = "telegram"

    def __init__(self):
        self.sent = []
        self.contact_requests = []

    def parse_start(self, update):
        msg = update.get("message") or {}
        text = msg.get("text") or ""
        if not text.startswith("/start"):
            return None
        parts = text.split(maxsplit=1)
        return (str(msg["chat"]["id"]), parts[1] if len(parts) > 1 else "")

    def parse_contact(self, update):
        from apps.users.messengers.base import ContactShare

        msg = update.get("message") or {}
        c = msg.get("contact")
        if not c:
            return None
        return ContactShare(
            token="",
            chat_id=str(msg["chat"]["id"]),
            from_user_id=str(msg["from"]["id"]),
            contact_user_id=(str(c["user_id"]) if c.get("user_id") is not None else None),
            contact_phone=c.get("phone_number") or "",
        )

    def send_request_contact(self, chat_id, text):
        self.contact_requests.append((str(chat_id), text))

    def send_message(self, chat_id, text):
        self.sent.append((str(chat_id), text))


@pytest.mark.django_db
class TestHandler:
    def test_full_verify_via_handler(self):
        pv = pv_mod.create_verification("+79123456789", "telegram")
        prov = _FakeProvider()

        # /start <token> → просим контакт, чат привязан
        handle_update(prov, {"message": {"chat": {"id": 555}, "text": f"/start {pv.token}"}})
        assert prov.contact_requests, "должны попросить поделиться контактом"
        pv.refresh_from_db()
        assert pv.chat_id == "555"

        # контакт (свой, совпадает) → verified
        handle_update(
            prov,
            {
                "message": {
                    "chat": {"id": 555},
                    "from": {"id": 555},
                    "contact": {"user_id": 555, "phone_number": "+79123456789"},
                }
            },
        )
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.VERIFIED

    def test_bad_token_start(self):
        prov = _FakeProvider()
        handle_update(prov, {"message": {"chat": {"id": 1}, "text": "/start nope"}})
        assert prov.sent, "должны ответить про недействительную ссылку"
        assert not prov.contact_requests


# ── эндпоинты ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEndpoints:
    @pytest.fixture(autouse=True)
    def _bot_settings(self, settings):
        settings.TELEGRAM_BOT_TOKEN = "test-token"
        settings.TELEGRAM_BOT_USERNAME = "menugen_bot"

    def test_start_returns_deep_link(self, client):
        r = client.post(
            reverse("auth-phone-start"),
            {"phone": "89123456789", "provider": "telegram"},
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["deep_link"].startswith("https://t.me/menugen_bot?start=")
        assert PhoneVerification.objects.filter(token=r.data["token"]).exists()

    def test_start_rejects_existing_phone(self, client):
        User.objects.create_user(phone="+79123456789", password="pass12345", name="Ex")
        r = client.post(reverse("auth-phone-start"), {"phone": "89123456789"}, format="json")
        assert r.status_code == 409

    def test_status_flow(self, client):
        r = client.post(reverse("auth-phone-start"), {"phone": "89123456789"}, format="json")
        token = r.data["token"]
        s = client.get(reverse("auth-phone-status"), {"token": token})
        assert s.data["status"] == "pending"

    def test_register_requires_verified(self, client):
        r = client.post(reverse("auth-phone-start"), {"phone": "89123456789"}, format="json")
        token = r.data["token"]
        reg = client.post(
            reverse("auth-phone-register"),
            {"token": token, "name": "Ivan", "password": "pass12345", "password2": "pass12345"},
            format="json",
        )
        assert reg.status_code == 400
        assert reg.data["code"] == "not_verified"

    def test_full_register_and_login(self, client):
        # start
        r = client.post(reverse("auth-phone-start"), {"phone": "89123456789"}, format="json")
        token = r.data["token"]
        # verify (через логику сверки напрямую)
        pv = PhoneVerification.objects.get(token=token)
        pv_mod.apply_shared_contact(pv, contact_phone="89123456789", contact_user_id="7", from_user_id="7")
        # status → verified
        s = client.get(reverse("auth-phone-status"), {"token": token})
        assert s.data["status"] == "verified"
        # register → tokens
        reg = client.post(
            reverse("auth-phone-register"),
            {"token": token, "name": "Ivan", "password": "pass12345", "password2": "pass12345"},
            format="json",
        )
        assert reg.status_code == 201, reg.data
        assert "access" in reg.data
        user = User.objects.get(phone="+79123456789")
        assert user.email is None
        # заявка использована
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.CONSUMED

        # вход по телефону+паролю (phone-only)
        login = client.post(
            reverse("auth-login"),
            {"phone": "+7 912 345 67 89", "password": "pass12345"},
            format="json",
        )
        assert login.status_code == 200, login.data
        assert "access" in login.data

        # неверный пароль
        bad = client.post(
            reverse("auth-login"),
            {"phone": "89123456789", "password": "wrong"},
            format="json",
        )
        assert bad.status_code == 400
