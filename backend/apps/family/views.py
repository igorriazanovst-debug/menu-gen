from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Family, FamilyMember
from .serializers import FamilyMemberSerializer, FamilySerializer, InviteMemberSerializer

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

        member = FamilyMember.objects.create(
            family=family, user=invitee, role=FamilyMember.Role.MEMBER
        )
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class FamilyRemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, member_id):
        family = _get_user_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)

        is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
        is_self = FamilyMember.objects.filter(
            family=family, user=request.user, id=member_id
        ).exists()

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
