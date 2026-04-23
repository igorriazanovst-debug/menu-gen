from django.db import models

from apps.users.models import User


class Family(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_families")
    name = models.CharField(max_length=255, blank=True)
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
