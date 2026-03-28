from django.db import models

from apps.users.models import User


class SocialLink(models.Model):
    class Provider(models.TextChoices):
        VK = "vk", "ВКонтакте"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_links")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_user_id = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_links"
        unique_together = [("user", "provider")]
        indexes = [
            models.Index(fields=["user_id", "provider"]),
        ]

    def __str__(self):
        return f"SocialLink({self.user}, {self.provider})"
