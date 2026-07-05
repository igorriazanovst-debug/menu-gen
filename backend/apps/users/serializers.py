from django.contrib.auth import get_user_model
from django.utils import timezone  # noqa: F401  # MG-profile-premium
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile

# MG_504_V_serializers
MG504_FIELDS = ("bedtime_hour", "cheat_meal_interval", "last_cheat_meal_date")

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=5)  # MG_208_V_be_serializer
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("name", "email", "phone", "password", "password2")

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("Укажите email или телефон.")
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError("Пароли не совпадают.")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        email = attrs.get("email")
        phone = attrs.get("phone")
        password = attrs.get("password")

        if not email and not phone:
            raise serializers.ValidationError("Укажите email или телефон.")

        if email:
            user = authenticate(request=self.context.get("request"), username=email, password=password)
        else:
            try:
                u = User.objects.get(phone=phone)
            except User.DoesNotExist:
                u = None
            user = (
                authenticate(
                    request=self.context.get("request"),
                    username=u.email if u else None,
                    password=password,
                )
                if u
                else None
            )

        if not user or not user.is_active:
            raise serializers.ValidationError("Неверные учётные данные.")

        attrs["user"] = user
        return attrs


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    @staticmethod
    def get_tokens(user):
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


# MG_205UI_V_serializers = 1
TARGET_FIELDS_MG205UI = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class ProfileTargetAuditSerializer(serializers.Serializer):
    """Запись истории правок одного поля КБЖУ."""

    id = serializers.IntegerField(read_only=True)
    field = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    old_value = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True, allow_null=True)
    new_value = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True, allow_null=True)
    reason = serializers.CharField(read_only=True, allow_blank=True)
    at = serializers.DateTimeField(read_only=True)
    by_user = serializers.SerializerMethodField()

    def get_by_user(self, obj):
        if obj.by_user_id is None:
            return None
        return {"id": obj.by_user.id, "name": obj.by_user.name}


class ProfileSerializer(serializers.ModelSerializer):
    targets_calculated = serializers.SerializerMethodField()
    targets_meta = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "birth_year",
            "gender",
            "height_cm",
            "weight_kg",
            "activity_level",
            "goal",
            "calorie_target",
            "protein_target_g",
            "fat_target_g",
            "carb_target_g",
            "fiber_target_g",
            "meal_plan_type",
            "targets_calculated",
            "targets_meta",
        ) + MG504_FIELDS

    def get_targets_calculated(self, obj):
        from .nutrition import calculate_targets

        result = calculate_targets(obj)
        if not result:
            return None
        return {
            "calorie_target": result["calorie_target"],
            "protein_target_g": str(result["protein_target_g"]),
            "fat_target_g": str(result["fat_target_g"]),
            "carb_target_g": str(result["carb_target_g"]),
            "fiber_target_g": str(result["fiber_target_g"]),
        }

    def get_targets_meta(self, obj):
        """MG-205-UI: для каждого target-поля — последняя запись аудита."""
        from .models import ProfileTargetAudit

        if not getattr(obj, "pk", None):
            return {}
        out = {}
        for f in TARGET_FIELDS_MG205UI:
            last = ProfileTargetAudit.objects.filter(profile=obj, field=f).order_by("-at").first()
            if last is None:
                out[f] = {"source": "auto", "by_user": None, "at": None}
            else:
                out[f] = {
                    "source": last.source,
                    "by_user": ({"id": last.by_user.id, "name": last.by_user.name} if last.by_user_id else None),
                    "at": last.at.isoformat() if last.at else None,
                }
        return out


class UserMeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    # MG-profile-premium: derived subscription summary for proactive UI.
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "vk_id",
            "avatar_url",
            "user_type",
            "allergies",
            "disliked_products",
            "ui_skin",  # MG_SKIN
            "created_at",
            "profile",
            "subscription_status",
        )
        read_only_fields = ("id", "vk_id", "user_type", "created_at")

    @extend_schema_field(
        {
            "type": "object",
            "nullable": True,
            "properties": {
                "is_active_premium": {"type": "boolean"},
                "has_ever_premium": {"type": "boolean"},
                "plan_code": {"type": "string", "nullable": True},
                "status": {
                    "type": "string",
                    "nullable": True,
                    "enum": ["active", "trial", "expired", "cancelled", None],
                },
                "expires_at": {"type": "string", "format": "date-time", "nullable": True},
                "menu_quota": {
                    "type": "object",
                    "properties": {
                        "used": {"type": "integer"},
                        "limit": {"type": "integer", "nullable": True},
                        "reset_at": {"type": "string", "format": "date"},
                    },
                },
            },
        }
    )
    def get_subscription_status(self, obj):
        # Local import — avoid app-loading order issues.
        from apps.subscriptions.models import Subscription
        from apps.subscriptions.permissions import get_user_family, has_active_premium, has_ever_had_premium
        from apps.subscriptions.quota import menu_quota_summary

        family = get_user_family(obj)
        if family is None:
            return None

        latest = Subscription.objects.filter(family=family).select_related("plan").order_by("-started_at").first()

        return {
            "is_active_premium": has_active_premium(family),
            "has_ever_premium": has_ever_had_premium(family),
            "plan_code": latest.plan.code if latest else None,
            "status": latest.status if latest else None,
            "expires_at": latest.expires_at.isoformat() if latest else None,
            # Freemium: остаток квоты на генерацию меню (limit=None → безлимит/premium).
            "menu_quota": menu_quota_summary(family),
        }


# MG_205_V_serializers = 1
TARGET_FIELDS_MG205 = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class UserMeUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("name", "avatar_url", "allergies", "disliked_products", "ui_skin", "profile")  # MG_SKIN

    def update(self, instance, validated_data):
        from .audit import record_target_change

        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None

        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            # Сохраним old-значения для аудита ДО изменения
            old_values = {f: getattr(profile, f, None) for f in TARGET_FIELDS_MG205}

            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

            # MG-205: для каждого пришедшего target-поля пишем аудит source='user'
            # (UserMeUpdateSerializer — это всегда сам пользователь правит свой профиль)
            for f in TARGET_FIELDS_MG205:
                if f in profile_data:
                    new_val = profile_data[f]
                    record_target_change(
                        profile=profile,
                        field=f,
                        new_value=new_val,
                        source="user",
                        by_user=actor,
                        old_value=old_values[f],
                        reason="user PATCH /users/me",
                    )
        return instance


# ─────────────────────────────────────────────────────────────────────────────
# MG_206_V_serializers = 1
# Калькулятор КБЖУ: preview/apply сериалайзеры
# ─────────────────────────────────────────────────────────────────────────────
from apps.users.calculator import VALID_ACTIVITIES as _CALC_ACTIVITIES  # noqa: E402
from apps.users.calculator import VALID_CUSTOM_MODES as _CALC_MODES  # noqa: E402
from apps.users.calculator import VALID_DIETS as _CALC_DIETS  # noqa: E402
from apps.users.calculator import VALID_GENDERS as _CALC_GENDERS  # noqa: E402
from apps.users.calculator import VALID_GOALS as _CALC_GOALS  # noqa: E402
from apps.users.calculator import VALID_SYSTEMS as _CALC_SYSTEMS  # noqa: E402


class CalculatorRequestSerializer(serializers.Serializer):
    """
    Универсальный запрос для preview/apply. Валидация по выбранной системе:
      - non-custom: требуется diet + базовые поля (weight/height/birth_year/gender/activity_level/goal)
      - custom + grams: требуются custom_calorie_target + custom_*_g
      - custom + percents: требуются базовые поля + custom_*_pct + custom_calorie_delta
    """

    system = serializers.ChoiceField(choices=[(s, s) for s in _CALC_SYSTEMS])
    diet = serializers.ChoiceField(choices=[(d, d) for d in _CALC_DIETS], required=False, allow_null=True)

    # base inputs (для preset и для custom_mode=percents)
    height_cm = serializers.IntegerField(min_value=50, max_value=250, required=False)
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=20, max_value=400, required=False)
    birth_year = serializers.IntegerField(min_value=1900, max_value=2030, required=False)
    gender = serializers.ChoiceField(choices=[(g, g) for g in _CALC_GENDERS], required=False)
    activity_level = serializers.ChoiceField(choices=[(a, a) for a in _CALC_ACTIVITIES], required=False)
    goal = serializers.ChoiceField(choices=[(g, g) for g in _CALC_GOALS], required=False)

    # custom mode
    custom_mode = serializers.ChoiceField(choices=[(m, m) for m in _CALC_MODES], required=False, allow_null=True)
    # grams branch
    custom_calorie_target = serializers.IntegerField(min_value=500, max_value=10000, required=False)
    custom_protein_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, min_value=0, max_value=1000, required=False
    )
    custom_fat_g = serializers.DecimalField(max_digits=6, decimal_places=1, min_value=0, max_value=1000, required=False)
    custom_carb_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, min_value=0, max_value=2000, required=False
    )
    custom_fiber_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, min_value=0, max_value=200, required=False
    )
    # percents branch
    custom_calorie_delta = serializers.IntegerField(min_value=-2000, max_value=2000, required=False)
    custom_protein_pct = serializers.FloatField(min_value=0, max_value=100, required=False)
    custom_fat_pct = serializers.FloatField(min_value=0, max_value=100, required=False)
    custom_carb_pct = serializers.FloatField(min_value=0, max_value=100, required=False)

    def validate(self, attrs):
        sys_code = attrs["system"]
        if sys_code != "custom":
            # preset path
            if not attrs.get("diet"):
                raise serializers.ValidationError({"diet": "Обязателен для непользовательской системы."})
            required = ["height_cm", "weight_kg", "birth_year", "gender", "activity_level", "goal"]
            missing = [f for f in required if attrs.get(f) in (None, "")]
            if missing:
                raise serializers.ValidationError({m: "Обязательное поле." for m in missing})
            return attrs
        # custom path
        mode = attrs.get("custom_mode")
        if mode not in _CALC_MODES:
            raise serializers.ValidationError({"custom_mode": "Укажите режим: grams или percents."})
        if mode == "grams":
            required = ["custom_calorie_target", "custom_protein_g", "custom_fat_g", "custom_carb_g", "custom_fiber_g"]
            missing = [f for f in required if attrs.get(f) in (None, "")]
            if missing:
                raise serializers.ValidationError({m: "Обязательное поле в режиме grams." for m in missing})
        else:  # percents
            required_base = ["height_cm", "weight_kg", "birth_year", "gender", "activity_level"]
            required_pcts = ["custom_protein_pct", "custom_fat_pct", "custom_carb_pct"]
            missing = [f for f in (required_base + required_pcts) if attrs.get(f) in (None, "")]
            if missing:
                raise serializers.ValidationError({m: "Обязательное поле в режиме percents." for m in missing})
            total = (
                float(attrs["custom_protein_pct"]) + float(attrs["custom_fat_pct"]) + float(attrs["custom_carb_pct"])
            )
            if abs(total - 100.0) > 0.5:
                raise serializers.ValidationError(
                    {"custom_protein_pct": f"Сумма Б/Ж/У должна быть 100%, сейчас {total:.1f}%."}
                )
        return attrs


class CalculatorResultSerializer(serializers.Serializer):
    """Результат расчёта (preview и apply возвращают одинаковый формат)."""

    system = serializers.CharField()
    diet = serializers.CharField(allow_null=True, required=False)
    age = serializers.IntegerField(allow_null=True, required=False)
    bmr = serializers.IntegerField(allow_null=True, required=False)
    tdee = serializers.IntegerField(allow_null=True, required=False)
    calorie_target = serializers.IntegerField()
    protein_target_g = serializers.DecimalField(max_digits=6, decimal_places=1)
    fat_target_g = serializers.DecimalField(max_digits=6, decimal_places=1)
    carb_target_g = serializers.DecimalField(max_digits=6, decimal_places=1)
    fiber_target_g = serializers.DecimalField(max_digits=6, decimal_places=1)
