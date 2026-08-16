"""MG_PAYSTUB / MG_PAYRELIABLE: инициация платежа.

Строка платежа создаётся ЗДЕСЬ, до похода к провайдеру. Раньше её создавал
только обработчик успеха — и пока оплата шла, у нас не было ни следа о ней:
нечего сверить, нечего показать пользователю, нечем восстановиться, если
уведомление не дойдёт.

В тестовом режиме (settings.PAYMENTS_STUB) провайдера нет — ссылка ведёт на
нашу страницу-имитацию, которая проходит ровно тот же путь активации.
"""

import os
import uuid
from urllib.parse import urlencode

from django.conf import settings

from .models import Payment


def _backend_base() -> str:
    return (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")


def initiate_payment(family, offer, return_url: str, user=None) -> tuple[str, str]:
    """Создаёт платёж под покупку `offer`. Возвращает (payment_url, payment_id)."""
    amount = offer.price

    if getattr(settings, "PAYMENTS_STUB", False):
        payment_id = f"stub-{uuid.uuid4().hex}"
        payment_url = _stub_url(payment_id, offer, return_url)
    else:
        from .yookassa_client import create_payment

        payment_url, payment_id = create_payment(
            amount=amount,
            description=f"Подписка MenuGen — {offer.title}",
            return_url=return_url,
            metadata={"family_id": family.id, "offer_code": offer.code},
            customer_email=(getattr(user, "email", "") or "").strip() or None,
        )

    Payment.objects.create(
        family=family,
        offer=offer,
        amount=amount,
        status=Payment.Status.PENDING,
        payment_id=payment_id,
    )
    return payment_url, payment_id


def _stub_url(payment_id: str, offer, return_url: str) -> str:
    params = urlencode(
        {
            "payment_id": payment_id,
            "offer_code": offer.code,
            "amount": f"{float(offer.price):.2f}",
            "return_url": return_url,
        }
    )
    return f"{_backend_base()}/api/v1/payments/stub/checkout/?{params}"
