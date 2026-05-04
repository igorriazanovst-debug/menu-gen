#!/usr/bin/env bash
# MG-205 apply STEP 3/4: serializers + permissions + family view
# Идемпотентен: маркер MG_205_V в каждом файле.
# Запуск: bash /opt/menugen/backend/scripts/mg_205_apply_3_api.sh

set -eu
PROJECT_ROOT="/opt/menugen"
BACKEND="${PROJECT_ROOT}/backend"
COMPOSE="docker compose -f ${PROJECT_ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
TASK="mg205"
BACKUPS="${PROJECT_ROOT}/backups"
mkdir -p "${BACKUPS}"

USR_SER="${BACKEND}/apps/users/serializers.py"
FAM_SER="${BACKEND}/apps/family/serializers.py"
FAM_VWS="${BACKEND}/apps/family/views.py"
SPC_PRM="${BACKEND}/apps/specialists/permissions.py"
SPC_VWS="${BACKEND}/apps/specialists/views.py"

echo "=== MG-205 apply STEP 3 ==="
echo "TS=${TS}"

echo "[0] backups..."
cp "${USR_SER}"  "${BACKUPS}/users_serializers.py.bak_${TASK}_step3_${TS}"
cp "${FAM_SER}"  "${BACKUPS}/family_serializers.py.bak_${TASK}_step3_${TS}"
cp "${FAM_VWS}"  "${BACKUPS}/family_views.py.bak_${TASK}_step3_${TS}"
cp "${SPC_VWS}"  "${BACKUPS}/specialists_views.py.bak_${TASK}_step3_${TS}"
echo "    OK"

# ============================================================
# 1. apps/specialists/permissions.py (новый)
# ============================================================
echo "[1] создаю apps/specialists/permissions.py..."
if [ -f "${SPC_PRM}" ]; then
  echo "    SKIP: уже существует, бэкапю и переписываю"
  cp "${SPC_PRM}" "${BACKUPS}/specialists_permissions.py.bak_${TASK}_step3_${TS}"
fi

cat > "${SPC_PRM}" <<'PYEOF'
"""
MG-205: пермишены для специалистов.

IsVerifiedSpecialist — текущий user является verified Specialist'ом.
SpecialistCanEditClientProfile — текущий user является verified Specialist'ом
    с активным SpecialistAssignment на семью target user.

is_verified_specialist_for_user(actor, target_user) — хелпер для
определения source='specialist' в serializers.
"""
from __future__ import annotations

from rest_framework import permissions

MG_205_V = 1


def _get_specialist(user):
    """Возвращает Specialist instance или None."""
    if not user or not user.is_authenticated:
        return None
    # related_name='specialist_profile' (см. apps/specialists/models.py)
    try:
        return user.specialist_profile
    except Exception:
        return None


def is_verified_specialist_for_user(actor, target_user) -> bool:
    """True, если actor — verified Specialist с активным assignment
    на любую из семей, в которой состоит target_user."""
    if not actor or not target_user:
        return False
    if actor.id == target_user.id:
        return False  # сам себе не специалист
    spec = _get_specialist(actor)
    if not spec or not spec.is_verified:
        return False

    # local imports чтобы избежать циклов
    from apps.family.models import FamilyMember
    from apps.specialists.models import SpecialistAssignment

    target_family_ids = list(
        FamilyMember.objects.filter(user=target_user).values_list("family_id", flat=True)
    )
    if not target_family_ids:
        return False

    return SpecialistAssignment.objects.filter(
        specialist=spec,
        family_id__in=target_family_ids,
        status=SpecialistAssignment.Status.ACTIVE,
    ).exists()


class IsVerifiedSpecialist(permissions.BasePermission):
    """Текущий user — verified Specialist."""

    def has_permission(self, request, view):
        spec = _get_specialist(request.user)
        return spec is not None and spec.is_verified


class SpecialistCanEditClientProfile(permissions.BasePermission):
    """Specialist может править профиль клиента из назначенной семьи.

    Ожидает, что view предоставит target_user через get_target_user(),
    или target_member через get_target_member().
    """

    def has_permission(self, request, view):
        spec = _get_specialist(request.user)
        if not spec or not spec.is_verified:
            return False
        target_user = None
        if hasattr(view, "get_target_user"):
            target_user = view.get_target_user()
        elif hasattr(view, "get_target_member"):
            m = view.get_target_member()
            target_user = getattr(m, "user", None) if m else None
        if target_user is None:
            return False
        return is_verified_specialist_for_user(request.user, target_user)
PYEOF
echo "    OK"

# ============================================================
# 2. apps/specialists/views.py — заменить локальный класс IsVerifiedSpecialist
#    на re-import из permissions.py (обратная совместимость)
# ============================================================
echo "[2] specialists/views.py: re-import IsVerifiedSpecialist..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/specialists/views.py"
src = open(path, encoding="utf-8").read()

if "MG_205_V" in src:
    print("    SKIP: уже патчено")
    sys.exit(0)

old = '''class IsVerifiedSpecialist(permissions.BasePermission):
    def has_permission(self, request, view):
        specialist = _get_specialist(request.user)
        return specialist is not None and specialist.is_verified'''
new = '''# MG_205_V = 1: класс перемещён в apps/specialists/permissions.py
from .permissions import IsVerifiedSpecialist  # noqa: F401  re-export для обратной совместимости'''

if old not in src:
    print("    ERROR: ожидаемый блок IsVerifiedSpecialist не найден")
    sys.exit(1)
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("    OK")
PYEOF

# ============================================================
# 3. apps/users/serializers.py — UserMeUpdateSerializer.update() пишет аудит
# ============================================================
echo "[3] users/serializers.py: аудит при PATCH..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/users/serializers.py"
src = open(path, encoding="utf-8").read()

if "MG_205_V_serializers" in src:
    print("    SKIP: уже патчено")
    sys.exit(0)

old = '''class UserMeUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("name", "avatar_url", "allergies", "disliked_products", "profile")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance'''

new = '''# MG_205_V_serializers = 1
TARGET_FIELDS_MG205 = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class UserMeUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("name", "avatar_url", "allergies", "disliked_products", "profile")

    def update(self, instance, validated_data):
        from .audit import record_target_change

        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None

        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            # Сохраним old-значения для аудита ДО изменения
            old_values = {f: getattr(profile, f, None) for f in TARGET_FIELDS_MG205}

            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

            # MG-205: для каждого пришедшего target-поля пишем аудит source='user'
            # (UserMeUpdateSerializer — это всегда сам пользователь правит свой профиль)
            for f in TARGET_FIELDS_MG205:
                if f in profile_data:
                    new_val = profile_data[f]
                    record_target_change(
                        profile=profile,
                        field=f,
                        new_value=new_val,
                        source="user",
                        by_user=actor,
                        old_value=old_values[f],
                        reason="user PATCH /users/me",
                    )
        return instance'''

if old not in src:
    print("    ERROR: ожидаемый блок UserMeUpdateSerializer не найден")
    sys.exit(1)
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("    OK")
PYEOF

# ============================================================
# 4. apps/family/serializers.py — FamilyMemberUpdateSerializer.update() пишет аудит
#    с определением source (user/specialist)
# ============================================================
echo "[4] family/serializers.py: аудит при PATCH с определением source..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/family/serializers.py"
src = open(path, encoding="utf-8").read()

if "MG_205_V_family_ser" in src:
    print("    SKIP: уже патчено")
    sys.exit(0)

old = '''class FamilyMemberUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=255)
    allergies = serializers.ListField(child=serializers.CharField(), required=False)
    disliked_products = serializers.ListField(child=serializers.CharField(), required=False)
    profile = ProfileUpdateSerializer(required=False)

    def update(self, instance, validated_data):
        user = instance.user
        profile_data = validated_data.pop("profile", None)

        for attr in ("name", "allergies", "disliked_products"):
            if attr in validated_data:
                setattr(user, attr, validated_data[attr])
        user.save()

        if profile_data:
            profile = user.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance'''

new = '''# MG_205_V_family_ser = 1
TARGET_FIELDS_MG205 = (
    "calorie_target",
    "protein_target_g",
    "fat_target_g",
    "carb_target_g",
    "fiber_target_g",
)


class FamilyMemberUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=255)
    allergies = serializers.ListField(child=serializers.CharField(), required=False)
    disliked_products = serializers.ListField(child=serializers.CharField(), required=False)
    profile = ProfileUpdateSerializer(required=False)

    def update(self, instance, validated_data):
        from apps.users.audit import record_target_change
        from apps.specialists.permissions import is_verified_specialist_for_user

        user = instance.user
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None

        # MG-205: определяем источник правки
        if actor and actor.id == user.id:
            source = "user"
        elif actor and is_verified_specialist_for_user(actor, user):
            source = "specialist"
        else:
            # Глава семьи правит члена семьи → считаем source='user'
            # (правки головы семьи приравниваются к ручным правкам пользователя)
            source = "user"

        profile_data = validated_data.pop("profile", None)

        for attr in ("name", "allergies", "disliked_products"):
            if attr in validated_data:
                setattr(user, attr, validated_data[attr])
        user.save()

        if profile_data:
            profile = user.profile
            old_values = {f: getattr(profile, f, None) for f in TARGET_FIELDS_MG205}

            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

            for f in TARGET_FIELDS_MG205:
                if f in profile_data:
                    record_target_change(
                        profile=profile,
                        field=f,
                        new_value=profile_data[f],
                        source=source,
                        by_user=actor,
                        old_value=old_values[f],
                        reason=f"family PATCH (source={source})",
                    )

        return instance'''

if old not in src:
    print("    ERROR: ожидаемый блок FamilyMemberUpdateSerializer не найден")
    sys.exit(1)
src = src.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(src)
print("    OK")
PYEOF

# ============================================================
# 5. apps/family/views.py — FamilyMemberUpdateView допускает специалиста
# ============================================================
echo "[5] family/views.py: пропуск verified specialist в FamilyMemberUpdateView..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/family/views.py"
src = open(path, encoding="utf-8").read()

if "MG_205_V_family_view" in src:
    print("    SKIP: уже патчено")
    sys.exit(0)

old = '''        is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
        is_self = FamilyMember.objects.filter(
            family=family, user=request.user, id=member_id
        ).exists()

        if not is_head and not is_self:
            return Response(status=status.HTTP_403_FORBIDDEN)'''

new = '''        # MG_205_V_family_view = 1: добавлен путь для verified specialist'а
        is_head = family.owner_id == request.user.id or request.user.user_type == "admin"
        is_self = FamilyMember.objects.filter(
            family=family, user=request.user, id=member_id
        ).exists()

        # Specialist допускается, если у него есть активный assignment на эту семью
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
            return Response(status=status.HTTP_403_FORBIDDEN)'''

if old not in src:
    print("    ERROR: ожидаемый блок проверки прав не найден")
    sys.exit(1)
src = src.replace(old, new, 1)

# Также: serializer передаёт context — нужно проверить, что передаём context=request
old2 = '''serializer = FamilyMemberUpdateSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()'''
new2 = '''serializer = FamilyMemberUpdateSerializer(
            member, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()'''
if old2 not in src:
    print("    WARN: блок вызова serializer.save() не найден точно — context не пробрасываем (возможно уже есть)")
else:
    src = src.replace(old2, new2, 1)
    print("    OK: context={'request': request} проброшен в serializer")

open(path, "w", encoding="utf-8").write(src)
print("    OK")
PYEOF

# ============================================================
# 6. Sanity
# ============================================================
echo "[6] sanity..."
${COMPOSE} exec -T backend python manage.py check
${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from apps.specialists.permissions import (
    IsVerifiedSpecialist, SpecialistCanEditClientProfile,
    is_verified_specialist_for_user, MG_205_V,
)
print("  permissions.py OK, MG_205_V=", MG_205_V)
from apps.users.serializers import UserMeUpdateSerializer, TARGET_FIELDS_MG205
print("  users/serializers.py OK, fields=", TARGET_FIELDS_MG205)
from apps.family.serializers import FamilyMemberUpdateSerializer
print("  family/serializers.py OK")
PYEOF

# ============================================================
# 7. Smoke test через ORM: PATCH-эмуляция
# ============================================================
echo "[7] smoke: эмулируем user-PATCH через UserMeUpdateSerializer..."
${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from rest_framework.test import APIRequestFactory
from apps.users.models import Profile, ProfileTargetAudit
from apps.users.serializers import UserMeUpdateSerializer
from apps.users.audit import get_field_source, is_locked

p = Profile.objects.get(id=1)
u = p.user
print(f"[before] protein={p.protein_target_g} source={get_field_source(p, 'protein_target_g')}")

# Эмуляция PATCH /users/me с profile.protein_target_g=125
factory = APIRequestFactory()
req = factory.patch("/api/v1/users/me", {})
req.user = u

ser = UserMeUpdateSerializer(
    instance=u,
    data={"profile": {"protein_target_g": "125.0"}},
    partial=True,
    context={"request": req},
)
ser.is_valid(raise_exception=True)
ser.save()

p.refresh_from_db()
print(f"[after PATCH protein=125] protein={p.protein_target_g} source={get_field_source(p, 'protein_target_g')} locked={is_locked(p, 'protein_target_g')}")

# Откат тестовой правки: force=True вернёт 112.5 и снимет lock
from apps.users.nutrition import fill_profile_targets
fill_profile_targets(p, force=True, actor=u)
p.save()
p.refresh_from_db()
print(f"[after rollback force=True] protein={p.protein_target_g} source={get_field_source(p, 'protein_target_g')}")

# Покажем последние записи аудита
print("[audit history protein_target_g]")
for pta in ProfileTargetAudit.objects.filter(profile=p, field="protein_target_g").order_by("-at")[:5]:
    print(f"   {pta.at:%H:%M:%S} src={pta.source} new={pta.new_value} reason='{pta.reason[:50]}'")
PYEOF

echo
echo "=== STEP 3 done ==="
echo
echo "Откат шага 3:"
echo "  cp ${BACKUPS}/users_serializers.py.bak_${TASK}_step3_${TS}    ${USR_SER}"
echo "  cp ${BACKUPS}/family_serializers.py.bak_${TASK}_step3_${TS}   ${FAM_SER}"
echo "  cp ${BACKUPS}/family_views.py.bak_${TASK}_step3_${TS}         ${FAM_VWS}"
echo "  cp ${BACKUPS}/specialists_views.py.bak_${TASK}_step3_${TS}    ${SPC_VWS}"
echo "  rm -f ${SPC_PRM}"
echo "  ${COMPOSE} restart backend"
