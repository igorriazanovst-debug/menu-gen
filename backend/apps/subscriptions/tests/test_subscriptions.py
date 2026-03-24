import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User
from django.utils import timezone
import datetime


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="sub@example.com", name="Юзер", password="pass1234")
    family = Family.objects.create(owner=user)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    plan = SubscriptionPlan.objects.create(
        code="basic", name="Basic", price="199.00", period="month",
        is_active=True, max_family_members=1,
    )
    return user, family, plan


@pytest.mark.django_db
class TestPlanList:
    def test_list_public(self, client, setup):
        resp = client.get(reverse("subscription-plans"))
        assert resp.status_code == 200
        assert len(resp.data) >= 1

    def test_inactive_plan_hidden(self, client, setup):
        _, _, plan = setup
        plan.is_active = False
        plan.save()
        resp = client.get(reverse("subscription-plans"))
        assert all(p["code"] != "basic" for p in resp.data)


@pytest.mark.django_db
class TestCurrentSubscription:
    def test_no_subscription(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.get(reverse("subscription-current"))
        assert resp.status_code == 404

    def test_with_subscription(self, client, setup):
        user, family, plan = setup
        Subscription.objects.create(
            family=family, plan=plan, status=Subscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        client.force_authenticate(user)
        resp = client.get(reverse("subscription-current"))
        assert resp.status_code == 200
        assert resp.data["plan"]["code"] == "basic"


@pytest.mark.django_db
class TestCancelSubscription:
    def test_cancel(self, client, setup):
        user, family, plan = setup
        Subscription.objects.create(
            family=family, plan=plan, status=Subscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + datetime.timedelta(days=30),
            auto_renew=True,
        )
        client.force_authenticate(user)
        resp = client.post(reverse("subscription-cancel"))
        assert resp.status_code == 200
        assert not Subscription.objects.get(family=family).auto_renew

    def test_cancel_no_subscription(self, client, setup):
        user, _, _ = setup
        client.force_authenticate(user)
        resp = client.post(reverse("subscription-cancel"))
        assert resp.status_code == 404
