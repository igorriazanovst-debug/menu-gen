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
        user = request.user
        # Стафф (админ) видит все семьи — проверяем ПЕРВЫМ, т.к. админ может
        # иметь и профиль специалиста, но при этом не иметь личных назначений.
        if user.is_staff:
            families = Family.objects.all()
        elif _is_specialist(user):
            fam_ids = (
                SpecialistAssignment.objects.filter(
                    specialist__user=user,
                    status__in=[SpecialistAssignment.Status.ACTIVE, SpecialistAssignment.Status.PENDING],
                )
                .values_list("family_id", flat=True)
                .distinct()
            )
            families = Family.objects.filter(id__in=list(fam_ids))
        else:
            families = Family.objects.none()
        data = [{"id": f.id, "name": f.name} for f in families.order_by("name")[:500]]
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
        return ConstructedMenu.objects.filter(author=self.request.user).prefetch_related("meals__items__recipe")

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response(status=status.HTTP_204_NO_CONTENT)
