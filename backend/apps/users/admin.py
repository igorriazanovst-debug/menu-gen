from datetime import timedelta

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from apps.subscriptions.models import Subscription, SubscriptionPlan

from .models import Profile, User


class AdminUserCreationForm(forms.ModelForm):
    """Полноценное создание пользователя в админке.

    Помимо полей аккаунта и прав (user_type, is_staff/superuser/managed) позволяет
    в один шаг:
      • задать пароль (или оставить пустым — «управляемый» аккаунт без входа);
      • создать семью и сделать пользователя её владельцем и главой;
      • назначить тариф — создать подписку на эту семью (для code=premium статус
        active/trial с будущим expires_at даёт премиум-доступ).
    """

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        required=False,
        help_text="Пусто → аккаунт без пароля (управляемый, без входа).",
    )
    password2 = forms.CharField(label="Пароль (повтор)", widget=forms.PasswordInput, required=False)

    create_family = forms.BooleanField(
        label="Создать семью",
        required=False,
        initial=True,
        help_text="Сделать пользователя владельцем и главой новой семьи.",
    )
    family_name = forms.CharField(label="Название семьи", required=False)
    plan = forms.ModelChoiceField(
        label="Тариф",
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        required=False,
        help_text="Назначить подписку семье. Требует «Создать семью».",
    )
    sub_status = forms.ChoiceField(
        label="Статус подписки",
        choices=Subscription.Status.choices,
        initial=Subscription.Status.ACTIVE,
        required=False,
    )
    sub_months = forms.IntegerField(
        label="Срок подписки, мес.",
        initial=12,
        min_value=1,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "phone",
            "vk_id",
            "name",
            "user_type",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_managed",
        )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Пароли не совпадают.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        if not cleaned.get("email") and not cleaned.get("phone"):
            self.add_error("email", "Нужен email или телефон.")
        if cleaned.get("plan") and not cleaned.get("create_family"):
            self.add_error("create_family", "Для назначения тарифа отметьте «Создать семью».")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = AdminUserCreationForm
    inlines = [ProfileInline]
    list_display = ("id", "email", "phone", "name", "user_type", "is_active", "created_at")
    list_filter = ("user_type", "is_active", "is_staff", "is_superuser", "is_managed")
    search_fields = ("email", "phone", "name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "phone", "vk_id", "password")}),
        ("Личные данные", {"fields": ("name", "avatar_url", "allergies", "disliked_products")}),
        (
            "Роли и доступ",
            {
                "fields": (
                    "user_type",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_managed",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            "Аккаунт",
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "vk_id", "name", "password1", "password2"),
            },
        ),
        (
            "Роли и права",
            {"fields": ("user_type", "is_active", "is_staff", "is_superuser", "is_managed")},
        ),
        (
            "Тариф и семья",
            {"fields": ("create_family", "family_name", "plan", "sub_status", "sub_months")},
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            self._provision(request, obj, form)

    def _provision(self, request, user, form):
        """Создать семью/подписку по данным формы создания (только при создании)."""
        cd = getattr(form, "cleaned_data", {}) or {}
        if not cd.get("create_family"):
            return

        from apps.family.models import Family, FamilyMember

        name = (cd.get("family_name") or "").strip() or (f"Семья {user.name}".strip() if user.name else "Семья")
        family = Family.objects.create(owner=user, name=name)
        FamilyMember.objects.get_or_create(family=family, user=user, defaults={"role": FamilyMember.Role.HEAD})

        plan = cd.get("plan")
        if plan:
            months = cd.get("sub_months") or 12
            now = timezone.now()
            Subscription.objects.create(
                family=family,
                plan=plan,
                status=cd.get("sub_status") or Subscription.Status.ACTIVE,
                started_at=now,
                expires_at=now + timedelta(days=30 * int(months)),
                auto_renew=True,
            )
        self.message_user(
            request,
            f"Создана семья «{name}»" + (f" и подписка «{plan.code}»." if plan else " (без подписки)."),
        )
