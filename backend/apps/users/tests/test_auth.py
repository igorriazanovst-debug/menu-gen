import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.email_verify import make_token
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user_data():
    return {"name": "Тест Тестов", "email": "test@example.com", "password": "testpass123", "password2": "testpass123"}


def _register_and_verify(client, user_data):
    """MG_EMAILVERIFY: регистрация + подтверждение e-mail → возвращает токены."""
    client.post(reverse("auth-register"), user_data, format="json")
    user = User.objects.get(email=user_data["email"])
    token = make_token(user)
    r = client.post(reverse("auth-email-verify"), {"token": token}, format="json")
    return r.data


@pytest.mark.django_db
class TestRegister:
    def test_register_requires_verification(self, client, user_data):
        resp = client.post(reverse("auth-register"), user_data, format="json")
        assert resp.status_code == 201
        # MG_EMAILVERIFY: токены НЕ выдаются до подтверждения e-mail.
        assert "access" not in resp.data
        assert resp.data["requires_email_verification"] is True

    def test_register_no_email_or_phone(self, client):
        url = reverse("auth-register")
        resp = client.post(url, {"name": "X", "password": "pass1234", "password2": "pass1234"}, format="json")
        assert resp.status_code == 400

    def test_register_passwords_mismatch(self, client, user_data):
        url = reverse("auth-register")
        user_data["password2"] = "different"
        resp = client.post(url, user_data, format="json")
        assert resp.status_code == 400

    def test_register_duplicate_email(self, client, user_data):
        url = reverse("auth-register")
        client.post(url, user_data, format="json")
        resp = client.post(url, user_data, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestEmailVerify:
    def test_login_blocked_until_verified(self, client, user_data):
        client.post(reverse("auth-register"), user_data, format="json")
        resp = client.post(
            reverse("auth-login"),
            {"email": user_data["email"], "password": user_data["password"]},
            format="json",
        )
        assert resp.status_code == 403
        assert resp.data["code"] == "email_not_verified"

    def test_verify_then_login(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        assert "access" in tokens
        resp = client.post(
            reverse("auth-login"),
            {"email": user_data["email"], "password": user_data["password"]},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_verify_invalid_token(self, client, user_data):
        client.post(reverse("auth-register"), user_data, format="json")
        resp = client.post(reverse("auth-email-verify"), {"token": "bogus"}, format="json")
        assert resp.status_code == 400

    def test_resend_generic_ok(self, client, user_data):
        client.post(reverse("auth-register"), user_data, format="json")
        resp = client.post(reverse("auth-email-resend"), {"email": user_data["email"]}, format="json")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, client, user_data):
        _register_and_verify(client, user_data)
        resp = client.post(
            reverse("auth-login"),
            {"email": user_data["email"], "password": user_data["password"]},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_login_wrong_password(self, client, user_data):
        _register_and_verify(client, user_data)
        resp = client.post(
            reverse("auth-login"),
            {"email": user_data["email"], "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 400

    def test_login_no_credentials(self, client):
        resp = client.post(reverse("auth-login"), {"password": "x"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestRefresh:
    def test_refresh_success(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        resp = client.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data


@pytest.mark.django_db
class TestLogout:
    def test_logout_success(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]}, format="json")
        assert resp.status_code == 204

    def test_logout_reuse_refresh_fails(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]}, format="json")
        resp = client.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]}, format="json")
        assert resp.status_code == 401

    def test_logout_unauthenticated(self, client):
        resp = client.post(reverse("auth-logout"), {"refresh": "x"}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestUserMe:
    def test_me_authenticated(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = client.get(reverse("users-me"))
        assert resp.status_code == 200
        assert resp.data["email"] == user_data["email"]
        assert "profile" in resp.data

    def test_me_unauthenticated(self, client):
        resp = client.get(reverse("users-me"))
        assert resp.status_code == 401

    def test_me_update(self, client, user_data):
        tokens = _register_and_verify(client, user_data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = client.patch(
            reverse("users-me"),
            {"name": "Новое Имя", "profile": {"goal": "lose_weight"}},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["name"] == "Новое Имя"
