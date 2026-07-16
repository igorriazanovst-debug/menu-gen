from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    class Period(models.TextChoices):
        MONTH = "month", "Месяц"
        YEAR = "year", "Год"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.MONTH)
    features = models.JSONField(default=dict)
    max_family_members = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "subscription_plans"
        indexes = [models.Index(fields=["code"]), models.Index(fields=["is_active"])]

    def __str__(self):
        return f"{self.name} ({self.price} ₽/{self.period})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        CANCELLED = "cancelled", "Отменена"
        EXPIRED = "expired", "Истекла"
        TRIAL = "trial", "Пробный период"

    family = models.ForeignKey("family.Family", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [
            models.Index(fields=["family_id", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.family} — {self.plan.code} ({self.status})"


class MenuGenerationCounter(models.Model):
    """Freemium-квота: сколько генераций меню семья использовала в текущем периоде.

    Период — календарный месяц (`period_start` = 1-е число). При генерации в новом
    месяце счётчик сбрасывается. Premium-семьи квотой не ограничены и сюда не пишут.
    """

    family = models.OneToOneField("family.Family", on_delete=models.CASCADE, related_name="menu_quota")
    period_start = models.DateField()
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menu_generation_counters"

    def __str__(self):
        return f"{self.family} — {self.count} @ {self.period_start}"


class PromoCode(models.Model):
    """Промокод, активирующий премиум-подписку бесплатно.

    Одноразовый (max_redemptions=1) или многоразовый (кампания, N активаций).
    Срок выдаваемой подписки: duration_days, если задан, иначе период плана.
    Создаётся в админке (в т.ч. пакетно), активируется пользователем на свою семью.
    """

    code = models.CharField(max_length=40, unique=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="promo_codes")
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Срок подписки в днях. Пусто — берётся период плана (месяц/год).",
    )
    max_redemptions = models.PositiveIntegerField(
        default=1,
        help_text="Сколько раз код можно активировать (1 — одноразовый).",
    )
    redeemed_count = models.PositiveIntegerField(default=0)
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="До какого момента код можно активировать. Пусто — без ограничения по дате.",
    )
    is_active = models.BooleanField(default=True)
    campaign = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Метка кампании/партии (для админки).",
    )
    owner = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Владелец ключа: имя или компания (для именных ключей).",
    )
    assigned_email = models.EmailField(
        blank=True,
        default="",
        help_text="Если задан — активировать код может только пользователь с этим email.",
    )
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promo_codes"
        indexes = [models.Index(fields=["code"]), models.Index(fields=["is_active"])]

    def __str__(self):
        return f"{self.code} → {self.plan.code} ({self.redeemed_count}/{self.max_redemptions})"

    @property
    def is_redeemable(self):
        if not self.is_active:
            return False
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        if self.redeemed_count >= self.max_redemptions:
            return False
        return True


class PromoRedemption(models.Model):
    """Факт активации промокода семьёй (одна семья — один раз на код)."""

    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    family = models.ForeignKey("family.Family", on_delete=models.CASCADE, related_name="promo_redemptions")
    user = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="promo_redemptions"
    )
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class RevokeMode(models.TextChoices):
        NONE = "", "—"
        FREE = "free", "Переведён на бесплатный тариф"
        BLOCK = "block", "Пользователь заблокирован"

    # Отзыв активации (см. promo.revoke_*). Пусто — активна.
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_mode = models.CharField(max_length=10, choices=RevokeMode.choices, blank=True, default="")

    class Meta:
        db_table = "promo_redemptions"
        constraints = [models.UniqueConstraint(fields=["promo", "family"], name="uniq_promo_family")]
        indexes = [models.Index(fields=["family"])]

    def __str__(self):
        return f"{self.promo.code} × {self.family} @ {self.redeemed_at}"

    @property
    def is_revoked(self):
        return self.revoked_at is not None
