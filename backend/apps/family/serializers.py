from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Family, FamilyMember

User = get_user_model()


class FamilyMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    avatar_url = serializers.URLField(source="user.avatar_url", read_only=True)

    class Meta:
        model = FamilyMember
        fields = ("id", "user_id", "name", "email", "avatar_url", "role", "joined_at")
        read_only_fields = ("id", "joined_at")


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
