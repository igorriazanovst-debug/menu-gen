"""MG_SPECINVITE: личный код специалиста.

Приглашение работает с двух сторон. Со стороны клиента — по e-mail специалиста
(было раньше). Со стороны специалиста — своим кодом: он даёт его клиенту, тот
вводит код и получает месяц премиума, а специалист сразу получает доступ.

Ввод кода и есть согласие клиента: он вводит его сам, добровольно и в свою
семью. Подтверждения со стороны специалиста тоже не ждём — код выпустил он.
Прекратить доступ клиент может в любой момент, и это важнее лишнего шага при
подключении.

Код — обычный PromoCode: там уже есть срок в днях, счётчик активаций, срок
годности и защита от повторной активации в той же семье. Связь «код → чей он»
живёт здесь, а не в subscriptions: подписки ничего не знают про специалистов и
знать не должны.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

# Месяц премиума клиенту — как договаривались.
INVITE_DAYS = 30
# Столько раз кодом можно воспользоваться. Код личный и многоразовый: специалист
# даёт его каждому новому клиенту, а не выпускает новый под каждого.
INVITE_MAX_REDEMPTIONS = 100
CODE_PREFIX = "SP-"


def _premium_plan():
    from apps.subscriptions.models import SubscriptionPlan

    return SubscriptionPlan.objects.filter(code="premium").first()


def get_or_create_code(specialist):
    """Личный код специалиста. Создаёт при первом обращении."""
    from apps.subscriptions.models import PromoCode
    from apps.subscriptions.promo import generate_unique_codes

    from .models import SpecialistInviteCode

    existing = SpecialistInviteCode.objects.filter(specialist=specialist).select_related("promo").first()
    if existing:
        return existing

    plan = _premium_plan()
    if plan is None:
        raise RuntimeError("Не найден тариф premium — код выпустить не из чего.")

    with transaction.atomic():
        code = generate_unique_codes(1, prefix=CODE_PREFIX)[0]
        promo = PromoCode.objects.create(
            code=code,
            plan=plan,
            duration_days=INVITE_DAYS,
            max_redemptions=INVITE_MAX_REDEMPTIONS,
            campaign="specialist-invite",
            owner=(specialist.user.name or specialist.user.email or "")[:200],
            created_by=specialist.user,
        )
        return SpecialistInviteCode.objects.create(specialist=specialist, promo=promo)


def specialist_for_code(code_str: str):
    """Чей это код. None — обычный промокод, не специалиста."""
    from .models import SpecialistInviteCode

    code_str = (code_str or "").strip().upper()
    if not code_str:
        return None
    link = (
        SpecialistInviteCode.objects.filter(promo__code=code_str)
        .select_related("specialist__user", "promo")
        .first()
    )
    return link.specialist if link else None


def link_after_redeem(code_str: str, family, user):
    """Привязать специалиста к семье после активации его кода.

    Вызывается сразу после успешного redeem(). Возвращает Specialist, если код
    оказался специалистским, иначе None. Назначение создаётся сразу активным:
    ввод кода — и есть согласие клиента.

    Ошибку наружу не пускаем: подписка уже выдана, и отменять её из-за неудачной
    привязки нельзя. Такой случай уходит в лог.
    """
    from .models import SpecialistAssignment

    try:
        specialist = specialist_for_code(code_str)
        if specialist is None or family is None:
            return None

        assignment, created = SpecialistAssignment.objects.get_or_create(
            family=family,
            specialist=specialist,
            defaults={
                "specialist_type": specialist.specialist_type,
                "status": SpecialistAssignment.Status.ACTIVE,
            },
        )
        if not created and assignment.status != SpecialistAssignment.Status.ACTIVE:
            # Клиент вернулся к тому же специалисту — оживляем связь.
            assignment.status = SpecialistAssignment.Status.ACTIVE
            assignment.specialist_type = specialist.specialist_type
            assignment.save(update_fields=["status", "specialist_type"])
        return specialist
    except Exception as exc:
        logger.error("specialist invite link failed for code %s: %s", code_str, exc)
        return None
