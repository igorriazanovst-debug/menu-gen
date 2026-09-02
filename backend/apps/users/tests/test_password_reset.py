"""MG_PWDRESET: восстановление пароля по ссылке.

Проверяется то, что ломается молча и дорого:

* ссылка перестаёт работать после того, как ею воспользовались (иначе письмо,
  осевшее в чужом почтовом ящике, годилось бы второй раз);
* форма запроса отвечает одинаково на существующий и несуществующий адрес
  (иначе это готовый способ перебирать, кто у нас зарегистрирован);
* старый пароль перестаёт пускать, новый пускает;
* непроверенный e-mail становится проверенным — иначе человек сменил бы пароль
  и всё равно упёрся в «подтвердите e-mail»;
* телефонный аккаунт получает ссылку в мессенджер, где подтверждал номер, —
  письмо ему слать некуда, e-mail у него может не быть вовсе.

Адреса выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не пользователи — пересекаться не с чем.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.password_reset import make_token, read_token

OLD_PASSWORD = "staryi-parol-77"
NEW_PASSWORD = "novyi-parol-88"


def _user(email="zabyvchivyi@example.test", name="Забывчивый", verified=True):
    user = User.objects.create_user(email=email, name=name, password=OLD_PASSWORD)
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def _request(client, email):
    return client.post(reverse("auth-password-reset-request"), {"email": email}, format="json")


def _confirm(client, token, password=NEW_PASSWORD, password2=None):
    return client.post(
        reverse("auth-password-reset-confirm"),
        {"token": token, "password": password, "password2": password2 or password},
        format="json",
    )


@pytest.mark.django_db
def test_token_opens_only_own_account():
    user = _user()
    other = _user(email="drugoi@example.test", name="Другой")
    assert read_token(make_token(user)).id == user.id
    assert read_token(make_token(other)).id == other.id


@pytest.mark.django_db
def test_token_dies_after_password_change():
    """Ссылка одноразовая: она подписана отпечатком старого пароля."""
    user = _user()
    token = make_token(user)
    user.set_password(NEW_PASSWORD)
    user.save(update_fields=["password"])
    assert read_token(token) is None


@pytest.mark.django_db
def test_broken_token_returns_none():
    user = _user()
    token = make_token(user)
    assert read_token(token + "x") is None
    assert read_token("") is None
    assert read_token("совсем не токен") is None


@pytest.mark.django_db
def test_request_answers_the_same_for_unknown_email():
    """Форма не должна выдавать, кто у нас зарегистрирован."""
    client = APIClient()
    _user()
    known = _request(client, "zabyvchivyi@example.test")
    unknown = _request(client, "takogo-net@example.test")
    assert known.status_code == 200 and unknown.status_code == 200
    assert known.data["detail"] == unknown.data["detail"]


@pytest.mark.django_db
def test_confirm_changes_password():
    client = APIClient()
    user = _user()
    resp = _confirm(client, make_token(user))
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert not user.check_password(OLD_PASSWORD)


@pytest.mark.django_db
def test_link_works_only_once():
    client = APIClient()
    user = _user()
    token = make_token(user)
    assert _confirm(client, token).status_code == 200
    again = _confirm(client, token, password="tretii-parol-99")
    assert again.status_code == 400
    assert again.data["code"] == "invalid_token"
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_confirm_requires_matching_passwords():
    client = APIClient()
    user = _user()
    resp = _confirm(client, make_token(user), password=NEW_PASSWORD, password2="drugoe-slovo")
    assert resp.status_code == 400
    user.refresh_from_db()
    assert user.check_password(OLD_PASSWORD)


@pytest.mark.django_db
def test_confirm_rejects_short_password():
    client = APIClient()
    user = _user()
    resp = _confirm(client, make_token(user), password="abcd")
    assert resp.status_code == 400
    user.refresh_from_db()
    assert user.check_password(OLD_PASSWORD)


@pytest.mark.django_db
def test_confirm_marks_email_verified():
    client = APIClient()
    user = _user(verified=False)
    assert user.email_verified_at is None
    assert _confirm(client, make_token(user)).status_code == 200
    user.refresh_from_db()
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_new_password_lets_in_and_old_does_not():
    client = APIClient()
    user = _user()
    _confirm(client, make_token(user))

    url = reverse("auth-login")
    bad = client.post(url, {"email": user.email, "password": OLD_PASSWORD}, format="json")
    assert bad.status_code == 400
    good = client.post(url, {"email": user.email, "password": NEW_PASSWORD}, format="json")
    assert good.status_code == 200
    assert "access" in good.data


@pytest.mark.django_db
def test_reset_does_not_cancel_pending_deletion():
    """MG_ACCDEL: отменяет удаление вход, а не смена пароля.

    Иначе человек, сбросивший пароль, незаметно для себя отменял бы решение
    удалить аккаунт.
    """
    from apps.users.account_deletion import request_deletion

    client = APIClient()
    user = _user()
    request_deletion(user)
    user.refresh_from_db()
    assert user.deletion_requested_at is not None

    assert _confirm(client, make_token(user)).status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


# ── MG_PWDRESET: восстановление для телефонных аккаунтов ────────────────────
#
# У аккаунта, заведённого по телефону, e-mail может не быть вовсе — письмо
# слать некуда. Ссылка уходит в тот мессенджер, где человек делился контактом
# при регистрации: это доказательство владения номером у нас уже есть, и
# заводить ради сброса новое не нужно.

PHONE = "+79995550011"


def _phone_user(phone=PHONE, chat_id="chat-777", provider="telegram", status=None):
    """Пользователь с телефоном и подтверждённой заявкой, как после регистрации."""
    from apps.users.models import PhoneVerification

    user = User.objects.create_user(email=None, name="Телефонный", password=OLD_PASSWORD, phone=phone)
    PhoneVerification.objects.create(
        phone=phone,
        provider=provider,
        token=f"tok-{phone}-{chat_id}",
        status=status or PhoneVerification.Status.CONSUMED,
        chat_id=chat_id,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    return user


@pytest.mark.django_db
def test_messenger_target_finds_the_chat_of_the_number():
    from apps.users.password_reset import messenger_target

    _phone_user()
    pv = messenger_target(PHONE)
    assert pv is not None
    assert pv.chat_id == "chat-777"
    assert pv.provider == "telegram"


@pytest.mark.django_db
def test_messenger_target_takes_the_freshest_chat():
    """Номер подтверждали повторно — писать надо в последний диалог."""
    from apps.users.models import PhoneVerification
    from apps.users.password_reset import messenger_target

    _phone_user(chat_id="staryi-chat")
    PhoneVerification.objects.create(
        phone=PHONE,
        provider="max",
        token="tok-svezhii",
        status=PhoneVerification.Status.VERIFIED,
        chat_id="svezhii-chat",
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    pv = messenger_target(PHONE)
    assert pv.chat_id == "svezhii-chat"
    assert pv.provider == "max"


@pytest.mark.django_db
def test_messenger_target_ignores_unconfirmed_and_chatless():
    """Заявка без чата или недоведённая до конца адресом быть не может."""
    from apps.users.models import PhoneVerification
    from apps.users.password_reset import messenger_target

    PhoneVerification.objects.create(
        phone=PHONE,
        provider="telegram",
        token="tok-pending",
        status=PhoneVerification.Status.PENDING,
        chat_id="chat-pending",
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    PhoneVerification.objects.create(
        phone=PHONE,
        provider="telegram",
        token="tok-bez-chata",
        status=PhoneVerification.Status.CONSUMED,
        chat_id="",
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    assert messenger_target(PHONE) is None


@pytest.mark.django_db
def test_request_by_phone_sends_link_to_messenger(monkeypatch):
    sent = []

    class _Provider:
        enabled = True

        def send_message(self, chat_id, text):
            sent.append((chat_id, text))

    monkeypatch.setattr("apps.users.messengers.get_provider", lambda name: _Provider())

    user = _phone_user()
    client = APIClient()
    resp = client.post(reverse("auth-password-reset-request"), {"phone": "8 999 555-00-11"}, format="json")
    assert resp.status_code == 200
    assert len(sent) == 1
    chat_id, text = sent[0]
    assert chat_id == "chat-777"
    # В сообщении должна быть рабочая ссылка на смену пароля.
    assert "/reset-password?token=" in text
    token = text.split("token=")[1].split()[0]
    assert read_token(token).id == user.id


@pytest.mark.django_db
def test_request_by_phone_answers_the_same_for_unknown_number(monkeypatch):
    sent = []

    class _Provider:
        enabled = True

        def send_message(self, chat_id, text):
            sent.append(chat_id)

    monkeypatch.setattr("apps.users.messengers.get_provider", lambda name: _Provider())

    _phone_user()
    client = APIClient()
    url = reverse("auth-password-reset-request")
    known = client.post(url, {"phone": PHONE}, format="json")
    unknown = client.post(url, {"phone": "+79995559999"}, format="json")
    assert known.status_code == 200 and unknown.status_code == 200
    assert known.data["detail"] == unknown.data["detail"]
    assert sent == ["chat-777"]  # второму писать было некуда


@pytest.mark.django_db
def test_request_by_phone_survives_dead_messenger(monkeypatch):
    """Бота заблокировали — ответ прежний, 500 не отдаём."""

    class _Provider:
        enabled = True

        def send_message(self, chat_id, text):
            raise RuntimeError("bot was blocked by the user")

    monkeypatch.setattr("apps.users.messengers.get_provider", lambda name: _Provider())

    _phone_user()
    client = APIClient()
    resp = client.post(reverse("auth-password-reset-request"), {"phone": PHONE}, format="json")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_phone_account_logs_in_with_new_password(monkeypatch):
    """Весь путь целиком: ссылка из мессенджера меняет пароль, вход работает."""
    sent = []

    class _Provider:
        enabled = True

        def send_message(self, chat_id, text):
            sent.append(text)

    monkeypatch.setattr("apps.users.messengers.get_provider", lambda name: _Provider())

    _phone_user()
    client = APIClient()
    client.post(reverse("auth-password-reset-request"), {"phone": PHONE}, format="json")
    token = sent[0].split("token=")[1].split()[0]

    assert _confirm(client, token).status_code == 200

    url = reverse("auth-login")
    bad = client.post(url, {"phone": PHONE, "password": OLD_PASSWORD}, format="json")
    assert bad.status_code == 400
    good = client.post(url, {"phone": PHONE, "password": NEW_PASSWORD}, format="json")
    assert good.status_code == 200
    assert "access" in good.data
