"""MG_PAYSTUB: инициация платежа — реальная ЮKassa или тестовая заглушка.

В тестовом режиме (settings.PAYMENTS_STUB) не ходим в ЮKassa, а возвращаем
ссылку на нашу страницу «оплаты», которая имитирует весь флоу (см. views:
StubCheckoutView / StubConfirmView) и в итоге прогоняет тот же обработчик
payment.succeeded, что и реальный вебхук.
"""

import os
import uuid
from urllib.parse import urlencode

from django.conf import settings


def _backend_base() -> str:
    return (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")


def initiate_payment(family, plan, return_url: str) -> tuple[str, str]:
    """Возвращает (payment_url, payment_id)."""
    if getattr(settings, "PAYMENTS_STUB", False):
        payment_id = f"stub-{uuid.uuid4().hex}"
        params = urlencode(
            {
                "payment_id": payment_id,
                "family_id": family.id,
                "plan_code": plan.code,
                "amount": f"{float(plan.price):.2f}",
                "return_url": return_url,
            }
        )
        payment_url = f"{_backend_base()}/api/v1/payments/stub/checkout/?{params}"
        return payment_url, payment_id

    # Боевой режим — реальная ЮKassa.
    from .yookassa_client import create_payment

    return create_payment(
        amount=float(plan.price),
        description=f"Подписка {plan.name}",
        return_url=return_url,
        metadata={"family_id": family.id, "plan_code": plan.code},
    )
