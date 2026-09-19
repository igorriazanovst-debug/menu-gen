import datetime
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone


def pytest_configure(config):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.REST_FRAMEWORK = {
        **getattr(settings, "REST_FRAMEWORK", {}),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }


@pytest.fixture
def grant_premium(db):
    """Выдать семье активный Premium.

    Почти весь холодильник и всё меню закрыты `IsFamilyPremiumOrReadOnly`, а
    регистрация заводит Free-подписку — значит тест, который ходит в эти ручки
    от нового пользователя, получит 403, и выглядеть это будет как сломанные
    права. Раньше каждый такой тест выписывал план и подписку у себя; здесь
    одно место на всех.
    """

    def _grant(family, days: int = 30):
        from apps.subscriptions.models import Subscription, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium", defaults={"name": "Premium", "price": Decimal("0")}
        )
        return Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - datetime.timedelta(days=1),
            expires_at=timezone.now() + datetime.timedelta(days=days),
        )

    return _grant
