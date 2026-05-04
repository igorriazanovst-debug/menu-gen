from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Family, FamilyMember

User = get_user_model()


class ProfileSerializer(serializers.Serializer):
    # MG_203_V = 1
    birth_year = serializers.IntegerField(read_only=True)
    gender = serializers.CharField(read_only=True)
    height_cm = serializers.IntegerField(read_only=True)
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    activity_level = serializers.CharField(read_only=True)
    goal = serializers.CharField(read_only=True)
    calorie_target = serializers.IntegerField(read_only=True)
    # MG-203: targets + meal plan
    protein_target_g = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    fat_target_g     = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    carb_target_g    = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    fiber_target_g   = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    meal_plan_type   = serializers.CharField(read_only=True)


class FamilyMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    avatar_url = serializers.URLField(source="user.avatar_url", read_only=True)
    allergies = serializers.ListField(source="user.allergies", read_only=True)
    disliked_products = serializers.ListField(source="user.disliked_products", read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = FamilyMember
        fields = (
            "id",
            "user_id",
            "name",
            "email",
            "avatar_url",
            "allergies",
            "disliked_products",
            "profile",
            "role",
            "joined_at",
        )
        read_only_fields = ("id", "joined_at")

    def get_profile(self, obj):
        try:
            p = obj.user.profile
            return ProfileSerializer(p).data
        except Exception:
            return None


class FamilySerializer(serializers.ModelSerializer):
    members = FamilyMemberSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source="owner.name", read_only=True)

    class Meta:
        model = Family
        fields = ("id", "name", "owner_name", "members", "created_at")
        read_only_fields = ("id", "owner_name", "members", "created_at")


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("Укажите email или телефон.")
        return attrs


class RemoveMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class ProfileUpdateSerializer(serializers.Serializer):
    birth_year = serializers.IntegerField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=["male", "female", "other"], required=False, allow_null=True
    )
    height_cm = serializers.IntegerField(required=False, allow_null=True)
    weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=1, required=False, allow_null=True
    )
    activity_level = serializers.ChoiceField(
        choices=["sedentary", "light", "moderate", "active", "very_active"],
        required=False,
    )
    goal = serializers.ChoiceField(
        choices=["lose_weight", "maintain", "gain_weight", "healthy"],
        required=False,
    )
    calorie_target = serializers.IntegerField(required=False, allow_null=True)
    # MG-203: targets + meal plan (write)
    protein_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    fat_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    carb_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    fiber_target_g = serializers.DecimalField(
        max_digits=6, decimal_places=1, required=False, allow_null=True
    )
    meal_plan_type = serializers.ChoiceField(
        choices=["3", "5"], required=False, allow_null=True
    )


# MG_205_V_family_ser = 1
TARGET_FIELDS_MG205 = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class FamilyMemberUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=255)
    allergies = serializers.ListField(child=serializers.CharField(), required=False)
    disliked_products = serializers.ListField(child=serializers.CharField(), required=False)
    profile = ProfileUpdateSerializer(required=False)

    def update(self, instance, validated_data):
        from apps.users.audit import record_target_change
        from apps.specialists.permissions import is_verified_specialist_for_user

        user = instance.user
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None

        # MG-205: определяем источник правки
        if actor and actor.id == user.id:
            source = "user"
        elif actor and is_verified_specialist_for_user(actor, user):
            source = "specialist"
        else:
            # Глава семьи правит члена семьи → считаем source='user'
            # (правки головы семьи приравниваются к ручным правкам пользователя)
            source = "user"

        profile_data = validated_data.pop("profile", None)

        for attr in ("name", "allergies", "disliked_products"):
            if attr in validated_data:
                setattr(user, attr, validated_data[attr])
        user.save()

        if profile_data:
            profile = user.profile
            old_values = {f: getattr(profile, f, None) for f in TARGET_FIELDS_MG205}

            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

            for f in TARGET_FIELDS_MG205:
                if f in profile_data:
                    record_target_change(
                        profile=profile,
                        field=f,
                        new_value=profile_data[f],
                        source=source,
                        by_user=actor,
                        old_value=old_values[f],
                        reason=f"family PATCH (source={source})",
                    )

        return instance
