from django.db import models

from apps.family.models import Family, FamilyMember
from apps.users.models import User


class Specialist(models.Model):
    class Type(models.TextChoices):
        DIETITIAN = "dietitian", "Диетолог"
        TRAINER = "trainer", "Тренер"

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
