from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Family, FamilyMember
from .serializers import (
    FamilyMemberSerializer,
    FamilyMemberUpdateSerializer,
    FamilySerializer,
    InviteMemberSerializer,
)

User = get_user_model()


def _get_user_family(user):
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    if membership:
        return membership.family
    return Family.objects.filter(owner=user).first()


class FamilyDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: FamilySerializer})
    def get(self, request):
        family = _get_user_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        serializer = FamilySerializer(family)
        return Response(serializer.data)

    @extend_schema(request=FamilySerializer, responses={200: FamilySerializer})
    def patch(self, request):
        family = _get_user_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        if family.owner_id != request.user.id and request.user.user_type != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = FamilySerializer(family, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FamilyInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=InviteMemberSerializer, responses={200: FamilyMemberSerializer})
    def post(self, request):
        family = _get_user_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        if family.owner_id != request.user.id and request.user.user_type != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        phone = serializer.validated_data.get("phone")

        try:
            if email:
                invitee = User.objects.get(email=email)
            else:
                invitee = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response(
                {"detail": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if FamilyMember.objects.filter(family=family, user=invitee).exists():
            return Response(
                {"detail": "Пользователь уже в семье."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверка лимита по подписке
        plan = _get_active_plan(family)
        current_count = family.members.count()
        if plan and current_count >= plan.max_family_members:
            return Response(
                {"detail": f"Лимит участников для тарифа «{plan.name}» исчерпан ({plan.max_family_members})."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = FamilyMember.objects.create(family=family, user=invitee, role=FamilyMember.Role.MEMBER)
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class FamilyRemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, member_id):
        family = _get_user_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)

        is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
        is_self = FamilyMember.objects.filter(family=family, user=request.user, id=member_id).exists()

        if not is_head and not is_self:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            member = FamilyMember.objects.get(id=member_id, family=family)
        except FamilyMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if member.role == FamilyMember.Role.HEAD:
            return Response(
                {"detail": "Нельзя удалить главу семьи."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FamilyMemberUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=FamilyMemberUpdateSerializer,
        responses={200: FamilyMemberSerializer},
    )
    def patch(self, request, member_id):
        family = _get_user_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # MG_205_V_family_view = 1: добавлен путь для verified specialist'а
        is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
        is_self = FamilyMember.objects.filter(
            family=family, user=request.user, id=member_id
        ).exists()

        # Specialist допускается, если у него есть активный assignment на эту семью
        is_specialist = False
        try:
            from apps.specialists.permissions import _get_specialist
            from apps.specialists.models import SpecialistAssignment
            spec = _get_specialist(request.user)
            if spec and spec.is_verified:
                is_specialist = SpecialistAssignment.objects.filter(
                    specialist=spec,
                    family=family,
                    status=SpecialistAssignment.Status.ACTIVE,
                ).exists()
        except Exception:
            is_specialist = False

        if not (is_head or is_self or is_specialist):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            member = FamilyMember.objects.select_related("user__profile").get(
                id=member_id, family=family
            )
        except FamilyMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = FamilyMemberUpdateSerializer(
            member, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        member.refresh_from_db()
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_200_OK)


# ── helpers ───────────────────────────────────────────────────────────────────


def _get_active_plan(family):
    from apps.subscriptions.models import Subscription

    sub = (
        Subscription.objects.filter(family=family, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .order_by("-started_at")
        .first()
    )
    return sub.plan if sub else None



# ─────────────────────────────────────────────────────────────────────────────
# MG_205UI_V_family_views = 1
# История + reset для одного поля КБЖУ участника семьи.
# ─────────────────────────────────────────────────────────────────────────────

TARGET_FIELD_CHOICES = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


def _validate_target_field(field: str):
    if field not in TARGET_FIELD_CHOICES:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"field": f"Допустимые значения: {list(TARGET_FIELD_CHOICES)}"})


def _resolve_member_with_perm(request, member_id):
    """Проверка прав (head / self / verified specialist с активным assignment).
    Возвращает (member, source_for_actions) или Response с ошибкой."""
    family = _get_user_family(request.user)
    if not family:
        return None, Response(status=status.HTTP_404_NOT_FOUND)

    is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
    is_self = FamilyMember.objects.filter(
        family=family, user=request.user, id=member_id
    ).exists()

    is_specialist = False
    try:
        from apps.specialists.permissions import _get_specialist
        from apps.specialists.models import SpecialistAssignment
        spec = _get_specialist(request.user)
        if spec and spec.is_verified:
            is_specialist = SpecialistAssignment.objects.filter(
                specialist=spec,
                family=family,
                status=SpecialistAssignment.Status.ACTIVE,
            ).exists()
    except Exception:
        is_specialist = False

    if not (is_head or is_self or is_specialist):
        return None, Response(status=status.HTTP_403_FORBIDDEN)

    try:
        member = FamilyMember.objects.select_related("user__profile").get(
            id=member_id, family=family
        )
    except FamilyMember.DoesNotExist:
        return None, Response(status=status.HTTP_404_NOT_FOUND)

    # Источник для аудита при правках через этот endpoint
    if is_self:
        src = "user"
    elif is_specialist and not is_self:
        src = "specialist"
    else:
        src = "user"  # head правит члена семьи — приравниваем к user
    return (member, src), None


class FamilyMemberTargetHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, member_id, field):
        _validate_target_field(field)
        result, err = _resolve_member_with_perm(request, member_id)
        if err is not None:
            return err
        member, _ = result
        from apps.users.models import ProfileTargetAudit
        from apps.users.serializers import ProfileTargetAuditSerializer
        try:
            profile = member.user.profile
        except Exception:
            return Response([], status=status.HTTP_200_OK)
        qs = (
            ProfileTargetAudit.objects.filter(profile=profile, field=field)
            .select_related("by_user")
            .order_by("-at")[:100]
        )
        return Response(ProfileTargetAuditSerializer(qs, many=True).data)


class FamilyMemberTargetResetView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, member_id, field):
        _validate_target_field(field)
        result, err = _resolve_member_with_perm(request, member_id)
        if err is not None:
            return err
        member, _ = result

        from apps.users.audit import record_target_change
        from apps.users.nutrition import calculate_targets

        try:
            profile = member.user.profile
        except Exception:
            return Response({"detail": "Профиль не найден."}, status=status.HTTP_404_NOT_FOUND)

        targets = calculate_targets(profile)
        if not targets:
            return Response(
                {"detail": "Недостаточно данных для расчёта (рост/вес/год рождения)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_value = getattr(profile, field, None)
        new_value = targets.get(field)
        setattr(profile, field, new_value)
        profile.save()

        record_target_change(
            profile=profile,
            field=field,
            new_value=new_value,
            source="auto",
            by_user=request.user,
            old_value=old_value,
            reason=f"family reset to auto by user {request.user.id}",
        )

        member.refresh_from_db()
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_200_OK)
