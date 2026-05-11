#!/bin/bash
# MG-605.C — Premium gate + member_id filter + PATCH владельцем
# Расположение: /opt/menugen/backend/scripts/patch_605c.sh
# Запуск:
#   bash /opt/menugen/backend/scripts/patch_605c.sh 2>&1 | tee /tmp/patch_605c.log

set -eu
PROJECT_DIR="${PROJECT_DIR:-/opt/menugen}"
BACKEND_DIR="$PROJECT_DIR/backend"
cd "$PROJECT_DIR"

echo "===================================================================="
echo "PATCH-605.C — старт"
echo "===================================================================="

# ─────────────────────────────────────────────────────────────────────────
# 1) apps/subscriptions/permissions.py — Premium-хелпер + DRF-класс
# ─────────────────────────────────────────────────────────────────────────
cat > "$BACKEND_DIR/apps/subscriptions/permissions.py" <<'PYEOF'
"""MG-605.C: Premium gate.

Хелпер `has_active_premium(family)` и DRF-permission `IsFamilyPremium`.

Premium = у семьи есть подписка с:
- plan.code == 'premium'
- status IN ('active', 'trial')
- expires_at > now()
"""
from django.utils import timezone
from rest_framework import permissions

from apps.family.models import FamilyMember
from .models import Subscription


PREMIUM_PLAN_CODE = "premium"
PREMIUM_ACTIVE_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.TRIAL)


def has_active_premium(family) -> bool:
    """Возвращает True, если у семьи есть активная Premium-подписка."""
    if family is None:
        return False
    return Subscription.objects.filter(
        family=family,
        plan__code=PREMIUM_PLAN_CODE,
        status__in=PREMIUM_ACTIVE_STATUSES,
        expires_at__gt=timezone.now(),
    ).exists()


def get_user_family(user):
    """Возвращает Family пользователя (через FamilyMember) или None."""
    if not user or not user.is_authenticated:
        return None
    membership = (
        FamilyMember.objects.select_related("family")
        .filter(user=user)
        .first()
    )
    return membership.family if membership else None


class IsFamilyPremium(permissions.BasePermission):
    """Разрешает доступ только если у семьи пользователя активна Premium."""

    message = "Требуется активная Premium-подписка."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        family = get_user_family(request.user)
        return has_active_premium(family)
PYEOF
echo "✓ создан apps/subscriptions/permissions.py"

# ─────────────────────────────────────────────────────────────────────────
# 2) apps/diary/permissions.py — IsDiaryEntryOwner (для PATCH/DELETE)
# ─────────────────────────────────────────────────────────────────────────
cat > "$BACKEND_DIR/apps/diary/permissions.py" <<'PYEOF'
"""MG-605.C: права на конкретную запись дневника.

IsDiaryEntryOwner — редактировать/удалять может только владелец записи
(member которой = FamilyMember текущего user-а).
Просмотр (SAFE_METHODS) уже ограничен через get_queryset.
"""
from rest_framework import permissions

from apps.family.models import FamilyMember


class IsDiaryEntryOwner(permissions.BasePermission):
    """Изменять/удалять может только владелец записи."""

    message = "Изменять можно только свои записи."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Владелец = FamilyMember текущего юзера == obj.member
        return FamilyMember.objects.filter(
            user=request.user, pk=obj.member_id
        ).exists()
PYEOF
echo "✓ создан apps/diary/permissions.py"

# ─────────────────────────────────────────────────────────────────────────
# 3) apps/diary/views.py — переписываем целиком
# ─────────────────────────────────────────────────────────────────────────
cat > "$BACKEND_DIR/apps/diary/views.py" <<'PYEOF'
from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
from apps.subscriptions.permissions import IsFamilyPremium

from .models import DiaryEntry, WaterLog
from .permissions import IsDiaryEntryOwner
from .serializers import (
    DiaryEntrySerializer,
    DiaryEntryWriteSerializer,
    DiaryStatsSerializer,
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
    target = (
        FamilyMember.objects.select_related("family")
        .filter(pk=target_id, family=current_member.family)
        .first()
    )
    if target is None:
        # Вне области видимости — не светим существование
        raise NotFound("Участник не найден.")
    if current_member.role != FamilyMember.Role.HEAD:
        raise PermissionDenied("Просмотр чужого дневника доступен только главе семьи.")
    return target


class DiaryListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium]

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
        qs = (
            DiaryEntry.objects.filter(member=target)
            .select_related("recipe")
            .order_by("date", "meal_type")
        )
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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium, IsDiaryEntryOwner]
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


class DiaryStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Дата от YYYY-MM-DD"),
            OpenApiParameter("to", str, description="Дата до YYYY-MM-DD"),
            OpenApiParameter("member_id", int, description="MG-605.C: статистика по члену семьи (только HEAD)"),
        ],
        responses={200: DiaryStatsSerializer(many=True)},
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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium]

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
PYEOF
echo "✓ обновлён apps/diary/views.py"

# ─────────────────────────────────────────────────────────────────────────
# 4) apps/diary/serializers.py — partial-friendly валидатор
# ─────────────────────────────────────────────────────────────────────────
cat > "$BACKEND_DIR/apps/diary/serializers.py" <<'PYEOF'
from rest_framework import serializers

from .models import DiaryEntry, WaterLog


class DiaryEntrySerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source="recipe.title", read_only=True, default=None)

    class Meta:
        model = DiaryEntry
        fields = (
            "id",
            "date",
            "meal_type",
            "recipe",
            "recipe_title",
            "custom_name",
            "nutrition",
            "quantity",
            "planned_menu_item",  # MG_605B_V_serializers
            "is_eaten",  # MG_605B_V_serializers
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class DiaryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaryEntry
        # MG_605B_V_serializers: план-факт
        # MG-605.C: используется и для POST, и для PATCH (через partial=True)
        fields = (
            "date", "meal_type", "recipe", "custom_name",
            "nutrition", "quantity", "planned_menu_item", "is_eaten",
        )

    def validate(self, attrs):
        # MG-605.C: на PATCH (partial) валидируем «recipe или custom_name»
        # с учётом instance — иначе любой PATCH без recipe ронял бы запись.
        recipe = attrs.get("recipe", getattr(self.instance, "recipe", None))
        custom_name = attrs.get("custom_name", getattr(self.instance, "custom_name", ""))
        if not recipe and not custom_name:
            raise serializers.ValidationError("Укажите рецепт или название блюда.")
        return attrs

    def create(self, validated_data):
        member = self.context["member"]
        if not validated_data.get("nutrition") and validated_data.get("recipe"):
            validated_data["nutrition"] = validated_data["recipe"].nutrition or {}
        return DiaryEntry.objects.create(member=member, **validated_data)


class DiaryStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    calories = serializers.FloatField()
    proteins = serializers.FloatField()
    fats = serializers.FloatField()
    carbs = serializers.FloatField()


class WaterLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterLog
        fields = ("id", "date", "water_ml")
        read_only_fields = ("id",)

    def create(self, validated_data):
        member = self.context["member"]
        obj, _ = WaterLog.objects.get_or_create(
            member=member,
            date=validated_data["date"],
            defaults={"water_ml": 0},
        )
        obj.water_ml = validated_data["water_ml"]
        obj.save(update_fields=["water_ml"])
        return obj
PYEOF
echo "✓ обновлён apps/diary/serializers.py"

# ─────────────────────────────────────────────────────────────────────────
# 5) Тесты MG-605.C
# ─────────────────────────────────────────────────────────────────────────
cat > "$BACKEND_DIR/apps/diary/tests/test_mg_605c_permissions.py" <<'PYEOF'
"""MG-605.C — Premium gate + ?member_id= + PATCH владельцем.

Покрывает:
- Premium gate (нет подписки → 403)
- ?member_id= для HEAD/MEMBER (403 / 404 / 200)
- PATCH /diary/{id}/ владельцем
- PATCH чужой записи (HEAD/MEMBER) → 404
- Запрет на изменение поля `member` через PATCH
- DELETE сохраняет существующее поведение
- DiaryStats с ?member_id=
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.diary.models import DiaryEntry

User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────


def _make_user(email):
    return User.objects.create_user(email=email, password="pwd12345!")


def _make_family_with_premium(owner_email="head@example.com", with_premium=True):
    head = _make_user(owner_email)
    family = Family.objects.create(owner=head, name="F")
    head_member = FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    if with_premium:
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0"), "period": SubscriptionPlan.Period.MONTH},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=30),
        )
    return family, head, head_member


def _add_member(family, email="m@example.com", role=FamilyMember.Role.MEMBER):
    user = _make_user(email)
    member = FamilyMember.objects.create(family=family, user=user, role=role)
    return user, member


def _make_entry(member, day=None, **kwargs):
    return DiaryEntry.objects.create(
        member=member,
        date=day or date.today(),
        meal_type=DiaryEntry.MealType.BREAKFAST,
        custom_name=kwargs.get("custom_name", "Toast"),
        quantity=kwargs.get("quantity", 1),
        nutrition=kwargs.get("nutrition", {"calories": {"value": 200}}),
    )


def _auth(client, user):
    client.force_authenticate(user=user)
    return client


# ─── 1) Premium gate ────────────────────────────────────────────────────────


class TestPremiumGate:
    def test_no_premium_list_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/")
        assert resp.status_code == 403

    def test_no_premium_stats_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/stats/")
        assert resp.status_code == 403

    def test_no_premium_water_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/water/")
        assert resp.status_code == 403

    def test_expired_premium_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0")},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=60),
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 403

    def test_cancelled_premium_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0")},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.CANCELLED,
            started_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=30),
        )
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 403

    def test_trial_premium_200(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0")},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.TRIAL,
            started_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=7),
        )
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 200

    def test_active_premium_200(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 200


# ─── 2) ?member_id= — HEAD / MEMBER ─────────────────────────────────────────


class TestMemberIdFilter:
    def test_head_can_see_member_diary(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/?member_id={m_member.id}")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in resp.json()]
        assert "MemberMeal" in names

    def test_member_cannot_see_other_member_diary(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        # просим дневник head с аккаунта member
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/?member_id={head_m.id}")
        assert resp.status_code == 403

    def test_member_can_see_own_via_member_id(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, custom_name="OwnMeal")
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/?member_id={m_member.id}")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in resp.json()]
        assert "OwnMeal" in names

    def test_member_id_from_other_family_404(self, db):
        family, head, head_m = _make_family_with_premium("head1@example.com")
        family2, head2, head2_m = _make_family_with_premium("head2@example.com")
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/?member_id={head2_m.id}")
        assert resp.status_code == 404

    def test_member_id_unknown_404(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/?member_id=999999")
        assert resp.status_code == 404

    def test_member_id_invalid_404(self, db):
        family, head, _ = _make_family_with_premium()
        client = _auth(APIClient(), head)
        resp = client.get("/api/v1/diary/?member_id=abc")
        assert resp.status_code == 404

    def test_without_member_id_returns_own(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(head_m, custom_name="HeadMeal")
        _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), m_user)
        resp = client.get("/api/v1/diary/")
        assert resp.status_code == 200
        names = [e["custom_name"] for e in resp.json()]
        assert "MemberMeal" in names and "HeadMeal" not in names


# ─── 3) PATCH /diary/{id}/ ──────────────────────────────────────────────────


class TestPatchOwner:
    def test_owner_can_patch_own(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A", quantity=1)
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True, "quantity": "2.5"}, format="json")
        assert resp.status_code == 200
        e.refresh_from_db()
        assert e.is_eaten is True
        assert e.quantity == Decimal("2.5")

    def test_member_cannot_patch_head_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(head_m, custom_name="HeadMeal")
        client = _auth(APIClient(), m_user)
        # MEMBER не видит чужую запись через get_queryset → 404
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True}, format="json")
        assert resp.status_code == 404

    def test_head_cannot_patch_member_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(m_member, custom_name="MemberMeal")
        client = _auth(APIClient(), head)
        # HEAD ВИДИТ (queryset включает всю семью), но не владелец → 403 (IsDiaryEntryOwner)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"is_eaten": True}, format="json")
        assert resp.status_code == 403

    def test_patch_cannot_change_member(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"member": m_member.id, "is_eaten": True}, format="json")
        assert resp.status_code == 200
        e.refresh_from_db()
        assert e.member_id == head_m.id  # member не поменялся

    def test_patch_partial_recipe_or_custom_name_ok(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        # пустой PATCH — валидный (recipe или custom_name из instance)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"quantity": "3.0"}, format="json")
        assert resp.status_code == 200

    def test_patch_clears_both_fields_fails(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m, custom_name="A")
        client = _auth(APIClient(), head)
        resp = client.patch(f"/api/v1/diary/{e.id}/", {"custom_name": ""}, format="json")
        # recipe=None в instance, custom_name становится '' → ошибка
        assert resp.status_code == 400


# ─── 4) DELETE ──────────────────────────────────────────────────────────────


class TestDelete:
    def test_owner_can_delete_own(self, db):
        family, head, head_m = _make_family_with_premium()
        e = _make_entry(head_m)
        client = _auth(APIClient(), head)
        resp = client.delete(f"/api/v1/diary/{e.id}/")
        assert resp.status_code == 204
        assert not DiaryEntry.objects.filter(pk=e.id).exists()

    def test_head_cannot_delete_member_entry(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        e = _make_entry(m_member)
        client = _auth(APIClient(), head)
        # HEAD видит, но не владелец → 403
        resp = client.delete(f"/api/v1/diary/{e.id}/")
        assert resp.status_code == 403
        assert DiaryEntry.objects.filter(pk=e.id).exists()


# ─── 5) Stats с ?member_id= ─────────────────────────────────────────────────


class TestStatsMemberId:
    def test_head_stats_for_member(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        _make_entry(m_member, nutrition={"calories": {"value": 500}})
        client = _auth(APIClient(), head)
        resp = client.get(f"/api/v1/diary/stats/?member_id={m_member.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["calories"] == 500.0

    def test_member_stats_other_403(self, db):
        family, head, head_m = _make_family_with_premium()
        m_user, m_member = _add_member(family, "m1@example.com")
        client = _auth(APIClient(), m_user)
        resp = client.get(f"/api/v1/diary/stats/?member_id={head_m.id}")
        assert resp.status_code == 403
PYEOF
echo "✓ создан apps/diary/tests/test_mg_605c_permissions.py"

# ─────────────────────────────────────────────────────────────────────────
# 6) Чистка тест-БД и прогон тестов
# ─────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Чистка тест-БД ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='test_menugen' AND pid <> pg_backend_pid();" || true
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
    psql -U menugen_user -d postgres -c "DROP DATABASE IF EXISTS test_menugen;" || true

echo ""
echo "=== Запуск тестов 605.C ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend \
    pytest apps/diary/tests/test_mg_605c_permissions.py -v --tb=short

echo ""
echo "=== Полный регресс diary ==="
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T backend \
    pytest apps/diary/ -v --tb=short

echo ""
echo "===================================================================="
echo "PATCH-605.C — готово"
echo "===================================================================="
