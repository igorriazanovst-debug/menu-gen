import datetime

import pytest
from django.utils import timezone

from apps.family.models import Family, FamilyMember
from apps.fridge.models import FridgeItem
from apps.menu.models import Menu
from apps.notifications.models import Notification
from apps.notifications.tasks import check_fridge_expiry, expire_subscriptions, send_menu_reminder
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def user_with_family(db):
    user = User.objects.create_user(email="task@example.com", name="Юзер", password="pass")
    family = Family.objects.create(owner=user)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return user, family, member


@pytest.mark.django_db
class TestCheckFridgeExpiry:
    def test_creates_notification_for_expiring(self, user_with_family):
        user, family, _ = user_with_family
        FridgeItem.objects.create(
            family=family,
            name="Молоко",
            expiry_date=timezone.now().date() + datetime.timedelta(days=1),
        )
        result = check_fridge_expiry.apply().get()
        assert result == 1
        assert Notification.objects.filter(user=user, notification_type=Notification.Type.FRIDGE_EXPIRY).exists()

    def test_no_notification_for_fresh(self, user_with_family):
        user, family, _ = user_with_family
        FridgeItem.objects.create(
            family=family,
            name="Сыр",
            expiry_date=timezone.now().date() + datetime.timedelta(days=30),
        )
        result = check_fridge_expiry.apply().get()
        assert result == 0

    def test_no_duplicate_notification_same_day(self, user_with_family):
        user, family, _ = user_with_family
        item = FridgeItem.objects.create(
            family=family,
            name="Кефир",
            expiry_date=timezone.now().date() + datetime.timedelta(days=1),
        )
        check_fridge_expiry.apply().get()
        check_fridge_expiry.apply().get()
        assert (
            Notification.objects.filter(
                user=user,
                notification_type=Notification.Type.FRIDGE_EXPIRY,
                action_url="/fridge/{}/".format(item.id),
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestExpireSubscriptions:
    def test_expires_old_subscription(self, user_with_family):
        _, family, _ = user_with_family
        plan = SubscriptionPlan.objects.create(code="basic_exp", name="Basic", price="199", period="month")
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - datetime.timedelta(days=60),
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        result = expire_subscriptions.apply().get()
        assert result == 1
        assert Subscription.objects.get(family=family).status == Subscription.Status.EXPIRED

    def test_does_not_expire_active(self, user_with_family):
        _, family, _ = user_with_family
        plan = SubscriptionPlan.objects.create(code="prem_exp", name="Premium", price="499", period="month")
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        result = expire_subscriptions.apply().get()
        assert result == 0


@pytest.mark.django_db
class TestSendMenuReminder:
    def test_sends_reminder_without_menu(self, user_with_family):
        user, _, _ = user_with_family
        result = send_menu_reminder.apply().get()
        assert result >= 1
        assert Notification.objects.filter(user=user, notification_type=Notification.Type.MENU_READY).exists()

    def test_no_reminder_with_active_menu(self, user_with_family):
        _, family, _ = user_with_family
        today = timezone.now().date()
        Menu.objects.create(
            family=family,
            creator_id=family.owner_id,
            period_days=7,
            start_date=today,
            end_date=today + datetime.timedelta(days=6),
            status=Menu.Status.ACTIVE,
        )
        result = send_menu_reminder.apply().get()
        assert result == 0
