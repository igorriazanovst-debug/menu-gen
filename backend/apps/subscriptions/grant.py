"""MG_PAYRELIABLE: выдача премиума за оплату.

Отдельно от вьюх и от платежей: подписку продлевают три разных повода —
оплата, промокод и рука администратора, а правило должно быть одно.

Главное правило: продлеваем **от текущей даты окончания**, а не от «сейчас».
Иначе человек, оплативший за неделю до конца, эту неделю теряет.
"""

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from .models import Subscription


def grant_months(family, plan, months: int) -> Subscription:
    """Продлевает (или создаёт) подписку семьи на `months` месяцев.

    Возвращает Subscription. Вызывать внутри транзакции вызывающего кода.
    """
    now = timezone.now()
    delta = relativedelta(months=months)

    current = (
        Subscription.objects.select_for_update()
        .filter(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            expires_at__gt=now,
        )
        .order_by("-expires_at")
        .first()
    )

    if current:
        current.expires_at = current.expires_at + delta
        current.save(update_fields=["expires_at"])
        return current

    return Subscription.objects.create(
        family=family,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=now,
        expires_at=now + delta,
        # Автопродления пока нет: списывать без спроса мы не умеем и не обещаем.
        auto_renew=False,
    )


def grant_for_offer(family, offer) -> Subscription:
    with transaction.atomic():
        return grant_months(family, offer.plan, offer.months)
