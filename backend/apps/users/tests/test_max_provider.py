"""MG_PHONEVERIFY/max: провайдер Max — разбор апдейтов и сверка контакта.

Формы апдейтов взяты из официальной библиотеки max-botapi (типы BotStarted,
MessageCreated, вложение contact с vcf_info/max_info). Сеть не задействуется.
"""

import pytest

from apps.users import phone_verify as pv_mod
from apps.users.messengers.handler import handle_update
from apps.users.messengers.max import MaxProvider, parse_vcf_phone
from apps.users.models import PhoneVerification

VCARD = "BEGIN:VCARD\nVERSION:3.0\nFN:Иван\nTEL;TYPE=CELL:+7 912 345-67-89\nEND:VCARD"


class TestParseVcfPhone:
    def test_extracts_phone(self):
        assert parse_vcf_phone(VCARD) == "+7 912 345-67-89"

    def test_plain_tel(self):
        assert parse_vcf_phone("BEGIN:VCARD\nTEL:+79123456789\nEND:VCARD") == "+79123456789"

    def test_item_prefixed_tel(self):
        assert parse_vcf_phone("item1.TEL;TYPE=voice:+79990001122") == "+79990001122"

    def test_no_phone(self):
        assert parse_vcf_phone("BEGIN:VCARD\nFN:Без телефона\nEND:VCARD") == ""
        assert parse_vcf_phone("") == ""


class TestParseStart:
    def setup_method(self):
        self.p = MaxProvider()

    def test_bot_started_with_payload(self):
        upd = {
            "update_type": "bot_started",
            "chat_id": 777,
            "user": {"user_id": 42, "first_name": "Иван"},
            "payload": "tok123",
        }
        assert self.p.parse_start(upd) == ("777", "tok123")

    def test_bot_started_without_payload(self):
        upd = {"update_type": "bot_started", "chat_id": 777, "user": {"user_id": 42}}
        assert self.p.parse_start(upd) == ("777", "")

    def test_text_start_command_fallback(self):
        upd = {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": 42},
                "recipient": {"chat_id": 777},
                "body": {"text": "/start tok456"},
            },
        }
        assert self.p.parse_start(upd) == ("777", "tok456")

    def test_other_update_is_none(self):
        assert self.p.parse_start({"update_type": "message_created", "message": {}}) is None


class TestParseContact:
    def setup_method(self):
        self.p = MaxProvider()

    def _update(self, *, sender_id=42, owner_id=42, vcf=VCARD):
        payload = {"vcf_info": vcf}
        if owner_id is not None:
            payload["max_info"] = {"user_id": owner_id}
        return {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": sender_id},
                "recipient": {"chat_id": 777},
                "body": {"attachments": [{"type": "contact", "payload": payload}]},
            },
        }

    def test_own_contact(self):
        share = self.p.parse_contact(self._update())
        assert share is not None
        assert share.chat_id == "777"
        assert share.from_user_id == "42"
        assert share.contact_user_id == "42"
        assert share.contact_phone == "+7 912 345-67-89"

    def test_foreign_contact_has_different_owner(self):
        share = self.p.parse_contact(self._update(sender_id=42, owner_id=99))
        assert share.from_user_id != share.contact_user_id

    def test_contact_without_max_info(self):
        """Контакт из адресной книги (не пользователь Max) — владелец неизвестен."""
        share = self.p.parse_contact(self._update(owner_id=None))
        assert share.contact_user_id is None

    def test_no_contact_attachment(self):
        upd = {"update_type": "message_created", "message": {"body": {"text": "привет"}}}
        assert self.p.parse_contact(upd) is None


class TestDeepLink:
    def test_build(self, settings):
        settings.MAX_BOT_USERNAME = "@menugen_bot"
        assert MaxProvider().build_deep_link("tok") == "https://max.ru/menugen_bot?start=tok"


# ── сквозной флоу через общий handler (провайдер-независимый) ────────────────


class _RecordingMax(MaxProvider):
    """Max-провайдер без сети: запоминает исходящие сообщения."""

    def __init__(self):
        self.sent = []
        self.contact_requests = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_request_contact(self, chat_id, text):
        self.contact_requests.append((chat_id, text))


@pytest.mark.django_db
class TestMaxFlow:
    def test_start_then_contact_verifies(self):
        pv = pv_mod.create_verification("+79123456789", "max")
        prov = _RecordingMax()

        handle_update(prov, {"update_type": "bot_started", "chat_id": 777, "payload": pv.token})
        assert prov.contact_requests, "бот должен попросить контакт"
        pv.refresh_from_db()
        assert pv.chat_id == "777"

        handle_update(
            prov,
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 42},
                    "recipient": {"chat_id": 777},
                    "body": {
                        "attachments": [
                            {"type": "contact", "payload": {"vcf_info": VCARD, "max_info": {"user_id": 42}}}
                        ]
                    },
                },
            },
        )
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.VERIFIED

    def test_foreign_contact_rejected(self):
        pv = pv_mod.create_verification("+79123456789", "max")
        prov = _RecordingMax()
        handle_update(prov, {"update_type": "bot_started", "chat_id": 778, "payload": pv.token})

        handle_update(
            prov,
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 42},
                    "recipient": {"chat_id": 778},
                    "body": {
                        "attachments": [
                            {"type": "contact", "payload": {"vcf_info": VCARD, "max_info": {"user_id": 99}}}
                        ]
                    },
                },
            },
        )
        pv.refresh_from_db()
        assert pv.status == PhoneVerification.Status.PENDING  # не подтверждён

    def test_bad_token_start(self):
        prov = _RecordingMax()
        handle_update(prov, {"update_type": "bot_started", "chat_id": 1, "payload": "нет-такого"})
        assert prov.sent and not prov.contact_requests
