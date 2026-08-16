"""Тонкая обёртка над ЮKassa SDK.

Все реквизиты берутся из переменных окружения — ничего не хардкодится.
"""

import uuid
from decimal import Decimal

import yookassa
from decouple import config
from django.conf import settings
from yookassa import Payment as YKPayment
from yookassa.domain.exceptions import ApiError


def _configure():
    yookassa.Configuration.account_id = config("YOOKASSA_SHOP_ID")
    yookassa.Configuration.secret_key = config("YOOKASSA_SECRET_KEY")


def build_receipt(amount: Decimal, description: str, customer_email: str | None) -> dict | None:
    """MG_PAYRECEIPT: чек по 54-ФЗ.

    ЮKassa пробивает и отправляет чек сама, но данные для него передаём мы:
    позиция, сумма, ставка НДС и контакт покупателя. Без контакта чек отправить
    некуда, поэтому без e-mail чек не формируем — платёж пройдёт, а расхождение
    будет видно в кабинете ЮKassa.

    Ставка НДС и признаки предмета/способа расчёта зависят от системы
    налогообложения — задаются в .env, а не в коде.
    """
    if not getattr(settings, "PAYMENTS_RECEIPT_ENABLED", False):
        return None
    if not customer_email:
        return None

    return {
        "customer": {"email": customer_email},
        "items": [
            {
                "description": description[:128],
                "quantity": "1.00",
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "vat_code": getattr(settings, "PAYMENTS_RECEIPT_VAT_CODE", 1),
                "payment_subject": getattr(settings, "PAYMENTS_RECEIPT_SUBJECT", "service"),
                "payment_mode": getattr(settings, "PAYMENTS_RECEIPT_MODE", "full_prepayment"),
            }
        ],
    }


def create_payment(
    amount: Decimal,
    description: str,
    return_url: str,
    metadata: dict,
    customer_email: str | None = None,
) -> tuple[str, str]:
    """Создаёт платёж в ЮKassa. Возвращает (confirmation_url, payment_id)."""
    _configure()
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    receipt = build_receipt(amount, description, customer_email)
    if receipt:
        payload["receipt"] = receipt

    # Ключ идемпотентности: повтор запроса не создаст второй платёж.
    payment = YKPayment.create(payload, str(uuid.uuid4()))
    return payment.confirmation.confirmation_url, payment.id


def get_payment(payment_id: str) -> dict:
    """Состояние платежа у ЮKassa — источник правды при активации."""
    _configure()
    try:
        payment = YKPayment.find_one(payment_id)
    except ApiError as exc:
        raise ValueError(f"ЮKassa API error: {exc}") from exc

    amount = getattr(payment, "amount", None)
    return {
        "id": payment.id,
        "status": payment.status,
        "paid": payment.paid,
        "amount": (
            {"value": getattr(amount, "value", None), "currency": getattr(amount, "currency", None)}
            if amount is not None
            else None
        ),
    }
