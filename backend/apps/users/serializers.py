from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
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


class ProfileSerializer(serializers.ModelSerializer):
    targets_calculated = serializers.SerializerMethodField()

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
            "carbs_target_g",
            "fiber_target_g",
            "meal_plan",
            "targets_calculated",
        )

    def get_targets_calculated(self, obj):
        from .nutrition import calculate_targets
        result = calculate_targets(obj)
        if not result:
            return None
        return {
            "calorie_target":   result["calorie_target"],
            "protein_target_g": str(result["protein_target_g"]),
            "fat_target_g":     str(result["fat_target_g"]),
            "carbs_target_g":   str(result["carbs_target_g"]),
            "fiber_target_g":   str(result["fiber_target_g"]),
        }


class UserMeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

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
            "created_at",
            "profile",
        )
        read_only_fields = ("id", "vk_id", "user_type", "created_at")


class UserMeUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("name", "avatar_url", "allergies", "disliked_products", "profile")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance
