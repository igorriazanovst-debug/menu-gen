from datetime import date

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember

# MG_605D_V_views: импорт MenuItem для import-from-menu
from apps.menu.models import Menu, MenuItem
from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly

from .models import DiaryEntry, WaterLog
from .permissions import IsDiaryEntryOwner
from .serializers import DiaryCopySerializer  # DIARY_COPY_V3
from .serializers import (
    DiaryEntrySerializer,
    DiaryEntryWriteSerializer,
    DiaryImportSerializer,
    DiaryStatsDaySerializer,
    WaterLogSerializer,
)


def _get_member(user):
    return FamilyMember.objects.filter(user=user).select_related("family").first()


def _resolve_target_member(request, current_member):
    """MG-605.C: разрешаем `?member_id=` с учётом ролей.

    - Без `?member_id=` → возвращает current_member
    - С `?member_id=` равным current_member.id → возвращает current_member
    - С `?member_id=` другого члена своей семьи:
        * если current_member.role == HEAD → разрешаем
        * иначе → PermissionDenied (403)
    - С `?member_id=` чужой семьи / несуществующего → NotFound (404)
    """
    raw = request.query_params.get("member_id")
    if not raw:
        return current_member
    try:
        target_id = int(raw)
    except (TypeError, ValueError):
        raise NotFound("Участник не найден.")
    if target_id == current_member.id:
        return current_member
    target = FamilyMember.objects.select_related("family").filter(pk=target_id, family=current_member.family).first()
    if target is None:
        # Вне области видимости — не светим существование
        raise NotFound("Участник не найден.")
    if current_member.role != FamilyMember.Role.HEAD:
        raise PermissionDenied("Просмотр чужого дневника доступен только главе семьи.")
    return target


class DiaryListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    def get_member(self):
        if not hasattr(self, "_member"):
            self._member = _get_member(self.request.user)
        return self._member

    def _target_member(self):
        if not hasattr(self, "_target_member_cache"):
            current = self.get_member()
            if current is None:
                self._target_member_cache = None
            else:
                self._target_member_cache = _resolve_target_member(self.request, current)
        return self._target_member_cache

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DiaryEntry.objects.none()
        current = self.get_member()
        if not current:
            return DiaryEntry.objects.none()
        target = self._target_member()
        qs = DiaryEntry.objects.filter(member=target).select_related("recipe").order_by("date", "meal_type")
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
        parameters=[
            OpenApiParameter("date", str, description="Фильтр по дате YYYY-MM-DD"),
            OpenApiParameter("member_id", int, description="MG-605.C: просмотр дневника члена семьи (только HEAD)"),
        ],
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
        # POST всегда создаёт запись для самого пользователя — игнорим ?member_id=
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(DiaryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class DiaryEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """MG-605.C: добавлен PATCH (PUT тоже разрешён, но обычно используется PATCH).

    Видеть чужие записи: HEAD — все в своей семье, MEMBER — только свои.
    Редактировать/удалять может только владелец записи.
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly, IsDiaryEntryOwner]
    http_method_names = ["get", "patch", "delete", "head", "options"]
    serializer_class = DiaryEntrySerializer

    def get_member(self):
        if not hasattr(self, "_member"):
            self._member = _get_member(self.request.user)
        return self._member

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return DiaryEntryWriteSerializer
        return DiaryEntrySerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["member"] = self.get_member()
        return ctx

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DiaryEntry.objects.none()
        current = self.get_member()
        if not current:
            return DiaryEntry.objects.none()
        # HEAD видит все записи своей семьи; MEMBER — только свои.
        if current.role == FamilyMember.Role.HEAD:
            return DiaryEntry.objects.filter(member__family=current.family)
        return DiaryEntry.objects.filter(member=current)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # MG-605.C: редактировать `member` запрещено
        request.data.pop("member", None)
        return super().update(request, *args, **kwargs)


# MG_605D_V_views: helper для вычисления КБЖУ одной записи
_NUTRITION_KEYS = ("calories", "proteins", "fats", "carbs")


def _entry_nutrition(entry):
    """Вернуть dict {calories, proteins, fats, carbs} для записи DiaryEntry,
    учитывая quantity. Безопасно к битым/частичным nutrition."""
    nutr = entry.nutrition or {}
    qty = float(entry.quantity or 1)
    out = {}
    for key in _NUTRITION_KEYS:
        # DIARY_STATS_FLAT_V5: nutrition value may be a flat number, a numeric
        # string, or a legacy {"value": ...} dict. Support all three.
        raw = nutr.get(key)
        try:
            if isinstance(raw, dict):
                val = float(raw.get("value", 0) or 0)
            elif raw is None:
                val = 0.0
            else:
                val = float(raw)
            out[key] = val * qty
        except (TypeError, ValueError, AttributeError):
            out[key] = 0.0
    return out


def _empty_bucket():
    return {k: 0.0 for k in _NUTRITION_KEYS}


def _add_bucket(dst, src):
    for k in _NUTRITION_KEYS:
        dst[k] += src[k]


class DiaryStatsView(APIView):
    """MG-605.D: возвращает за каждый день {date, planned, actual, total}.

    - planned: записи с planned_menu_item IS NOT NULL (что было запланировано)
    - actual:  is_eaten=True ИЛИ planned_menu_item IS NULL
               (вручную добавленное всегда учитывается в факте; плановое — только после галочки)
    - total:   синоним actual (для UI прогресс-бара)
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Дата от YYYY-MM-DD"),
            OpenApiParameter("to", str, description="Дата до YYYY-MM-DD"),
            OpenApiParameter("member_id", int, description="MG-605.C: статистика по члену семьи (только HEAD)"),
        ],
        responses={200: DiaryStatsDaySerializer(many=True)},
    )
    def get(self, request):
        current = _get_member(request.user)
        if not current:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)

        target = _resolve_target_member(request, current)

        date_from = request.query_params.get("from", str(date.today()))
        date_to = request.query_params.get("to", str(date.today()))

        entries = DiaryEntry.objects.filter(member=target, date__gte=date_from, date__lte=date_to)

        stats: dict = {}
        for entry in entries:
            d = str(entry.date)
            if d not in stats:
                stats[d] = {
                    "date": d,
                    "planned": _empty_bucket(),
                    "actual": _empty_bucket(),
                    "total": _empty_bucket(),
                }
            nutr = _entry_nutrition(entry)

            # DIARY_COPY_V3: plan flag = explicit field OR legacy menu link.
            is_planned = bool(getattr(entry, "is_planned", False)) or (entry.planned_menu_item_id is not None)
            # actual: is_eaten=True ИЛИ запись без плана (manual)
            is_actual = entry.is_eaten or (not is_planned)

            if is_planned:
                _add_bucket(stats[d]["planned"], nutr)
            if is_actual:
                _add_bucket(stats[d]["actual"], nutr)
                _add_bucket(stats[d]["total"], nutr)

        return Response(sorted(stats.values(), key=lambda x: x["date"]))


class DiaryImportFromMenuView(APIView):
    """MG-605.D: POST /api/v1/diary/import-from-menu/?menu_id=&date=

    Импортирует все MenuItem указанного меню как плановые записи DiaryEntry
    на указанную дату для target-члена семьи.

    Правила:
    - target_member определяется через _resolve_target_member (?member_id=),
      по умолчанию = текущий FamilyMember; MEMBER не может импортировать чужим.
    - Импортируются только MenuItem с (member == target ИЛИ member IS NULL).
    - Идемпотентно: записи с уже существующим planned_menu_item пропускаются (no-op).
    - Меню должно принадлежать семье target-члена; иначе 404.
    - Ответ 200: {created: N, skipped: M, entries: [...]} (полный список DiaryEntry
      для этого меню+target, включая ранее существующие, чтобы UI мог сразу отрисовать).
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    @extend_schema(
        parameters=[
            OpenApiParameter("menu_id", int, description="ID меню для импорта"),
            OpenApiParameter("date", str, description="Дата плана YYYY-MM-DD"),
            OpenApiParameter("member_id", int, description="Импорт за члена семьи (только HEAD)"),
        ],
        responses={200: DiaryEntrySerializer(many=True)},
    )
    def post(self, request):
        current = _get_member(request.user)
        if not current:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)

        target = _resolve_target_member(request, current)

        # Валидация query-параметров через сериализатор.
        # FILL_FROM_MENU_V4: menu_id/date come via query; item_ids via body.
        merged = {**request.query_params.dict()}
        body_item_ids = request.data.get("item_ids") if hasattr(request, "data") else None
        if body_item_ids is not None:
            merged["item_ids"] = body_item_ids
        params_serializer = DiaryImportSerializer(data=merged)
        params_serializer.is_valid(raise_exception=True)
        menu_id = params_serializer.validated_data["menu_id"]
        plan_date = params_serializer.validated_data["date"]
        sel_item_ids = params_serializer.validated_data.get("item_ids") or []

        # Меню должно принадлежать семье target-члена.
        menu = Menu.objects.filter(pk=menu_id, family=target.family).first()
        if menu is None:
            return Response({"detail": "Меню не найдено."}, status=status.HTTP_404_NOT_FOUND)

        # MenuItem'ы: только те, что для target (или общие — member IS NULL).
        items_qs = MenuItem.objects.filter(menu=menu).filter(member__in=[target]).select_related(
            "recipe"
        ) | MenuItem.objects.filter(menu=menu, member__isnull=True).select_related("recipe")
        items_qs = items_qs.distinct()
        # FILL_FROM_MENU_V4: if a subset was requested, keep only those MenuItems.
        if sel_item_ids:
            items_qs = items_qs.filter(id__in=sel_item_ids)

        created_count = 0
        skipped_count = 0
        created_or_existing = []

        with transaction.atomic():
            for mi in items_qs:
                # Идемпотентность через UNIQUE на planned_menu_item.
                entry, was_created = DiaryEntry.objects.get_or_create(
                    planned_menu_item=mi,
                    defaults={
                        "member": target,
                        "date": plan_date,
                        "meal_type": mi.meal_type,
                        "recipe": mi.recipe,
                        "custom_name": "",
                        "nutrition": getattr(mi.recipe, "nutrition", {}) or {},
                        "quantity": mi.quantity,
                        "is_eaten": False,
                        "is_planned": True,  # DIARY_COPY_V3
                    },
                )
                if was_created:
                    created_count += 1
                else:
                    skipped_count += 1
                created_or_existing.append(entry)

        return Response(
            {
                "created": created_count,
                "skipped": skipped_count,
                "entries": DiaryEntrySerializer(created_or_existing, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class WaterLogView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

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


# DIARY_COPY_V3: copy selected entries from any day into target day as PLAN.
class DiaryCopyView(APIView):
    """POST /api/v1/diary/copy/?member_id=

    Body: {"entry_ids": [int, ...], "target_date": "YYYY-MM-DD"}

    Copies the chosen diary entries (which must be visible to the target member)
    into ``target_date`` as planned entries (is_planned=True, is_eaten=False,
    planned_menu_item=None). Source entries are left untouched.

    Access:
    - target member resolved via _resolve_target_member (?member_id=, HEAD-only
      for other members).
    - only entries belonging to the target member can be copied; anything else
      is silently ignored (we never leak existence of other members' rows).
    """

    permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]

    @extend_schema(
        parameters=[
            OpenApiParameter("member_id", int, description="Copy into a member diary (HEAD only)"),  # DIARY_COPY_V3
        ],
        request=DiaryCopySerializer,
        responses={201: DiaryEntrySerializer(many=True)},
    )
    def post(self, request):
        current = _get_member(request.user)
        if not current:
            return Response({"detail": "Участник не найден."}, status=status.HTTP_404_NOT_FOUND)

        target = _resolve_target_member(request, current)

        body = DiaryCopySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        entry_ids = body.validated_data["entry_ids"]
        target_date = body.validated_data["target_date"]

        # Only entries owned by the target member can be copied.
        sources = list(DiaryEntry.objects.filter(pk__in=entry_ids, member=target).select_related("recipe"))

        created = []
        with transaction.atomic():
            for src in sources:
                created.append(
                    DiaryEntry.objects.create(
                        member=target,
                        date=target_date,
                        meal_type=src.meal_type,
                        recipe=src.recipe,
                        custom_name=src.custom_name,
                        nutrition=src.nutrition or {},
                        quantity=src.quantity,
                        planned_menu_item=None,
                        is_eaten=False,
                        is_planned=True,
                    )
                )

        return Response(
            DiaryEntrySerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )
