from django.db import models

from apps.users.models import User


class SyncLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Создание"
        UPDATE = "update", "Обновление"
        DELETE = "delete", "Удаление"

    class SyncStatus(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SYNCED = "synced", "Синхронизировано"
        CONFLICT = "conflict", "Конфликт"
        FAILED = "failed", "Ошибка"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sync_logs")
    device_id = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=Action.choices)
    payload = models.JSONField(default=dict)
    sync_status = models.CharField(max_length=20, choices=SyncStatus.choices, default=SyncStatus.PENDING)
    retry_count = models.PositiveSmallIntegerField(default=0)
    conflict_data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sync_log"
        indexes = [
            models.Index(fields=["user_id", "device_id"]),
            models.Index(fields=["sync_status"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"SyncLog({self.user}, {self.entity_type}, {self.action}, {self.sync_status})"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=255, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["user_id", "action"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["created_at"]),
        ]
