"""MG_EMAILVERIFY: добавление/смена e-mail в профиле с подтверждением по ссылке."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.email_verify import make_token
from apps.users.models import User


@pytest.fixture
def phone_user(db):
    return User.objects.create_user(phone="+79123456789", password="pass12345", name="Телефонный")


@pytest.mark.django_db
class TestSetEmail:
    def test_add_email_then_verify(self, phone_user, settings):
        settings.DEBUG = True  # чтобы verify_link вернулся в ответе (без SMTP)
        api = APIClient()
        api.force_authenticate(phone_user)

        r = api.post(reverse("users-me-set-email"), {"email": "New@Example.com"}, format="json")
        assert r.status_code == 200, r.data
        assert r.data["requires_email_verification"] is True
        assert "verify_link" in r.data

        phone_user.refresh_from_db()
        assert phone_user.email == "new@example.com"  # нормализован в нижний регистр
        assert phone_user.email_verified_at is None  # ещё не подтверждён

        # /users/me/ показывает email_verified=False
        me = api.get(reverse("users-me"))
        assert me.data["email"] == "new@example.com"
        assert me.data["email_verified"] is False

        # подтверждение по токену из ссылки
        v = api.post(reverse("auth-email-verify"), {"token": make_token(phone_user)}, format="json")
        assert v.status_code == 200
        phone_user.refresh_from_db()
        assert phone_user.is_email_verified

    def test_email_taken_by_other(self, phone_user):
        User.objects.create_user(email="taken@example.com", password="pass12345", name="Другой")
        api = APIClient()
        api.force_authenticate(phone_user)
        r = api.post(reverse("users-me-set-email"), {"email": "taken@example.com"}, format="json")
        assert r.status_code == 409
        assert r.data["code"] == "email_taken"

    def test_requires_auth(self):
        api = APIClient()
        r = api.post(reverse("users-me-set-email"), {"email": "x@example.com"}, format="json")
        assert r.status_code in (401, 403)
