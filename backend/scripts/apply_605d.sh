#!/usr/bin/env bash
# MG-605.D apply:
#   - POST /api/v1/diary/import-from-menu/?menu_id=&date=
#   - GET /api/v1/diary/stats/ → новая вложенная структура {planned, actual, total}
#   - тесты + правка существующих stats-тестов под новый формат
set -euo pipefail

ROOT="/opt/menugen"
BACKEND="$ROOT/backend"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"
DIARY="$BACKEND/apps/diary"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="/tmp/mg_605d_backup_${TS}"

mkdir -p "$BAK"
echo "[1/7] Backup → $BAK"
for f in views.py serializers.py urls.py tests/test_diary.py tests/test_mg_605c_permissions.py; do
  cp -v "$DIARY/$f" "$BAK/$(basename $f)"
done
echo

# ─────────────────────────────────────────────────────────────────────────────
# [2/7] serializers.py — добавить DiaryImportSerializer + DiaryStatsDaySerializer
# ─────────────────────────────────────────────────────────────────────────────
echo "[2/7] serializers.py — добавляем DiaryImportSerializer + DiaryStatsDaySerializer"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/serializers.py")
src = p.read_text(encoding="utf-8")

if "MG_605D_V_serializers" in src:
    print("  serializers.py: уже пропатчен")
    raise SystemExit(0)

# Заменяем старый DiaryStatsSerializer на новую структуру и добавляем DiaryImportSerializer.
old = '''class DiaryStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    calories = serializers.FloatField()
    proteins = serializers.FloatField()
    fats = serializers.FloatField()
    carbs = serializers.FloatField()
'''

new = '''# MG_605D_V_serializers: вложенная структура план/факт.
class _NutritionBucketSerializer(serializers.Serializer):
    calories = serializers.FloatField()
    proteins = serializers.FloatField()
    fats = serializers.FloatField()
    carbs = serializers.FloatField()


class DiaryStatsDaySerializer(serializers.Serializer):
    """MG-605.D: возвращает {date, planned, actual, total}.

    - planned: суммы по записям с planned_menu_item IS NOT NULL
    - actual:  суммы по записям, считающимся «съеденными»:
               is_eaten = True ИЛИ planned_menu_item IS NULL
               (вручную добавленное считаем фактом сразу; плановое — только после галочки)
    - total:   синоним actual (для UI прогресс-бара)
    """
    date = serializers.DateField()
    planned = _NutritionBucketSerializer()
    actual = _NutritionBucketSerializer()
    total = _NutritionBucketSerializer()


# Обратная совместимость на случай внешних импортов.
DiaryStatsSerializer = DiaryStatsDaySerializer


class DiaryImportSerializer(serializers.Serializer):
    """MG-605.D: query-params для POST /diary/import-from-menu/."""
    menu_id = serializers.IntegerField()
    date = serializers.DateField()
'''

assert old in src, "ОШИБКА: не нашёл DiaryStatsSerializer для замены"
src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
print("  ✓ serializers.py обновлён")
PYEOF
echo

# ─────────────────────────────────────────────────────────────────────────────
# [3/7] views.py — переписать DiaryStatsView + добавить DiaryImportFromMenuView
# ─────────────────────────────────────────────────────────────────────────────
echo "[3/7] views.py — DiaryStatsView (новая структура) + DiaryImportFromMenuView"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/views.py")
src = p.read_text(encoding="utf-8")

if "MG_605D_V_views" in src:
    print("  views.py: уже пропатчен")
    raise SystemExit(0)

# 1) Импорты
old_imports = '''from datetime import date

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
'''

new_imports = '''from datetime import date

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.models import FamilyMember
# MG_605D_V_views: импорт MenuItem для import-from-menu
from apps.menu.models import Menu, MenuItem
from apps.subscriptions.permissions import IsFamilyPremium

from .models import DiaryEntry, WaterLog
from .permissions import IsDiaryEntryOwner
from .serializers import (
    DiaryEntrySerializer,
    DiaryEntryWriteSerializer,
    DiaryImportSerializer,
    DiaryStatsDaySerializer,
    WaterLogSerializer,
)
'''
assert old_imports in src, "ОШИБКА: не нашёл блок импортов"
src = src.replace(old_imports, new_imports, 1)

# 2) Заменяем DiaryStatsView целиком
old_stats = '''class DiaryStatsView(APIView):
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
'''

new_stats = '''# MG_605D_V_views: helper для вычисления КБЖУ одной записи
_NUTRITION_KEYS = ("calories", "proteins", "fats", "carbs")


def _entry_nutrition(entry):
    """Вернуть dict {calories, proteins, fats, carbs} для записи DiaryEntry,
    учитывая quantity. Безопасно к битым/частичным nutrition."""
    nutr = entry.nutrition or {}
    qty = float(entry.quantity or 1)
    out = {}
    for key in _NUTRITION_KEYS:
        try:
            out[key] = float(nutr.get(key, {}).get("value", 0)) * qty
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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium]

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

        entries = DiaryEntry.objects.filter(
            member=target, date__gte=date_from, date__lte=date_to
        )

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

            is_planned = entry.planned_menu_item_id is not None
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
    permission_classes = [permissions.IsAuthenticated, IsFamilyPremium]

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
        params_serializer = DiaryImportSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        menu_id = params_serializer.validated_data["menu_id"]
        plan_date = params_serializer.validated_data["date"]

        # Меню должно принадлежать семье target-члена.
        menu = Menu.objects.filter(pk=menu_id, family=target.family).first()
        if menu is None:
            return Response({"detail": "Меню не найдено."}, status=status.HTTP_404_NOT_FOUND)

        # MenuItem'ы: только те, что для target (или общие — member IS NULL).
        items_qs = MenuItem.objects.filter(menu=menu).filter(
            member__in=[target]
        ).select_related("recipe") | MenuItem.objects.filter(
            menu=menu, member__isnull=True
        ).select_related("recipe")
        items_qs = items_qs.distinct()

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
'''

assert old_stats in src, "ОШИБКА: не нашёл DiaryStatsView для замены"
src = src.replace(old_stats, new_stats, 1)

p.write_text(src, encoding="utf-8")
print("  ✓ views.py обновлён")
PYEOF
echo

# ─────────────────────────────────────────────────────────────────────────────
# [4/7] urls.py — добавить маршрут import-from-menu
# ─────────────────────────────────────────────────────────────────────────────
echo "[4/7] urls.py — добавить маршрут diary-import-from-menu"

python3 <<'PYEOF'
from pathlib import Path
p = Path("/opt/menugen/backend/apps/diary/urls.py")
src = p.read_text(encoding="utf-8")

if "DiaryImportFromMenuView" in src:
    print("  urls.py: уже пропатчен")
    raise SystemExit(0)

old = '''from .views import DiaryEntryDetailView, DiaryListCreateView, DiaryStatsView, WaterLogView

urlpatterns = [
    path("", DiaryListCreateView.as_view(), name="diary-list"),
    path("<int:pk>/", DiaryEntryDetailView.as_view(), name="diary-entry-detail"),
    path("stats/", DiaryStatsView.as_view(), name="diary-stats"),
    path("water/", WaterLogView.as_view(), name="diary-water"),
]
'''

new = '''from .views import (
    DiaryEntryDetailView,
    DiaryImportFromMenuView,
    DiaryListCreateView,
    DiaryStatsView,
    WaterLogView,
)

urlpatterns = [
    path("", DiaryListCreateView.as_view(), name="diary-list"),
    path("<int:pk>/", DiaryEntryDetailView.as_view(), name="diary-entry-detail"),
    path("stats/", DiaryStatsView.as_view(), name="diary-stats"),
    path("water/", WaterLogView.as_view(), name="diary-water"),
    # MG_605D_V_urls
    path("import-from-menu/", DiaryImportFromMenuView.as_view(), name="diary-import-from-menu"),
]
'''
assert old in src, "ОШИБКА: не нашёл urls.py блок"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("  ✓ urls.py обновлён")
PYEOF
echo

# ─────────────────────────────────────────────────────────────────────────────
# [5/7] Правка старых тестов под новый формат stats
# ─────────────────────────────────────────────────────────────────────────────
echo "[5/7] Правка test_diary.py и test_mg_605c_permissions.py под {planned, actual, total}"

python3 <<'PYEOF'
from pathlib import Path

# test_diary.py:136 — assert resp.data[0]["calories"] == 300.0
p1 = Path("/opt/menugen/backend/apps/diary/tests/test_diary.py")
src1 = p1.read_text(encoding="utf-8")
old1 = 'assert resp.data[0]["calories"] == 300.0'
new1 = (
    '# MG-605.D: вложенная структура; запись без planned_menu_item → actual\n'
    '        assert resp.data[0]["actual"]["calories"] == 300.0\n'
    '        assert resp.data[0]["total"]["calories"] == 300.0\n'
    '        assert resp.data[0]["planned"]["calories"] == 0.0'
)
if old1 in src1:
    src1 = src1.replace(old1, new1, 1)
    p1.write_text(src1, encoding="utf-8")
    print("  ✓ test_diary.py обновлён")
else:
    print("  ! test_diary.py: assert уже исправлен или не найден")

# test_mg_605c_permissions.py:318 — assert data[0]["calories"] == 500.0
p2 = Path("/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py")
src2 = p2.read_text(encoding="utf-8")
old2 = 'assert data[0]["calories"] == 500.0'
new2 = (
    '# MG-605.D: вложенная структура; запись без planned_menu_item → actual\n'
    '        assert data[0]["actual"]["calories"] == 500.0'
)
if old2 in src2:
    src2 = src2.replace(old2, new2, 1)
    p2.write_text(src2, encoding="utf-8")
    print("  ✓ test_mg_605c_permissions.py обновлён")
else:
    print("  ! test_mg_605c_permissions.py: assert уже исправлен или не найден")
PYEOF
echo

# ─────────────────────────────────────────────────────────────────────────────
# [6/7] Новые тесты MG-605.D
# ─────────────────────────────────────────────────────────────────────────────
echo "[6/7] Создаём тесты MG-605.D"

cat > "$DIARY/tests/test_mg_605d_import.py" <<'PYEOF'
"""MG-605.D — POST /api/v1/diary/import-from-menu/?menu_id=&date=

Покрывает:
- успешный импорт (создаёт DiaryEntry для каждого MenuItem)
- идемпотентность (повторный вызов — skipped, не дубли)
- isolation: импортируются только items target-члена + общие (member IS NULL)
- HEAD импортирует за члена семьи через ?member_id=
- MEMBER не может импортировать за другого (403)
- меню чужой семьи → 404
- меню не существует → 404
- нет Premium → 403
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────


def _user(email):
    return User.objects.create_user(email=email, password="pwd12345!", name=email.split("@")[0])


def _premium_family(owner, members=()):
    fam = Family.objects.create(owner=owner)
    head = FamilyMember.objects.create(family=fam, user=owner, role=FamilyMember.Role.HEAD)
    extra = []
    for u in members:
        extra.append(FamilyMember.objects.create(family=fam, user=u, role=FamilyMember.Role.MEMBER))
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=30),
    )
    return fam, head, extra


def _recipe(title="Овсянка", kcal=300):
    return Recipe.objects.create(
        title=title,
        ingredients=[],
        steps=[],
        nutrition={
            "calories": {"value": str(kcal), "unit": "ккал"},
            "proteins": {"value": "10", "unit": "г"},
            "fats": {"value": "5", "unit": "г"},
            "carbs": {"value": "50", "unit": "г"},
        },
        is_published=True,
    )


def _menu(family, start=None):
    start = start or date.today()
    return Menu.objects.create(
        family=family,
        creator_id=family.owner_id,
        period_days=1,
        start_date=start,
        end_date=start,
        status=Menu.Status.ACTIVE,
    )


def _menu_item(menu, recipe, member=None, day_offset=0, meal_type="breakfast", meal_slot="breakfast", qty=1):
    return MenuItem.objects.create(
        menu=menu,
        recipe=recipe,
        member=member,
        day_offset=day_offset,
        meal_type=meal_type,
        meal_slot=meal_slot,
        component_role="other",
        quantity=Decimal(str(qty)),
    )


@pytest.fixture
def client():
    return APIClient()


# ─── tests ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDiaryImportFromMenu:

    def test_import_creates_planned_entries(self, client):
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = _menu(fam)
        mi = _menu_item(menu, r, member=head)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            data=None,
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 200, resp.data
        assert resp.data["created"] == 1
        assert resp.data["skipped"] == 0
        assert len(resp.data["entries"]) == 1

        entry = DiaryEntry.objects.get(planned_menu_item=mi)
        assert entry.member_id == head.id
        assert entry.date == date.today()
        assert entry.meal_type == "breakfast"
        assert entry.is_eaten is False
        assert entry.recipe_id == r.id

    def test_import_idempotent(self, client):
        head_user = _user("head@example.com")
        fam, head, _ = _premium_family(head_user)
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r, member=head)

        client.force_authenticate(head_user)
        qs = f"menu_id={menu.id}&date={date.today()}"
        # 1-й вызов
        r1 = client.post(reverse("diary-import-from-menu"), QUERY_STRING=qs)
        # 2-й вызов
        r2 = client.post(reverse("diary-import-from-menu"), QUERY_STRING=qs)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.data["created"] == 1
        assert r2.data["created"] == 0
        assert r2.data["skipped"] == 1
        assert DiaryEntry.objects.count() == 1

    def test_import_only_target_members_items(self, client):
        """Импорт за HEAD — берёт MenuItem'ы HEAD + общие (member IS NULL),
        но НЕ берёт items другого члена семьи."""
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        mi_head = _menu_item(menu, r, member=head, meal_slot="breakfast", meal_type="breakfast")
        mi_common = _menu_item(menu, r, member=None, meal_slot="lunch", meal_type="lunch", day_offset=0)
        _menu_item(menu, r, member=other, meal_slot="dinner", meal_type="dinner", day_offset=0)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 200
        assert resp.data["created"] == 2  # head + common
        entries_for_head = DiaryEntry.objects.filter(member=head)
        assert entries_for_head.count() == 2
        planned_ids = set(entries_for_head.values_list("planned_menu_item_id", flat=True))
        assert planned_ids == {mi_head.id, mi_common.id}

    def test_head_imports_for_member(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        mi = _menu_item(menu, r, member=other)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}&member_id={other.id}",
        )
        assert resp.status_code == 200
        assert resp.data["created"] == 1
        entry = DiaryEntry.objects.get(planned_menu_item=mi)
        assert entry.member_id == other.id

    def test_member_cannot_import_for_other(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam, head, [other] = _premium_family(head_user, members=[other_user])
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r, member=head)

        client.force_authenticate(other_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}&member_id={head.id}",
        )
        assert resp.status_code == 403

    def test_menu_from_other_family_404(self, client):
        head_user = _user("head@example.com")
        other_user = _user("other@example.com")
        fam1, head1, _ = _premium_family(head_user)
        fam2 = Family.objects.create(owner=other_user)
        FamilyMember.objects.create(family=fam2, user=other_user, role=FamilyMember.Role.HEAD)
        r = _recipe()
        foreign_menu = _menu(fam2)
        _menu_item(foreign_menu, r)

        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={foreign_menu.id}&date={date.today()}",
        )
        assert resp.status_code == 404

    def test_menu_not_found(self, client):
        head_user = _user("head@example.com")
        _premium_family(head_user)
        client.force_authenticate(head_user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id=999999&date={date.today()}",
        )
        assert resp.status_code == 404

    def test_no_premium_403(self, client):
        user = _user("nopremium@example.com")
        fam = Family.objects.create(owner=user)
        FamilyMember.objects.create(family=fam, user=user, role=FamilyMember.Role.HEAD)
        r = _recipe()
        menu = _menu(fam)
        _menu_item(menu, r)

        client.force_authenticate(user)
        resp = client.post(
            reverse("diary-import-from-menu"),
            QUERY_STRING=f"menu_id={menu.id}&date={date.today()}",
        )
        assert resp.status_code == 403

    def test_invalid_query_params(self, client):
        head_user = _user("head@example.com")
        _premium_family(head_user)
        client.force_authenticate(head_user)
        # без menu_id
        resp = client.post(reverse("diary-import-from-menu"), QUERY_STRING=f"date={date.today()}")
        assert resp.status_code == 400
        # без date
        resp = client.post(reverse("diary-import-from-menu"), QUERY_STRING="menu_id=1")
        assert resp.status_code == 400
PYEOF
echo "  ✓ test_mg_605d_import.py"

cat > "$DIARY/tests/test_mg_605d_stats.py" <<'PYEOF'
"""MG-605.D — GET /api/v1/diary/stats/ новая вложенная структура.

Покрывает:
- структура ответа: {date, planned, actual, total}
- planned = записи с planned_menu_item IS NOT NULL
- actual = is_eaten=True ИЛИ planned_menu_item IS NULL
- запись plan+is_eaten=True → попадает И в planned, И в actual/total
- запись plan+is_eaten=False → только planned, не actual
- запись manual (planned_menu_item=None) → всегда actual, не planned
- запись manual+is_eaten=True → всегда actual
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.menu.models import Menu, MenuItem
from apps.recipes.models import Recipe
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


def _user(email):
    return User.objects.create_user(email=email, password="pwd12345!", name=email.split("@")[0])


def _premium_family(owner):
    fam = Family.objects.create(owner=owner)
    head = FamilyMember.objects.create(family=fam, user=owner, role=FamilyMember.Role.HEAD)
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium", defaults={"name": "Premium", "price": Decimal("0")},
    )
    Subscription.objects.create(
        family=fam,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        started_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=30),
    )
    return fam, head


def _recipe(kcal=300, p=10, f=5, c=50):
    return Recipe.objects.create(
        title="R",
        ingredients=[],
        steps=[],
        nutrition={
            "calories": {"value": str(kcal), "unit": "ккал"},
            "proteins": {"value": str(p), "unit": "г"},
            "fats": {"value": str(f), "unit": "г"},
            "carbs": {"value": str(c), "unit": "г"},
        },
        is_published=True,
    )


def _menu_item(family, recipe, member=None):
    menu = Menu.objects.create(
        family=family, creator_id=family.owner_id,
        period_days=1, start_date=date.today(), end_date=date.today(),
        status=Menu.Status.ACTIVE,
    )
    return MenuItem.objects.create(
        menu=menu, recipe=recipe, member=member,
        meal_type="breakfast", meal_slot="breakfast",
        day_offset=0, quantity=Decimal("1"), component_role="other",
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestDiaryStatsNewShape:

    def test_response_shape(self, client):
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=100)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="breakfast",
            recipe=r, nutrition=r.nutrition, quantity=1, is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        assert resp.status_code == 200
        d = resp.data[0]
        assert set(d.keys()) == {"date", "planned", "actual", "total"}
        for bucket in ("planned", "actual", "total"):
            assert set(d[bucket].keys()) == {"calories", "proteins", "fats", "carbs"}

    def test_manual_entry_counts_in_actual(self, client):
        """Запись без planned_menu_item — даже без is_eaten — считается actual."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=200)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="snack",
            recipe=r, nutrition=r.nutrition, quantity=1, is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["actual"]["calories"] == 200.0
        assert d["total"]["calories"] == 200.0
        assert d["planned"]["calories"] == 0.0

    def test_planned_unchecked_only_in_planned(self, client):
        """Плановая запись без галочки → только в planned, не в actual."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=300)
        mi = _menu_item(fam, r, member=head)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="breakfast",
            recipe=r, nutrition=r.nutrition, quantity=1,
            planned_menu_item=mi, is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 300.0
        assert d["actual"]["calories"] == 0.0
        assert d["total"]["calories"] == 0.0

    def test_planned_eaten_in_both(self, client):
        """Плановая запись с галочкой → и в planned, и в actual/total."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=400, p=20, f=10, c=30)
        mi = _menu_item(fam, r, member=head)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="breakfast",
            recipe=r, nutrition=r.nutrition, quantity=1,
            planned_menu_item=mi, is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 400.0
        assert d["actual"]["calories"] == 400.0
        assert d["total"]["calories"] == 400.0
        assert d["actual"]["proteins"] == 20.0

    def test_quantity_scales_nutrition(self, client):
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r = _recipe(kcal=100)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="snack",
            recipe=r, nutrition=r.nutrition, quantity=Decimal("2.5"), is_eaten=True,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["actual"]["calories"] == 250.0

    def test_mixed_day(self, client):
        """План 300 без галки + manual 100 → planned=300, actual=100, total=100."""
        user = _user("u@x.com")
        fam, head = _premium_family(user)
        r_plan = _recipe(kcal=300)
        r_manual = _recipe(kcal=100)
        mi = _menu_item(fam, r_plan, member=head)
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="breakfast",
            recipe=r_plan, nutrition=r_plan.nutrition, quantity=1,
            planned_menu_item=mi, is_eaten=False,
        )
        DiaryEntry.objects.create(
            member=head, date=date.today(), meal_type="snack",
            recipe=r_manual, nutrition=r_manual.nutrition, quantity=1,
            is_eaten=False,
        )
        client.force_authenticate(user)
        resp = client.get(reverse("diary-stats"), {"from": str(date.today()), "to": str(date.today())})
        d = resp.data[0]
        assert d["planned"]["calories"] == 300.0
        assert d["actual"]["calories"] == 100.0
        assert d["total"]["calories"] == 100.0
PYEOF
echo "  ✓ test_mg_605d_stats.py"
echo

# ─────────────────────────────────────────────────────────────────────────────
# [7/7] Прогон тестов apps/diary
# ─────────────────────────────────────────────────────────────────────────────
echo "[7/7] Прогон тестов apps/diary -v"
$COMPOSE exec -T backend pytest apps/diary/ -v --tb=short 2>&1 | tail -80
echo
echo "================================================================"
echo "  MG-605.D APPLY DONE"
echo "================================================================"
echo "Backup: $BAK"
