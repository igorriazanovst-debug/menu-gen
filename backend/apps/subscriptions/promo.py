"""Логика промокодов: генерация кодов и активация подписки по коду.

Активация переиспользует ту же модель выдачи, что и оплата (payments):
`Subscription(status=active)` с расчётом срока по периоду плана — но с поддержкой
произвольного срока в днях (PromoCode.duration_days) и продления уже активной
подписки (срок стекуется поверх текущего).
"""

import secrets
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from .models import PromoCode, PromoRedemption, Subscription, SubscriptionPlan

# Алфавит без визуально похожих символов (0/O, 1/I/L).
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class PromoError(Exception):
    """Ошибка активации промокода (сообщение — для пользователя)."""


def generate_code(prefix: str = "") -> str:
    """Случайный код вида PREFIXABCD-EFGH-JKLM."""
    body = "-".join("".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3))
    return f"{(prefix or '').strip().upper()}{body}"


def generate_unique_codes(count: int, prefix: str = "") -> list[str]:
    """Список из `count` уникальных (в БД и между собой) кодов."""
    result: set[str] = set()
    existing = set(PromoCode.objects.values_list("code", flat=True))
    while len(result) < count:
        c = generate_code(prefix)
        if c in existing or c in result:
            continue
        result.add(c)
    return list(result)


def _duration_delta(promo: PromoCode):
    if promo.duration_days:
        return timedelta(days=promo.duration_days)
    if promo.plan.period == SubscriptionPlan.Period.MONTH:
        return relativedelta(months=1)
    return relativedelta(years=1)


def redeem(code_str: str, family, user):
    """Активировать промокод на семью. Возвращает Subscription или бросает PromoError."""
    code_str = (code_str or "").strip().upper()
    if not code_str:
        raise PromoError("Введите промокод.")
    if family is None:
        raise PromoError("Семья не найдена.")

    with transaction.atomic():
        try:
            promo = PromoCode.objects.select_for_update().get(code=code_str)
        except PromoCode.DoesNotExist:
            raise PromoError("Промокод не найден.")

        if not promo.is_redeemable:
            raise PromoError("Промокод недействителен, просрочен или уже полностью использован.")
        # Именной код: активировать может только закреплённый пользователь (по email).
        if promo.assigned_email:
            user_email = (getattr(user, "email", "") or "").strip().lower()
            if user_email != promo.assigned_email.strip().lower():
                raise PromoError("Этот промокод закреплён за другим пользователем.")
        if PromoRedemption.objects.filter(promo=promo, family=family).exists():
            raise PromoError("Этот промокод уже активирован в вашей семье.")

        now = timezone.now()
        delta = _duration_delta(promo)

        # Есть активная неистёкшая подписка — продлеваем (стекуем срок), иначе создаём новую.
        active = (
            Subscription.objects.filter(family=family, status=Subscription.Status.ACTIVE)
            .order_by("-expires_at")
            .first()
        )
        if active and active.expires_at and active.expires_at > now:
            active.expires_at = active.expires_at + delta
            active.save(update_fields=["expires_at"])
            sub = active
        else:
            sub = Subscription.objects.create(
                family=family,
                plan=promo.plan,
                status=Subscription.Status.ACTIVE,
                started_at=now,
                expires_at=now + delta,
                auto_renew=False,  # промо не привязано к оплате — без автосписания
            )

        promo.redeemed_count += 1
        promo.save(update_fields=["redeemed_count"])
        PromoRedemption.objects.create(promo=promo, family=family, user=user, subscription=sub)
        return sub


def revoke_redemption(redemption, mode: str):
    """Отозвать конкретную активацию.

    mode="free"  — снять премиум: выданную подписку переводим в EXPIRED (семья
                   откатывается на бесплатный тариф).
    mode="block" — то же + блокировка ВСЕЙ семьи (is_active=False у всех
                   участников) «до последующих решений» (staff/суперпользователей
                   не трогаем).
    """
    from apps.family.models import FamilyMember

    now = timezone.now()
    sub = redemption.subscription
    if sub is not None and sub.status != Subscription.Status.EXPIRED:
        sub.status = Subscription.Status.EXPIRED
        sub.expires_at = now
        sub.auto_renew = False
        sub.save(update_fields=["status", "expires_at", "auto_renew"])

    if mode == "block":
        members = FamilyMember.objects.filter(family=redemption.family).select_related("user")
        for m in members:
            u = m.user
            if u is not None and not u.is_superuser and not u.is_staff and u.is_active:
                u.is_active = False
                u.save(update_fields=["is_active"])

    redemption.revoked_at = now
    redemption.revoke_mode = mode
    redemption.save(update_fields=["revoked_at", "revoke_mode"])


def revoke_code(promo, mode: str):
    """Отозвать код целиком: деактивировать и отозвать все его активации."""
    with transaction.atomic():
        if promo.is_active:
            promo.is_active = False
            promo.save(update_fields=["is_active"])
        for r in promo.redemptions.select_related("subscription", "user"):
            revoke_redemption(r, mode)
