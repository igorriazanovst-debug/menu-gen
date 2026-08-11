from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.menu.serializers import MenuDetailSerializer

from .access import Section, permissions_for
from .journal import log_action
from .models import Recommendation, Specialist, SpecialistAssignment
from .serializers import (
    ClientFamilySerializer,
    ClientMenuListSerializer,
    RecommendationSerializer,
    RecommendationWriteSerializer,
    SpecialistProfileSerializer,
    SpecialistVerifySerializer,
)


def _get_specialist(user):
    try:
        return user.specialist_profile
    except Specialist.DoesNotExist:
        return None


# MG_205_V = 1: класс перемещён в apps/specialists/permissions.py
from .permissions import IsVerifiedSpecialist, SpecialistSectionPermission  # noqa: F401,E402  re-export

# MG_SPECACCESS: у вьюх кабинета проверка доступа теперь одна на всех —
# SpecialistSectionPermission. Она находит активное назначение, сверяет роль с
# матрицей и кладёт назначение в request.assignment. Раньше каждая вьюха
# повторяла проверку назначения своими руками, а роль не сверялась вовсе:
# тренер мог править меню, повар — коридор калорий.
CABINET_PERMISSIONS = [permissions.IsAuthenticated, SpecialistSectionPermission]

# ── Профиль специалиста ──────────────────────────────────────────────────────


class SpecialistProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: SpecialistProfileSerializer})
    def get(self, request):
        specialist = _get_specialist(request.user)
        if not specialist:
            return Response({"detail": "Профиль специалиста не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SpecialistProfileSerializer(specialist).data)


# ── Верификация (самозаявка) ─────────────────────────────────────────────────


class SpecialistRegisterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=SpecialistVerifySerializer, responses={201: SpecialistProfileSerializer})
    def post(self, request):
        if hasattr(request.user, "specialist_profile"):
            return Response({"detail": "Профиль специалиста уже существует."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SpecialistVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        specialist = Specialist.objects.create(
            user=request.user,
            specialist_type=serializer.validated_data["specialist_type"],
        )
        return Response(SpecialistProfileSerializer(specialist).data, status=status.HTTP_201_CREATED)


# ── Список клиентов специалиста ──────────────────────────────────────────────


class CabinetClientListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVerifiedSpecialist]

    @extend_schema(responses={200: ClientFamilySerializer(many=True)})
    def get(self, request):
        specialist = _get_specialist(request.user)
        assignments = (
            SpecialistAssignment.objects.filter(
                specialist=specialist,
                status=SpecialistAssignment.Status.ACTIVE,
            )
            .select_related("family")
            .prefetch_related("family__members__user")
        )

        families = [a.family for a in assignments]
        serializer = ClientFamilySerializer(families, many=True, context={"specialist": specialist})
        return Response(serializer.data)


# ── Меню клиента ─────────────────────────────────────────────────────────────


class CabinetClientMenuListView(APIView):
    permission_classes = CABINET_PERMISSIONS
    section = Section.MENU

    @extend_schema(responses={200: ClientMenuListSerializer(many=True)})
    def get(self, request, family_id):
        menus = Menu.objects.filter(family_id=family_id).order_by("-generated_at")
        return Response(ClientMenuListSerializer(menus, many=True).data)


class CabinetClientMenuDetailView(APIView):
    permission_classes = CABINET_PERMISSIONS
    section = Section.MENU

    @extend_schema(responses={200: MenuDetailSerializer})
    def get(self, request, family_id, menu_id):
        try:
            menu = Menu.objects.prefetch_related("items__recipe", "items__member__user").get(
                id=menu_id, family_id=family_id
            )
        except Menu.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(MenuDetailSerializer(menu).data)


class CabinetMenuItemSwapView(APIView):
    """Специалист меняет рецепт в позиции меню клиента."""

    permission_classes = CABINET_PERMISSIONS
    section = Section.MENU

    def patch(self, request, family_id, menu_id, item_id):
        try:
            menu = Menu.objects.get(id=menu_id, family_id=family_id)
            item = MenuItem.objects.get(id=item_id, menu=menu)
        except (Menu.DoesNotExist, MenuItem.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)

        recipe_id = request.data.get("recipe_id")
        if not recipe_id:
            return Response({"detail": "recipe_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.recipes.models import Recipe

        try:
            recipe = Recipe.objects.get(id=recipe_id, is_published=True)
        except Recipe.DoesNotExist:
            return Response({"detail": "Рецепт не найден."}, status=status.HTTP_404_NOT_FOUND)

        was = item.recipe.title if item.recipe_id else "—"
        item.recipe = recipe
        item.save(update_fields=["recipe"])
        menu.modified_by = Menu.ModifiedBy.SPECIALIST
        menu.save(update_fields=["modified_by", "updated_at"])
        log_action(
            request.assignment,
            Section.MENU,
            "swap_item",
            summary=f"{was} → {recipe.title}",
            member=item.member,
            object_id=item.id,
        )
        return Response(status=status.HTTP_200_OK)


# ── Рекомендации ─────────────────────────────────────────────────────────────


class CabinetRecommendationListView(APIView):
    # Рекомендации ведёт тот, кто отвечает за цели клиента: у повара раздел
    # профиля только на чтение, поэтому и советы он писать не может.
    permission_classes = CABINET_PERMISSIONS
    section = Section.PROFILE

    @extend_schema(responses={200: RecommendationSerializer(many=True)})
    def get(self, request, family_id):
        assignment = request.assignment

        recs = (
            Recommendation.objects.filter(assignment=assignment).select_related("member__user").order_by("-created_at")
        )
        return Response(RecommendationSerializer(recs, many=True).data)

    @extend_schema(request=RecommendationWriteSerializer, responses={201: RecommendationSerializer})
    def post(self, request, family_id):
        assignment = request.assignment

        serializer = RecommendationWriteSerializer(data=request.data, context={"assignment": assignment})
        serializer.is_valid(raise_exception=True)
        rec = serializer.save(
            assignment=assignment,
            family_id=family_id,
        )
        log_action(
            assignment,
            Section.PROFILE,
            "add_recommendation",
            summary=rec.name,
            member=rec.member,
            object_id=rec.id,
        )
        return Response(RecommendationSerializer(rec).data, status=status.HTTP_201_CREATED)


class CabinetRecommendationDetailView(APIView):
    permission_classes = CABINET_PERMISSIONS
    section = Section.PROFILE

    def _get_rec(self, specialist, family_id, rec_id):
        try:
            return Recommendation.objects.select_related("assignment__specialist").get(
                id=rec_id,
                family_id=family_id,
                assignment__specialist=specialist,
            )
        except Recommendation.DoesNotExist:
            return None

    @extend_schema(request=RecommendationWriteSerializer, responses={200: RecommendationSerializer})
    def patch(self, request, family_id, rec_id):
        specialist = _get_specialist(request.user)
        rec = self._get_rec(specialist, family_id, rec_id)
        if not rec:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = RecommendationWriteSerializer(
            rec, data=request.data, partial=True, context={"assignment": rec.assignment}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_action(request.assignment, Section.PROFILE, "edit_recommendation", summary=rec.name, object_id=rec.id)
        return Response(RecommendationSerializer(rec).data)

    def delete(self, request, family_id, rec_id):
        specialist = _get_specialist(request.user)
        rec = self._get_rec(specialist, family_id, rec_id)
        if not rec:
            return Response(status=status.HTTP_404_NOT_FOUND)
        rec.is_active = False
        rec.save(update_fields=["is_active"])
        log_action(request.assignment, Section.PROFILE, "remove_recommendation", summary=rec.name, object_id=rec.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Управление назначениями (со стороны пользователя) ───────────────────────


class AssignmentInviteView(APIView):
    """Пользователь приглашает специалиста по email."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.users.models import User

        email = (request.data.get("email") or "").strip()
        requested_type = request.data.get("specialist_type")

        if not email:
            return Response({"detail": "Укажите e-mail специалиста."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
            specialist = user.specialist_profile
            if not specialist.is_verified:
                return Response({"detail": "Специалист не верифицирован."}, status=status.HTTP_400_BAD_REQUEST)
        except (User.DoesNotExist, Specialist.DoesNotExist):
            return Response({"detail": "Специалист не найден."}, status=status.HTTP_404_NOT_FOUND)

        # MG_SPECACCESS: роль назначения — та, в которой специалист верифицирован.
        # Иначе приглашающий сам решал бы, какие права выдать: позвать диетолога
        # «поваром» значило бы открыть ему холодильник и списки покупок.
        specialist_type = specialist.specialist_type
        if requested_type and requested_type != specialist_type:
            return Response(
                {"detail": f"Специалист зарегистрирован как «{specialist.get_specialist_type_display()}»."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        family_membership = FamilyMember.objects.filter(user=request.user).select_related("family").first()
        if not family_membership:
            return Response({"detail": "Семья не найдена."}, status=status.HTTP_404_NOT_FOUND)

        family = family_membership.family

        assignment, created = SpecialistAssignment.objects.get_or_create(
            family=family,
            specialist=specialist,
            defaults={"specialist_type": specialist_type, "status": SpecialistAssignment.Status.PENDING},
        )
        if not created:
            return Response({"detail": "Специалист уже привязан."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Приглашение отправлено.", "assignment_id": assignment.id}, status=status.HTTP_201_CREATED
        )


class AssignmentAcceptView(APIView):
    """Специалист принимает назначение."""

    permission_classes = [permissions.IsAuthenticated, IsVerifiedSpecialist]

    def post(self, request, assignment_id):
        specialist = _get_specialist(request.user)
        try:
            assignment = SpecialistAssignment.objects.get(
                id=assignment_id,
                specialist=specialist,
                status=SpecialistAssignment.Status.PENDING,
            )
        except SpecialistAssignment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        assignment.status = SpecialistAssignment.Status.ACTIVE
        assignment.save(update_fields=["status"])
        return Response({"detail": "Назначение принято."})


class AssignmentEndView(APIView):
    """Завершение назначения (специалист или пользователь)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, assignment_id):
        specialist = _get_specialist(request.user)
        family_membership = FamilyMember.objects.filter(user=request.user).select_related("family").first()

        qs = SpecialistAssignment.objects.filter(id=assignment_id)
        if specialist:
            qs = qs.filter(specialist=specialist)
        elif family_membership:
            qs = qs.filter(family=family_membership.family)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            assignment = qs.get()
        except SpecialistAssignment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        assignment.status = SpecialistAssignment.Status.ENDED
        assignment.save(update_fields=["status"])
        return Response({"detail": "Назначение завершено."})


# ── Pending-назначения для специалиста ──────────────────────────────────────


class CabinetPendingAssignmentsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVerifiedSpecialist]

    def get(self, request):
        specialist = _get_specialist(request.user)
        assignments = SpecialistAssignment.objects.filter(
            specialist=specialist,
            status=SpecialistAssignment.Status.PENDING,
        ).select_related("family")
        data = [{"assignment_id": a.id, "family_id": a.family_id, "family_name": a.family.name} for a in assignments]
        return Response(data)
