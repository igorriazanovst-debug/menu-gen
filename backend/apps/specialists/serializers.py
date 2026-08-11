from rest_framework import serializers

from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu

from .access import permissions_for
from .models import Recommendation, Specialist, SpecialistActionLog, SpecialistAssignment


class SpecialistProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    # MG_SPECACCESS: права роли — чтобы интерфейс не гадал, что показывать.
    # Прятать кнопку — не защита, решение всё равно за сервером; но и предлагать
    # заведомо запретное не нужно.
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Specialist
        fields = ("id", "name", "email", "specialist_type", "is_verified", "verified_at", "permissions")

    def get_permissions(self, obj) -> dict:
        return permissions_for(obj.specialist_type)


class FamilyMemberShortSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = FamilyMember
        fields = ("id", "name", "email", "role")


class ClientFamilySerializer(serializers.ModelSerializer):
    members = FamilyMemberShortSerializer(many=True, read_only=True)
    assignment_id = serializers.SerializerMethodField()
    assignment_status = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = ("id", "name", "members", "assignment_id", "assignment_status")

    def get_assignment(self, obj):
        specialist = self.context.get("specialist")
        if not specialist:
            return None
        return SpecialistAssignment.objects.filter(family=obj, specialist=specialist).order_by("-assigned_at").first()

    def get_assignment_id(self, obj):
        a = self.get_assignment(obj)
        return a.id if a else None

    def get_assignment_status(self, obj):
        a = self.get_assignment(obj)
        return a.status if a else None


class RecommendationSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.user.name", read_only=True, default=None)

    class Meta:
        model = Recommendation
        fields = (
            "id",
            "rec_type",
            "name",
            "dosage",
            "frequency",
            "start_date",
            "end_date",
            "is_active",
            "is_read",
            "member_name",
            "created_at",
        )


class RecommendationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = (
            "rec_type",
            "name",
            "dosage",
            "frequency",
            "start_date",
            "end_date",
            "member",
        )

    def validate_member(self, value):
        assignment = self.context.get("assignment")
        if value and assignment:
            if not FamilyMember.objects.filter(id=value.id, family=assignment.family).exists():
                raise serializers.ValidationError("Участник не принадлежит семье клиента.")
        return value


class ClientMenuListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ("id", "start_date", "end_date", "period_days", "status", "generated_at")


class SpecialistVerifySerializer(serializers.Serializer):
    specialist_type = serializers.ChoiceField(choices=Specialist.Type.choices)


class SpecialistActionLogSerializer(serializers.ModelSerializer):
    """MG_SPECACCESS: история правок специалиста в данных клиента."""

    specialist_name = serializers.CharField(source="specialist.user.name", read_only=True, default=None)
    member_name = serializers.CharField(source="member.user.name", read_only=True, default=None)

    class Meta:
        model = SpecialistActionLog
        fields = ("id", "section", "action", "summary", "member_name", "specialist_name", "created_at")
