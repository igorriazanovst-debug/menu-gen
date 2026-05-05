#!/bin/bash
# /opt/menugen/backend/scripts/mg_205ui_apply_backend.sh
# MG-205-UI этап A: backend (history + reset endpoints + meta в сериализаторах).
# Идемпотентен: маркеры MG_205UI_V_*.
set -euo pipefail

ROOT=/opt/menugen
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups
mkdir -p "$BAK"

USERS_VIEWS=$ROOT/backend/apps/users/views.py
USERS_SER=$ROOT/backend/apps/users/serializers.py
USERS_URLS=$ROOT/backend/apps/users/urls/users.py
FAMILY_VIEWS=$ROOT/backend/apps/family/views.py
FAMILY_SER=$ROOT/backend/apps/family/serializers.py
FAMILY_URLS=$ROOT/backend/apps/family/urls.py

# ─────── 1) Бэкап БД ───────
echo "[1/7] DB backup..."
docker compose -f $ROOT/docker-compose.yml exec -T db \
  pg_dump -U postgres menugen 2>/dev/null | gzip > "$BAK/db_mg205ui_${TS}.sql.gz" || true
ls -la "$BAK/db_mg205ui_${TS}.sql.gz" 2>/dev/null || echo "  (db backup skipped — db cli not available; ok for dev)"

# ─────── 2) Бэкап файлов ───────
echo "[2/7] File backups..."
cp "$USERS_VIEWS"   "$BAK/users_views.py.bak_mg205ui_${TS}"
cp "$USERS_SER"     "$BAK/users_serializers.py.bak_mg205ui_${TS}"
cp "$USERS_URLS"    "$BAK/users_urls_users.py.bak_mg205ui_${TS}"
cp "$FAMILY_VIEWS"  "$BAK/family_views.py.bak_mg205ui_${TS}"
cp "$FAMILY_SER"    "$BAK/family_serializers.py.bak_mg205ui_${TS}"
cp "$FAMILY_URLS"   "$BAK/family_urls.py.bak_mg205ui_${TS}"

# ─────── 3) Patch users/serializers.py ───────
echo "[3/7] Patch users/serializers.py..."
python3 <<PYEOF
import re
from pathlib import Path

p = Path("$USERS_SER")
src = p.read_text()

if "MG_205UI_V_serializers" in src:
    print("  already patched, skipping")
else:
    # 3a) Импорты для аудита
    inject_top = '''
# MG_205UI_V_serializers = 1
TARGET_FIELDS_MG205UI = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class ProfileTargetAuditSerializer(serializers.Serializer):
    """Запись истории правок одного поля КБЖУ."""
    id = serializers.IntegerField(read_only=True)
    field = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    old_value = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    new_value = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    reason = serializers.CharField(read_only=True, allow_blank=True)
    at = serializers.DateTimeField(read_only=True)
    by_user = serializers.SerializerMethodField()

    def get_by_user(self, obj):
        if obj.by_user_id is None:
            return None
        return {"id": obj.by_user.id, "name": obj.by_user.name}


'''
    # Вставляем перед классом ProfileSerializer
    pattern_class = re.compile(r"class ProfileSerializer\(serializers\.ModelSerializer\):")
    if not pattern_class.search(src):
        raise SystemExit("ERROR: ProfileSerializer not found in users/serializers.py")
    src = pattern_class.sub(inject_top + "class ProfileSerializer(serializers.ModelSerializer):", src, count=1)

    # 3b) targets_meta = SerializerMethodField() рядом с targets_calculated
    src = re.sub(
        r"(targets_calculated\s*=\s*serializers\.SerializerMethodField\(\))",
        r"\1\n    targets_meta = serializers.SerializerMethodField()",
        src,
        count=1,
    )

    # 3c) В Meta.fields после "targets_calculated", добавить "targets_meta",
    src = re.sub(
        r'("targets_calculated",)',
        r'\1\n            "targets_meta",',
        src,
        count=1,
    )

    # 3d) Метод get_targets_meta — вставляем сразу после метода get_targets_calculated
    method_meta = '''
    def get_targets_meta(self, obj):
        """MG-205-UI: для каждого target-поля — последняя запись аудита."""
        from .models import ProfileTargetAudit
        if not getattr(obj, "pk", None):
            return {}
        out = {}
        for f in TARGET_FIELDS_MG205UI:
            last = (
                ProfileTargetAudit.objects.filter(profile=obj, field=f)
                .order_by("-at")
                .first()
            )
            if last is None:
                out[f] = {"source": "auto", "by_user": None, "at": None}
            else:
                out[f] = {
                    "source": last.source,
                    "by_user": (
                        {"id": last.by_user.id, "name": last.by_user.name}
                        if last.by_user_id else None
                    ),
                    "at": last.at.isoformat() if last.at else None,
                }
        return out

'''
    # Якорь — конец метода get_targets_calculated (по закрывающей dict + return)
    pattern_method = re.compile(
        r"(def get_targets_calculated\(self, obj\):.*?\n        \}\s*\n)",
        re.DOTALL,
    )
    m = pattern_method.search(src)
    if not m:
        raise SystemExit("ERROR: cannot anchor after get_targets_calculated")
    src = src[: m.end()] + method_meta + src[m.end() :]

    p.write_text(src)
    print("  patched ✓")
PYEOF

# ─────── 4) Patch family/serializers.py ───────
echo "[4/7] Patch family/serializers.py..."
python3 <<PYEOF
import re
from pathlib import Path

p = Path("$FAMILY_SER")
src = p.read_text()

if "MG_205UI_V_family_ser" in src:
    print("  already patched, skipping")
else:
    inject = '''    # MG_205UI_V_family_ser = 1
    targets_meta = serializers.SerializerMethodField()

    def get_targets_meta(self, obj):
        from apps.users.models import ProfileTargetAudit
        from apps.users.serializers import TARGET_FIELDS_MG205UI
        if not obj or not getattr(obj, "pk", None):
            return {}
        out = {}
        for f in TARGET_FIELDS_MG205UI:
            last = (
                ProfileTargetAudit.objects.filter(profile=obj, field=f)
                .order_by("-at")
                .first()
            )
            if last is None:
                out[f] = {"source": "auto", "by_user": None, "at": None}
            else:
                out[f] = {
                    "source": last.source,
                    "by_user": (
                        {"id": last.by_user.id, "name": last.by_user.name}
                        if last.by_user_id else None
                    ),
                    "at": last.at.isoformat() if last.at else None,
                }
        return out

'''
    # Точка вставки: после строки meal_plan_type = ... в read-only ProfileSerializer
    pattern = re.compile(
        r"(meal_plan_type\s*=\s*serializers\.CharField\(read_only=True\)\s*\n)"
    )
    if not pattern.search(src):
        raise SystemExit("ERROR: anchor 'meal_plan_type = CharField(read_only=True)' not found in family/serializers.py")
    src = pattern.sub(r"\1\n" + inject, src, count=1)
    p.write_text(src)
    print("  patched ✓")
PYEOF

# ─────── 5) Patch users/views.py + urls/users.py ───────
echo "[5/7] Patch users/views.py + urls..."
python3 <<PYEOF
import re
from pathlib import Path

vp = Path("$USERS_VIEWS")
src = vp.read_text()
if "MG_205UI_V_views" not in src:
    add = '''


# ─────────────────────────────────────────────────────────────────────────────
# MG_205UI_V_views = 1
# История правок целевых КБЖУ + сброс одного поля к авторасчёту.
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


class TargetHistoryView(APIView):
    """GET /users/me/targets/{field}/history/ — история правок одного поля."""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, field: str):
        _validate_target_field(field)
        from apps.users.models import ProfileTargetAudit
        from apps.users.serializers import ProfileTargetAuditSerializer

        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response([], status=status.HTTP_200_OK)

        qs = (
            ProfileTargetAudit.objects.filter(profile=profile, field=field)
            .select_related("by_user")
            .order_by("-at")[:100]
        )
        return Response(ProfileTargetAuditSerializer(qs, many=True).data)


class TargetResetView(APIView):
    """POST /users/me/targets/{field}/reset/ — пересчитать одно поле и снять lock."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, field: str):
        _validate_target_field(field)
        from apps.users.audit import record_target_change
        from apps.users.nutrition import calculate_targets

        profile = getattr(request.user, "profile", None)
        if profile is None:
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

        # запись аудита: source='auto', by_user=request.user (инициатор reset)
        record_target_change(
            profile=profile,
            field=field,
            new_value=new_value,
            source="auto",
            by_user=request.user,
            old_value=old_value,
            reason=f"reset to auto by user {request.user.id}",
        )

        # Возвращаем обновлённого юзера (как и UserMeView)
        return Response(UserMeSerializer(request.user).data)
'''
    src = src + add
    vp.write_text(src)
    print("  views.py patched ✓")
else:
    print("  views.py already patched")

# urls
up = Path("$USERS_URLS")
usrc = up.read_text()
if "MG_205UI_V_urls" not in usrc:
    if "from apps.users.views import UserMeView" not in usrc:
        usrc = "from apps.users.views import UserMeView, TargetHistoryView, TargetResetView\n" + usrc
    else:
        usrc = usrc.replace(
            "from apps.users.views import UserMeView",
            "from apps.users.views import UserMeView, TargetHistoryView, TargetResetView",
            1,
        )

    # Расширяем urlpatterns
    inject = '''
    # MG_205UI_V_urls = 1
    path("me/targets/<str:field>/history/", TargetHistoryView.as_view(), name="users-me-target-history"),
    path("me/targets/<str:field>/reset/",   TargetResetView.as_view(),   name="users-me-target-reset"),
'''
    if "urlpatterns = [" not in usrc:
        raise SystemExit("ERROR: cannot find urlpatterns in users/urls/users.py")
    usrc = re.sub(
        r"(urlpatterns\s*=\s*\[\s*\n)",
        r"\1" + inject,
        usrc,
        count=1,
    )
    up.write_text(usrc)
    print("  urls/users.py patched ✓")
else:
    print("  urls/users.py already patched")
PYEOF

# ─────── 6) Patch family/views.py + urls.py ───────
echo "[6/7] Patch family/views.py + urls.py..."
python3 <<PYEOF
import re
from pathlib import Path

vp = Path("$FAMILY_VIEWS")
src = vp.read_text()
if "MG_205UI_V_family_views" not in src:
    add = '''


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
    is_self = FamilyMember.objects.filter(
        family=family, user=request.user, id=member_id
    ).exists()

    is_specialist = False
    try:
        from apps.specialists.permissions import _get_specialist
        from apps.specialists.models import SpecialistAssignment
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
        member = FamilyMember.objects.select_related("user__profile").get(
            id=member_id, family=family
        )
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
'''
    src = src + add
    vp.write_text(src)
    print("  family/views.py patched ✓")
else:
    print("  family/views.py already patched")

# urls
up = Path("$FAMILY_URLS")
usrc = up.read_text()
if "MG_205UI_V_family_urls" not in usrc:
    # Импорты
    usrc = re.sub(
        r"from \.views import ([^\n]+)",
        lambda m: "from .views import " + m.group(1).rstrip()
                  + ", FamilyMemberTargetHistoryView, FamilyMemberTargetResetView",
        usrc,
        count=1,
    )
    inject = '''    # MG_205UI_V_family_urls = 1
    path("members/<int:member_id>/targets/<str:field>/history/",
         FamilyMemberTargetHistoryView.as_view(),
         name="family-member-target-history"),
    path("members/<int:member_id>/targets/<str:field>/reset/",
         FamilyMemberTargetResetView.as_view(),
         name="family-member-target-reset"),
'''
    # Перед закрывающей скобкой urlpatterns
    usrc = re.sub(
        r"(\n\]\s*\n*\Z)",
        r"\n" + inject + r"\1",
        usrc,
        count=1,
    )
    up.write_text(usrc)
    print("  family/urls.py patched ✓")
else:
    print("  family/urls.py already patched")
PYEOF

# ─────── 7) Verify ───────
echo "[7/7] Verify..."
echo ""
echo "── markers ──"
grep -nE "MG_205UI_V_" $USERS_SER $USERS_VIEWS $USERS_URLS $FAMILY_SER $FAMILY_VIEWS $FAMILY_URLS

echo ""
echo "── Django syntax check ──"
docker compose -f $ROOT/docker-compose.yml exec -T backend python -c "
import django; django.setup()
" 2>&1 | head -5 || true

docker compose -f $ROOT/docker-compose.yml exec -T backend python manage.py check 2>&1 | tail -10

echo ""
echo "── Routes ──"
docker compose -f $ROOT/docker-compose.yml exec -T backend python manage.py show_urls 2>/dev/null \
  | grep -E "targets/|users/me|family/members" \
  | sort -u || \
  docker compose -f $ROOT/docker-compose.yml exec -T backend python -c "
from django.urls import get_resolver
def walk(r, prefix=''):
    for p in r.url_patterns:
        if hasattr(p, 'url_patterns'):
            walk(p, prefix + str(p.pattern))
        else:
            full = prefix + str(p.pattern)
            if 'target' in full or 'users/me' in full:
                print(full)
import django; django.setup(); walk(get_resolver())
" 2>&1 | head -20

echo ""
echo "=== DONE @ $TS ==="
echo "Backups:"
ls -la $BAK/*_mg205ui_${TS}* 2>/dev/null
echo ""
echo "ROLLBACK:"
echo "  cp $BAK/users_serializers.py.bak_mg205ui_${TS}    $USERS_SER"
echo "  cp $BAK/users_views.py.bak_mg205ui_${TS}          $USERS_VIEWS"
echo "  cp $BAK/users_urls_users.py.bak_mg205ui_${TS}     $USERS_URLS"
echo "  cp $BAK/family_serializers.py.bak_mg205ui_${TS}   $FAMILY_SER"
echo "  cp $BAK/family_views.py.bak_mg205ui_${TS}         $FAMILY_VIEWS"
echo "  cp $BAK/family_urls.py.bak_mg205ui_${TS}          $FAMILY_URLS"
