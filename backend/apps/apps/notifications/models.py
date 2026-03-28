from django.db import models
from apps.users.models import User


class Notification(models.Model):
    class Type(models.TextChoices):
        MENU_READY = "menu_ready", "Меню готово"
        FRIDGE_EXPIRY = "fridge_expiry", "Срок годности"
        SPECIALIST_MESSAGE = "specialist_message", "Сообщение специалиста"
        SUBSCRIPTION = "subscription", "Подписка"
        SYSTEM = "system", "Системное"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(max_length=512, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(fields=["user_id", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Notification({self.user}, {self.notification_type})"
