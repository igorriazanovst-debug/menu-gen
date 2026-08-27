"""MG_PAYRELIABLE: активация подписки по факту оплаты.

Единственное место, где оплата превращается в подписку. Сюда приходят оба
пути — уведомление от ЮKassa и проверка статуса по возвращении пользователя, —
и оба обязаны быть безопасны при повторе.

Три правила, каждое закрывает свою дыру:

1. **Телу уведомления не верим.** Оттуда берём только идентификатор платежа, а
   статус и сумму спрашиваем у ЮKassa по API. Подделанное уведомление тогда
   бесполезно, и подписка включится даже если уведомление вовсе не дошло —
   достаточно, чтобы пользователь вернулся на сайт.

2. **Идемпотентность по строке платежа.** ЮKassa повторяет уведомление, пока не
   получит 200. Строка платежа создаётся при инициации и блокируется здесь:
   второй проход видит `succeeded` и уходит ни с чем.

3. **Сумма сверяется.** Активируем ровно тот период, за который заплачено.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Payment

log = logging.getLogger(__name__)


class ActivationError(Exception):
    """Оплату не удалось превратить в подписку."""


def fetch_remote_payment(payment_id: str) -> dict:
    """Состояние платежа у провайдера: {status, paid, amount}."""
    from django.conf import settings

    if getattr(settings, "PAYMENTS_STUB", False):
        # Заглушка: провайдера нет, «подтверждение» делает наша тестовая страница.
        return {"id": payment_id, "status": "succeeded", "paid": True, "amount": None}

    from .yookassa_client import get_payment

    return get_payment(payment_id)


def activate_payment(payment_id: str) -> Payment | None:
    """Проверяет платёж у провайдера и выдаёт подписку. Идемпотентна.

    Возвращает Payment или None, если такого платежа у нас нет.
    """
    if not payment_id:
        return None

    remote = fetch_remote_payment(payment_id)

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(payment_id=payment_id).first()
        if payment is None:
            # Платёж не наш либо строку не создали при инициации.
            log.error("activate_payment: платёж %s не найден в базе", payment_id)
            return None

        if payment.status == Payment.Status.SUCCEEDED:
            return payment  # уже активировали — повтор уведомления

        if remote.get("status") != "succeeded" or not remote.get("paid", True):
            log.info("activate_payment: платёж %s ещё не оплачен (%s)", payment_id, remote.get("status"))
            return payment

        offer = payment.offer
        if offer is None:
            log.error("activate_payment: у платежа %s не указан период", payment_id)
            raise ActivationError("У платежа не указан период подписки.")

        _check_amount(payment, remote)

        from apps.subscriptions.grant import grant_months

        subscription = grant_months(payment.family, offer.plan, offer.months)

        payment.subscription = subscription
        payment.status = Payment.Status.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.save(update_fields=["subscription", "status", "paid_at"])

        log.info(
            "Подписка выдана: семья=%s период=%s до %s (платёж %s)",
            payment.family_id,
            offer.code,
            subscription.expires_at,
            payment_id,
        )
        return payment


def _check_amount(payment: Payment, remote: dict) -> None:
    """Оплачено должно совпадать с тем, что мы выставили."""
    amount = (remote.get("amount") or {}) if isinstance(remote.get("amount"), dict) else {}
    value = amount.get("value")
    if value is None:
        return  # провайдер суммы не отдал (заглушка) — сверять нечего
    try:
        paid = Decimal(str(value))
    except (TypeError, ValueError):
        return
    if paid != payment.amount:
        log.error(
            "activate_payment: сумма платежа %s не совпала — выставлено %s, оплачено %s",
            payment.payment_id,
            payment.amount,
            paid,
        )
        raise ActivationError("Оплаченная сумма не совпадает с выставленной.")


def mark_cancelled(payment_id: str) -> None:
    Payment.objects.filter(payment_id=payment_id, status=Payment.Status.PENDING).update(status=Payment.Status.CANCELLED)


def mark_refunded(payment_id: str) -> None:
    Payment.objects.filter(payment_id=payment_id).update(status=Payment.Status.REFUNDED)
