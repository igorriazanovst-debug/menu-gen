from django.db import models

from apps.family.models import Family, FamilyMember
from apps.users.models import User


class Specialist(models.Model):
    class Type(models.TextChoices):
        DIETITIAN = "dietitian", "Диетолог (нутрициолог)"
        TRAINER = "trainer", "Фитнес-тренер"
        # MG_SPECACCESS: личный повар — ведёт закупку и готовку, поэтому у него
        # свои права (см. apps/specialists/access.py).
        COOK = "cook", "Личный повар"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="specialist_profile")
    specialist_type = models.CharField(max_length=20, choices=Type.choices)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    archive_document_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "specialists"
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["specialist_type", "is_verified"]),
        ]

    def __str__(self):
        return f"Specialist({self.user}, {self.specialist_type})"


class SpecialistAssignment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        ACTIVE = "active", "Активно"
        ENDED = "ended", "Завершено"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="specialist_assignments")
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="assignments")
    specialist_type = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "specialist_assignments"
        indexes = [
            models.Index(fields=["family_id", "status"]),
            models.Index(fields=["specialist_id", "status"]),
        ]


class Recommendation(models.Model):
    class Type(models.TextChoices):
        SUPPLEMENT = "supplement", "БАД"
        FOOD = "food", "Питание"
        EXERCISE = "exercise", "Упражнение"
        OTHER = "other", "Другое"

    assignment = models.ForeignKey(SpecialistAssignment, on_delete=models.CASCADE, related_name="recommendations")
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, blank=True)
    rec_type = models.CharField(max_length=20, choices=Type.choices)
    name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendations"
        indexes = [
            models.Index(fields=["assignment_id"]),
            models.Index(fields=["family_id", "is_active"]),
        ]


class DocumentArchive(models.Model):
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=100)
    encrypted_data = models.BinaryField()
    encryption_key_id = models.CharField(max_length=255)
    retention_until = models.DateField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_archive"
        indexes = [
            models.Index(fields=["specialist_id"]),
            models.Index(fields=["retention_until"]),
        ]


class DocumentAccessLog(models.Model):
    document = models.ForeignKey(DocumentArchive, on_delete=models.CASCADE, related_name="access_logs")
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    access_reason = models.TextField(blank=True)
    request_number = models.CharField(max_length=100, blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_access_log"
        indexes = [
            models.Index(fields=["document_id", "accessed_at"]),
            models.Index(fields=["accessed_by_id"]),
        ]


class SpecialistActionLog(models.Model):
    """MG_SPECACCESS: что специалист сделал в данных клиента.

    Специалист меняет чужие данные — меню, цели, холодильник. Без журнала на
    вопрос «кто это поменял» ответить нечем: у клиента правка выглядит так, будто
    она случилась сама. Пишем только изменения; чтение не пишем — это шум.
    """

    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="actions")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="specialist_actions")
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, blank=True)
    section = models.CharField(max_length=20)
    action = models.CharField(max_length=40)
    summary = models.CharField(max_length=500, blank=True, default="")
    object_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "specialist_action_log"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["family", "-created_at"]),
            models.Index(fields=["specialist", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.specialist_id} {self.section}.{self.action} → семья {self.family_id}"


class SpecialistInviteCode(models.Model):
    """MG_SPECINVITE: личный код специалиста — приглашение со своей стороны.

    Сам код живёт в PromoCode (там уже есть срок, счётчик активаций и защита от
    повторной активации в одной семье). Здесь только связь «код → чей он»:
    подписки про специалистов ничего не знают и знать не должны.
    """

    specialist = models.OneToOneField(Specialist, on_delete=models.CASCADE, related_name="invite_code")
    promo = models.ForeignKey("subscriptions.PromoCode", on_delete=models.CASCADE, related_name="specialist_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "specialist_invite_codes"
        indexes = [models.Index(fields=["promo"])]

    def __str__(self):
        return f"{self.promo.code} → {self.specialist}"
