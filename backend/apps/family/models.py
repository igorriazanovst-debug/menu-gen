from django.db import models

from apps.users.models import User


class Family(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_families")
    name = models.CharField(max_length=255, blank=True)
    # MG_RUBRIC006: family currency (used for shopping prices/totals).
    currency = models.CharField(max_length=8, default="RUB")
    # MG_SHELFLIFE: подставлять ли срок годности при переносе покупок в
    # холодильник. Настройка семейная, а не личная: холодильник общий, разбирать
    # пакеты может любой — включая повара, — и два разных режима у мужа и жены
    # означали бы, что итог зависит от того, кто донёс сумку.
    auto_expiry = models.BooleanField(
        default=True, help_text="Подставлять срок годности при переносе покупок в холодильник"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "families"
        indexes = [models.Index(fields=["owner_id"])]

    def __str__(self):
        return f"Family({self.owner}, {self.name})"


class FamilyMember(models.Model):
    class Role(models.TextChoices):
        HEAD = "head", "Глава семьи"
        MEMBER = "member", "Участник"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="family_memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "family_members"
        unique_together = [("family", "user")]
        indexes = [
            models.Index(fields=["family_id"]),
            models.Index(fields=["user_id"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.family} ({self.role})"


class FamilyInvite(models.Model):
    """MG_FAMINVITE: приглашение в семью, на которое можно ответить.

    До этой задачи ручка называлась «пригласить», но приглашения не было: сервер
    находил аккаунт по почте или телефону и сразу создавал членство. Человек
    оказывался за чужим столом, не узнав об этом: получал общий холодильник и
    список покупок, а глава семьи — право видеть и править его профиль и нормы
    КБЖУ. Согласия не спрашивали, уведомления не слали.

    Устройство списано с `ShoppingListAccess` (apps/shopping/models.py): те же
    три состояния и та же пара ручек «мои входящие» и «ответить». Отдельная
    выдумка тут была бы хуже уже работающей.

    Строка на пару «семья + приглашённый» одна: повторное приглашение переводит
    её обратно в ожидание, а не плодит вторую. История отказов не хранится
    намеренно — она никому не нужна, а знание «мне уже отказывали трижды» лучше
    не давать никому.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает ответа"
        ACCEPTED = "accepted", "Принято"
        REJECTED = "rejected", "Отклонено"
        CANCELLED = "cancelled", "Отозвано"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="invites")
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="family_invites")
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "family_invites"
        unique_together = [("family", "invited_user")]
        indexes = [
            models.Index(fields=["invited_user_id", "status"]),
            models.Index(fields=["family_id", "status"]),
        ]

    def __str__(self):
        return f"Invite({self.invited_user} -> {self.family}, {self.status})"
