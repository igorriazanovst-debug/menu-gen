"""
Тонкая обёртка над ЮKassa SDK.
Все реквизиты берутся из переменных окружения — ничего не хардкодится.
"""
import uuid
from decouple import config

import yookassa
from yookassa import Payment as YKPayment
from yookassa.domain.exceptions import ApiError


def _configure():
    yookassa.Configuration.account_id = config("YOOKASSA_SHOP_ID")
    yookassa.Configuration.secret_key = config("YOOKASSA_SECRET_KEY")


def create_payment(amount: float, description: str, return_url: str, metadata: dict) -> tuple[str, str]:
    """
    Создаёт платёж в ЮKassa.
    Возвращает (confirmation_url, payment_id).
    """
    _configure()
    payment = YKPayment.create({
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }, uuid.uuid4())
    return payment.confirmation.confirmation_url, payment.id


def get_payment(payment_id: str) -> dict:
    """Возвращает статус платежа из ЮKassa."""
    _configure()
    try:
        payment = YKPayment.find_one(payment_id)
        return {"id": payment.id, "status": payment.status, "paid": payment.paid}
    except ApiError as exc:
        raise ValueError(f"ЮKassa API error: {exc}") from exc
