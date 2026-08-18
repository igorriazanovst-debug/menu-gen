"""MG_CONSTRUCTOR: API ручного конструктора меню (для специалистов/стаффа)."""

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
