from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .invites import notify_invited  # MG_FAMINVITE
from .models import FamilyInvite, FamilyMember
from .selection import current_family, current_membership, memberships  # MG_ONEFAMILY
from .serializers import AttachAccountSerializer  # MG_MANAGEDMEMBER
from .serializers import CreateManagedMemberSerializer  # MG_MANAGEDMEMBER
from .serializers import FamilyChoiceSerializer  # MG_ACTIVEFAMILY
from .serializers import FamilyInviteRespondSerializer  # MG_FAMINVITE
from .serializers import FamilyInviteSerializer  # MG_FAMINVITE
from .serializers import FamilySwitchSerializer  # MG_ACTIVEFAMILY
from .serializers import FamilyMemberSerializer, FamilyMemberUpdateSerializer, FamilySerializer, InviteMemberSerializer

User = get_user_model()


def _get_user_family(user):
    # MG_ONEFAMILY: правило выбора семьи — одно на весь проект, см. selection.py.
    return current_family(user)


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


# ── MG_ACTIVEFAMILY: несколько семей и переключение между ними ───────────────
#
# Человек может состоять в нескольких семьях: своя заводится при регистрации,
# плюс те, куда его пригласили. Работает он в каждый момент в одной — так решено
# сознательно. Плюс: никогда не возникает вопроса «в чей холодильник положить
# купленное молоко», всё кладётся туда, за каким столом человек сейчас. Минус:
# чтобы отметить своё, находясь за родительским столом, надо переключиться.
#
# Две ручки: список столов и выбор стола. Больше ничего не требуется — все
# остальные разделы читают выбор через family/selection.py.


def _family_choices(user):
    """Список семей человека для переключателя, с пометкой активной."""
    from apps.subscriptions.permissions import has_active_premium

    rows = memberships(user)
    active = current_membership(user)
    active_id = active.family_id if active else None
    out = []
    for row in rows:
        family = row.family
        out.append(
            {
                "id": family.id,
                "name": family.name,
                "role": row.role,
                "is_active": family.id == active_id,
                "is_own": family.owner_id == user.id,
                "members_count": family.members.count(),
                "has_premium": has_active_premium(family),
            }
        )
    return out


class FamilyChoicesView(APIView):
    """GET /family/choices/ — где я состою и за каким столом сижу сейчас.

    Список всегда содержит хотя бы свою семью, поэтому пустым не бывает у тех,
    кто зарегистрировался обычным путём.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: FamilyChoiceSerializer(many=True)})
    def get(self, request):
        return Response(FamilyChoiceSerializer(_family_choices(request.user), many=True).data)


class FamilySwitchView(APIView):
    """POST /family/switch/ {"family_id": N} — сесть за другой стол.

    Переключить можно только на ту семью, где человек состоит: чужая семья
    отвечает 404 и не подтверждает даже своё существование.

    Ответ — тот же список, что у GET /family/choices/, уже с новой пометкой
    активной: клиенту после переключения нужно перерисовать переключатель, и
    отдельный запрос за этим слать незачем.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=FamilySwitchSerializer, responses={200: FamilyChoiceSerializer(many=True)})
    def post(self, request):
        serializer = FamilySwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family_id = serializer.validated_data["family_id"]

        if not FamilyMember.objects.filter(user=request.user, family_id=family_id).exists():
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        request.user.active_family_id = family_id
        request.user.save(update_fields=["active_family", "updated_at"])
        return Response(FamilyChoiceSerializer(_family_choices(request.user), many=True).data)


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

        email = (serializer.validated_data.get("email") or "").strip()
        phone = (serializer.validated_data.get("phone") or "").strip()

        # MG_EMAILCI: e-mail регистронезависимо при поиске приглашаемого.
        if email:
            invitee = User.objects.filter(email__iexact=email).order_by("id").first()
        else:
            invitee = User.objects.filter(phone=phone).order_by("id").first()
        if invitee is None:
            return Response(
                {"detail": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if FamilyMember.objects.filter(family=family, user=invitee).exists():
            return Response(
                {"detail": "Пользователь уже в семье."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitee.id == request.user.id:
            return Response(
                {"detail": "Нельзя пригласить самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверка лимита по тарифу (free → лимит free-плана). Здесь она
        # предупредительная: между приглашением и ответом состав семьи может
        # поменяться, поэтому при принятии лимит считается заново.
        limit, plan_name = _member_limit_info(family)
        if family.members.count() >= limit:
            return Response(
                {"detail": f"Лимит участников для тарифа «{plan_name}» исчерпан ({limit})."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # MG_FAMINVITE: приглашаем, а не зачисляем. Членство появится только
        # после согласия — см. FamilyInviteRespondView.
        invite, _created = FamilyInvite.objects.get_or_create(
            family=family,
            invited_user=invitee,
            defaults={"invited_by": request.user},
        )
        invite.status = FamilyInvite.Status.PENDING
        invite.invited_by = request.user
        invite.responded_at = None
        invite.save(update_fields=["status", "invited_by", "responded_at"])

        notify_invited(invite)
        return Response(FamilyInviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class FamilyInvitesView(APIView):
    """GET /family/invites/ — приглашения, ждущие моего ответа.

    Отвечает списком (обычно пустым): человека могут звать сразу несколько
    семей, и выбирать он должен сам, а не получать первую попавшуюся.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: FamilyInviteSerializer(many=True)})
    def get(self, request):
        rows = (
            FamilyInvite.objects.filter(invited_user=request.user, status=FamilyInvite.Status.PENDING)
            .select_related("family", "invited_by")
            .order_by("-created_at")
        )
        return Response(FamilyInviteSerializer(rows, many=True).data)


class FamilyInviteRespondView(APIView):
    """POST /family/invites/<id>/respond/ {"accept": true|false}

    Согласие — единственный способ попасть в чужую семью. При согласии человек
    сразу садится за этот стол (MG_ACTIVEFAMILY): он только что сказал «да»,
    показывать ему после этого прежнюю семью было бы странно.

    Отказ ничего не ломает: строка остаётся со статусом «отклонено», глава семьи
    может позвать снова, и тогда она вернётся в ожидание.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=FamilyInviteRespondSerializer, responses={200: FamilyInviteSerializer})
    def post(self, request, invite_id):
        body = FamilyInviteRespondSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        accept = body.validated_data["accept"]

        invite = (
            FamilyInvite.objects.select_related("family")
            .filter(pk=invite_id, invited_user=request.user, status=FamilyInvite.Status.PENDING)
            .first()
        )
        if invite is None:
            # Чужое приглашение и уже отвеченное неразличимы снаружи намеренно.
            return Response({"detail": "Приглашение не найдено."}, status=status.HTTP_404_NOT_FOUND)

        if not accept:
            invite.status = FamilyInvite.Status.REJECTED
            invite.responded_at = timezone.now()
            invite.save(update_fields=["status", "responded_at"])
            return Response(FamilyInviteSerializer(invite).data)

        family = invite.family
        # Лимит считаем заново: приглашение могло пролежать, пока семья набралась.
        limit, plan_name = _member_limit_info(family)
        if family.members.count() >= limit:
            return Response(
                {"detail": f"В семье больше нет свободных мест (тариф «{plan_name}», {limit})."},
                status=status.HTTP_403_FORBIDDEN,
            )

        FamilyMember.objects.get_or_create(
            family=family,
            user=request.user,
            defaults={"role": FamilyMember.Role.MEMBER},
        )
        invite.status = FamilyInvite.Status.ACCEPTED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])

        request.user.active_family = family
        request.user.save(update_fields=["active_family", "updated_at"])
        return Response(FamilyInviteSerializer(invite).data)


class FamilyInviteCancelView(APIView):
    """DELETE /family/invites/<id>/ — глава семьи передумал звать."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, invite_id):
        family = _get_user_family(request.user)
        if not family:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if family.owner_id != request.user.id and request.user.user_type != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)

        invite = FamilyInvite.objects.filter(pk=invite_id, family=family, status=FamilyInvite.Status.PENDING).first()
        if invite is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        invite.status = FamilyInvite.Status.CANCELLED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FamilyCreateManagedMemberView(APIView):
    """MG_MANAGEDMEMBER: POST /family/members/create-managed/

    Create a family member card WITHOUT inviting an existing user — e.g. a child
    with no device, or someone whose nutrition a specialist will manage. Creates
    a managed User (no login: blank e-mail/phone, unusable password) plus a
    Profile, and adds it to the family. The head can later attach credentials.
    Only the family head / admin may do this.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=CreateManagedMemberSerializer, responses={201: FamilyMemberSerializer})
    def post(self, request):
        family = _get_user_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        if family.owner_id != request.user.id and request.user.user_type != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = CreateManagedMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Subscription member limit (same rule as invite).
        limit, plan_name = _member_limit_info(family)
        if family.members.count() >= limit:
            return Response(
                {"detail": f"Лимит участников для тарифа «{plan_name}» исчерпан ({limit})."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from apps.users.models import Profile

        member_user = User(
            name=data["name"],
            is_managed=True,
            allergies=data.get("allergies") or [],
            disliked_products=data.get("disliked_products") or [],
        )
        member_user.set_unusable_password()
        member_user.save()

        profile = Profile.objects.create(user=member_user)
        profile_data = data.get("profile")
        if profile_data:
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        member = FamilyMember.objects.create(family=family, user=member_user, role=FamilyMember.Role.MEMBER)
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class FamilyAttachAccountView(APIView):
    """MG_MANAGEDMEMBER: POST /family/members/<id>/attach-account/

    Give a managed member their own login by adding e-mail/phone (and optionally
    an initial password). Clears the managed flag so the member can sign in.
    Only the family head / admin may do this.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=AttachAccountSerializer, responses={200: FamilyMemberSerializer})
    def post(self, request, member_id):
        family = _get_user_family(request.user)
        if not family:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)
        if family.owner_id != request.user.id and request.user.user_type != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            member = FamilyMember.objects.select_related("user").get(id=member_id, family=family)
        except FamilyMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not member.user.is_managed:
            return Response(
                {"detail": "У участника уже есть аккаунт."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AttachAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        u = member.user
        if data["email"]:
            u.email = data["email"]
        if data["phone"]:
            u.phone = data["phone"]
        password = data.get("password")
        if password:
            u.set_password(password)
        u.is_managed = False
        u.save()
        return Response(FamilyMemberSerializer(member).data, status=status.HTTP_200_OK)


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

        # MG_ACTIVEFAMILY: человек сидел за этим столом — вернём его к своему.
        # Чтение и без того не доверяет указателю на семью без членства, но
        # оставлять его висеть незачем: он попадёт в выгрузки и будет сбивать с
        # толку при разборе.
        removed_user = member.user
        member.delete()
        if removed_user.active_family_id == family.id:
            removed_user.active_family = None
            removed_user.save(update_fields=["active_family", "updated_at"])
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
        is_self = FamilyMember.objects.filter(family=family, user=request.user, id=member_id).exists()

        # Specialist допускается, если у него есть активный assignment на эту семью
        is_specialist = False
        try:
            from apps.specialists.models import SpecialistAssignment
            from apps.specialists.permissions import _get_specialist

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
            member = FamilyMember.objects.select_related("user__profile").get(id=member_id, family=family)
        except FamilyMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = FamilyMemberUpdateSerializer(member, data=request.data, partial=True, context={"request": request})
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


def _member_limit_info(family):
    """Эффективный лимит участников и имя тарифа.

    Если активной подписки нет — действует бесплатный тариф (free), у которого
    свой лимит (по умолчанию 1). Раньше при отсутствии подписки лимит не
    применялся вовсе — для freemium это закрыто.
    """
    plan = _get_active_plan(family)
    if plan:
        return plan.max_family_members, plan.name
    from apps.subscriptions.quota import free_max_family_members

    return free_max_family_members(), "Бесплатный"


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
    is_self = FamilyMember.objects.filter(family=family, user=request.user, id=member_id).exists()

    is_specialist = False
    try:
        from apps.specialists.models import SpecialistAssignment
        from apps.specialists.permissions import _get_specialist

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
        member = FamilyMember.objects.select_related("user__profile").get(id=member_id, family=family)
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
