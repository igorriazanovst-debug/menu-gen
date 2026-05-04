from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("Email или телефон обязателен")
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", User.UserType.ADMIN)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        USER = "user", "Пользователь"
        RECIPE_AUTHOR = "recipe_author", "Автор рецептов"
        SPECIALIST = "specialist", "Специалист"
        ADMIN = "admin", "Администратор"

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    vk_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    avatar_url = models.URLField(null=True, blank=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    allergies = models.JSONField(default=list, blank=True)
    disliked_products = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["vk_id"]),
            models.Index(fields=["user_type"]),
        ]

    def __str__(self):
        return self.email or self.phone or f"vk:{self.vk_id}"


class Profile(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"
        OTHER = "other", "Другой"

    class ActivityLevel(models.TextChoices):
        SEDENTARY = "sedentary", "Малоподвижный"
        LIGHT = "light", "Лёгкая активность"
        MODERATE = "moderate", "Умеренная активность"
        ACTIVE = "active", "Высокая активность"
        VERY_ACTIVE = "very_active", "Очень высокая активность"

    class Goal(models.TextChoices):
        LOSE_WEIGHT = "lose_weight", "Похудение"
        MAINTAIN = "maintain", "Поддержание веса"
        GAIN_WEIGHT = "gain_weight", "Набор массы"
        HEALTHY = "healthy", "Здоровое питание"

    class MealPlan(models.TextChoices):
        THREE = "3", "3 приёма пищи"
        FIVE = "5", "5 приёмов пищи"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    activity_level = models.CharField(max_length=20, choices=ActivityLevel.choices, default=ActivityLevel.MODERATE)
    goal = models.CharField(max_length=20, choices=Goal.choices, default=Goal.HEALTHY)
    calorie_target = models.PositiveSmallIntegerField(null=True, blank=True)
    protein_target_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fat_target_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carb_target_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fiber_target_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    meal_plan_type = models.CharField(max_length=2, choices=MealPlan.choices, default=MealPlan.THREE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return f"Profile({self.user})"

    # MG-202: auto-fill targets on save
    def save(self, *args, **kwargs):
        # MG-205: actor может быть проброшен через kwargs из view
        actor = kwargs.pop('_mg205_actor', None)
        from .nutrition import fill_profile_targets

        is_new = self.pk is None
        # Авторасчёт ДО сохранения. Для нового профиля аудит
        # запишется ниже (после первичного save), т.к. требуется pk.
        fill_profile_targets(self, force=False, actor=actor)
        super().save(*args, **kwargs)

        # MG-205: post-save audit pass — для новых профилей,
        # когда pk появился только что.
        if is_new:
            from .audit import record_target_change
            for f in (
                'calorie_target',
                'protein_target_g',
                'fat_target_g',
                'carb_target_g',
                'fiber_target_g',
            ):
                v = getattr(self, f, None)
                if v is None:
                    continue
                # идемпотентность: проверяем что записи ещё нет
                if not self.target_audits.filter(field=f).exists():
                    record_target_change(
                        profile=self,
                        field=f,
                        new_value=v,
                        source='auto',
                        by_user=actor,
                        old_value=None,
                        reason='auto-fill on profile create',
                    )


# ============================================================
# MG-205: аудит источника правок целей КБЖУ
# ============================================================
MG_205_V = 1


class ProfileTargetAudit(models.Model):
    """История правок полей КБЖУ профиля.

    Источник изменения: 'auto' (рассчитал fill_profile_targets),
    'user' (поставил сам пользователь), 'specialist' (диетолог/тренер).
    Текущий источник для поля = source последней записи (по at desc).
    """

    class Field(models.TextChoices):
        CALORIE = "calorie_target", "calorie_target"
        PROTEIN = "protein_target_g", "protein_target_g"
        FAT = "fat_target_g", "fat_target_g"
        CARB = "carb_target_g", "carb_target_g"
        FIBER = "fiber_target_g", "fiber_target_g"

    class Source(models.TextChoices):
        AUTO = "auto", "auto"
        USER = "user", "user"
        SPECIALIST = "specialist", "specialist"

    profile = models.ForeignKey(
        "Profile", on_delete=models.CASCADE, related_name="target_audits"
    )
    field = models.CharField(max_length=32, choices=Field.choices)
    source = models.CharField(max_length=16, choices=Source.choices)
    by_user = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_target_edits",
    )
    old_value = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    new_value = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    reason = models.TextField(blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profile_target_audit"
        indexes = [
            models.Index(fields=["profile", "field", "-at"]),
        ]
        ordering = ["-at"]

    def __str__(self):
        return f"PTA(pid={self.profile_id}, {self.field}={self.new_value}, src={self.source})"
