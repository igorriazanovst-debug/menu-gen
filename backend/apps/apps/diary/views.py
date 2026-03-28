from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from .models import DiaryEntry, WaterLog
from .serializers import (
    DiaryEntrySerializer,
    DiaryEntryWriteSerializer,
    DiaryStatsSerializer,
    WaterLogSerializer,
)


def _get_member(user):
    return FamilyMember.objects.filter(user=user).select_related("family").first()


class DiaryListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_member(self):
        if not hasattr(self, "_member"):
            self._member = _get_member(self.request.user)
        return self._member

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DiaryEntry.objects.none()
        member = self.get_member()
        if not member:
            return DiaryEntry.objects.none()
        qs = DiaryEntry.objects.filter(member=member).select_related("recipe").order_by("date", "meal_type")
        day = self.request.query_params.get("date")
        if day:
            qs = qs.filter(date=day)
        return qs

    def get_serializer_class(self):
        return DiaryEntryWriteSerializer if self.request.method == "POST" else DiaryEntrySerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["member"] = self.get_member()
        return ctx

    @extend_schema(
        parameters=[OpenApiParameter("date", str, description="Фильтр по дате YYYY-MM-DD")],
        responses={200: DiaryEntrySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        if not self.get_member():
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)
        return super().get(request, *args, **kwargs)

    @extend_schema(request=DiaryEntryWriteSerializer, responses={201: DiaryEntrySerializer})
    def post(self, request, *args, **kwargs):
        member = self.get_member()
        if not member:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(DiaryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class DiaryEntryDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DiaryEntrySerializer

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return DiaryEntry.objects.none()
        return DiaryEntry.objects.filter(member=member)


class DiaryStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Дата от YYYY-MM-DD"),
            OpenApiParameter("to", str, description="Дата до YYYY-MM-DD"),
        ],
        responses={200: DiaryStatsSerializer(many=True)},
    )
    def get(self, request):
        member = _get_member(request.user)
        if not member:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)

        date_from = request.query_params.get("from", str(date.today()))
        date_to = request.query_params.get("to", str(date.today()))

        entries = DiaryEntry.objects.filter(member=member, date__gte=date_from, date__lte=date_to)

        stats: dict = {}
        for entry in entries:
            d = str(entry.date)
            if d not in stats:
                stats[d] = {"date": d, "calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0}
            nutr = entry.nutrition or {}
            qty = float(entry.quantity or 1)
            for key in ("calories", "proteins", "fats", "carbs"):
                try:
                    val = float(nutr.get(key, {}).get("value", 0)) * qty
                except (TypeError, ValueError):
                    val = 0
                stats[d][key] += val

        return Response(sorted(stats.values(), key=lambda x: x["date"]))


class WaterLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("date", str, description="Дата YYYY-MM-DD (default: today)")],
        responses={200: WaterLogSerializer},
    )
    def get(self, request):
        member = _get_member(request.user)
        if not member:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)
        day = request.query_params.get("date", str(date.today()))
        obj, _ = WaterLog.objects.get_or_create(member=member, date=day, defaults={"water_ml": 0})
        return Response(WaterLogSerializer(obj).data)

    @extend_schema(request=WaterLogSerializer, responses={200: WaterLogSerializer})
    def post(self, request):
        member = _get_member(request.user)
        if not member:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WaterLogSerializer(data=request.data, context={"member": member})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(WaterLogSerializer(obj).data)
