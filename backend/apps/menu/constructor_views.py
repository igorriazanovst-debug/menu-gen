"""MG_CONSTRUCTOR: API ручного конструктора меню (для специалистов/стаффа)."""

from datetime import date

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import Family
from apps.specialists.models import SpecialistAssignment

from .constructor_serializers import ConstructedMenuListSerializer, ConstructedMenuSerializer
from .models import ConstructedMenu


def _is_specialist(user):
    return hasattr(user, "specialist_profile")


def allowed_family_ids(user):
    """Семьи, для которых пользователь вправе строить меню в конструкторе.

    Ровно те, где у специалиста активное назначение — то же правило, что даёт
    доступ к данным клиента (access.active_assignment). Раньше конструктор жил
    по своему правилу: staff видел все семьи, а список включал ещё и PENDING —
    и специалист видел (а на записи и мог привязать меню к) семьям, которые
    доступа ему не давали. Теперь список и запись сверяются с одним и тем же.
    """
    if not _is_specialist(user):
        return set()
    return set(
        SpecialistAssignment.objects.filter(
            specialist__user=user,
            status=SpecialistAssignment.Status.ACTIVE,
        )
        .values_list("family_id", flat=True)
        .distinct()
    )


class IsSpecialistOrStaff(permissions.BasePermission):
    """Доступ к конструктору: стафф или пользователь-специалист.

    «Определённых пользователей» добавим позже — здесь одна точка расширения.
    """

    message = "Конструктор меню доступен только специалистам."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or _is_specialist(user)))


class ConstructorClientsView(APIView):
    """Список клиентов (семей), для которых можно строить меню."""

    permission_classes = [permissions.IsAuthenticated, IsSpecialistOrStaff]

    def get(self, request):
        # Даже админу — только семьи с активным назначением. Для сквозного
        # доступа к любым семьям есть Django-админка; конструктор им не место.
        fam_ids = allowed_family_ids(request.user)
        families = Family.objects.filter(id__in=fam_ids).order_by("name")[:500]
        data = [{"id": f.id, "name": f.name} for f in families]
        return Response(data)


class ConstructedMenuListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsSpecialistOrStaff]
    pagination_class = None  # отдаём плоский список (фронт ждёт массив)

    def get_queryset(self):
        return ConstructedMenu.objects.filter(author=self.request.user).prefetch_related("meals")

    def get_serializer_class(self):
        return ConstructedMenuListSerializer if self.request.method == "GET" else ConstructedMenuSerializer


class ConstructedMenuDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsSpecialistOrStaff]
    serializer_class = ConstructedMenuSerializer

    def get_queryset(self):
        return ConstructedMenu.objects.filter(author=self.request.user).prefetch_related(
            "meals__items__recipe", "meals__items__product__category_fk"
        )

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConstructedMenuApplyView(APIView):
    """MG_MENUAPPLY: выдать составленное меню клиенту.

    POST /menu/constructor/<pk>/apply/  {"start_date": "YYYY-MM-DD"}

    Право на выдачу — не то же, что право строить: конструктор открыт всем
    специалистам, а класть меню в чужую семью может только роль, у которой меню
    на запись (диетолог, повар). Тренер меню читает — выдать не может.
    """

    permission_classes = [permissions.IsAuthenticated, IsSpecialistOrStaff]

    def post(self, request, pk):
        from apps.specialists.access import Section, active_assignment, allows
        from apps.specialists.journal import log_action

        from .constructor_apply import apply_to_family

        menu = ConstructedMenu.objects.filter(id=pk, author=request.user).first()
        if menu is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if menu.client_family_id is None:
            return Response(
                {"detail": "Меню не привязано к клиенту — выдавать некому."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        specialist = getattr(request.user, "specialist_profile", None)
        assignment = active_assignment(specialist, menu.client_family_id)
        if assignment is None or not allows(assignment, Section.MENU, write=True):
            return Response(
                {"detail": "Ваша роль не даёт права выдавать меню этому клиенту."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw = request.data.get("start_date")
        try:
            start = date.fromisoformat(raw) if raw else date.today()
        except (TypeError, ValueError):
            return Response({"detail": "Некорректная дата начала."}, status=status.HTTP_400_BAD_REQUEST)

        created = apply_to_family(menu, start, request.user)
        log_action(
            assignment,
            Section.MENU,
            "apply_menu",
            summary=f"{menu.name} → меню с {start}",
            object_id=created.id,
        )
        return Response(
            {
                "menu_id": created.id,
                "start_date": str(created.start_date),
                "end_date": str(created.end_date),
                "items": created.items.count(),
            },
            status=status.HTTP_201_CREATED,
        )
