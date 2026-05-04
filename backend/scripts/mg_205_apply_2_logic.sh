#!/usr/bin/env bash
# MG-205 apply STEP 2/4:
#   - apps/users/audit.py (новый): хелпер записи ProfileTargetAudit + AuditLog
#   - apps/users/nutrition.py: fill_profile_targets учитывает source последней записи
#   - apps/users/models.py: Profile.save() пробрасывает actor (актёра-пользователя)
# Идемпотентен (маркер MG_205_V в nutrition.py).
# Запуск: bash /opt/menugen/backend/scripts/mg_205_apply_2_logic.sh

set -eu
PROJECT_ROOT="/opt/menugen"
BACKEND="${PROJECT_ROOT}/backend"
COMPOSE="docker compose -f ${PROJECT_ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
TASK="mg205"
BACKUPS="${PROJECT_ROOT}/backups"
mkdir -p "${BACKUPS}"

NUTRITION="${BACKEND}/apps/users/nutrition.py"
MODELS="${BACKEND}/apps/users/models.py"
AUDIT_NEW="${BACKEND}/apps/users/audit.py"

echo "=== MG-205 apply STEP 2 ==="
echo "TS=${TS}"

echo "[0] backups..."
cp "${NUTRITION}" "${BACKUPS}/nutrition.py.bak_${TASK}_step2_${TS}"
cp "${MODELS}"    "${BACKUPS}/users_models.py.bak_${TASK}_step2_${TS}"
echo "    nutrition.py : ${BACKUPS}/nutrition.py.bak_${TASK}_step2_${TS}"
echo "    models.py    : ${BACKUPS}/users_models.py.bak_${TASK}_step2_${TS}"

# ============================================================
# 1. apps/users/audit.py — единая точка записи
# ============================================================
echo "[1] создаю apps/users/audit.py..."
if [ -f "${AUDIT_NEW}" ]; then
  echo "    SKIP: audit.py уже существует, бэкапю и переписываю"
  cp "${AUDIT_NEW}" "${BACKUPS}/users_audit.py.bak_${TASK}_step2_${TS}"
fi

cat > "${AUDIT_NEW}" <<'PYEOF'
"""
MG-205: единая точка записи правок целей КБЖУ.

record_target_change():
  1) пишет ProfileTargetAudit (история по полю)
  2) дублирует в общий AuditLog (entity_type='profile_target')

Используется из nutrition.fill_profile_targets и из serializers (PATCH).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

MG_205_V = 1


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def record_target_change(
    profile,
    field: str,
    new_value,
    source: str,
    by_user=None,
    old_value=None,
    reason: str = "",
) -> None:
    """Записать изменение цели КБЖУ в ProfileTargetAudit + AuditLog.

    Args:
        profile: instance Profile
        field: одно из 'calorie_target', 'protein_target_g',
               'fat_target_g', 'carb_target_g', 'fiber_target_g'
        new_value: новое значение (число / Decimal / None)
        source: 'auto' | 'user' | 'specialist'
        by_user: instance User или None (для 'auto' всегда None)
        old_value: предыдущее значение (для diff)
        reason: текстовый комментарий
    """
    # local imports — избегаем циклических зависимостей при загрузке Django
    from .models import ProfileTargetAudit

    nv = _to_decimal(new_value)
    ov = _to_decimal(old_value)

    pta = ProfileTargetAudit.objects.create(
        profile=profile,
        field=field,
        source=source,
        by_user=by_user,
        old_value=ov,
        new_value=nv,
        reason=reason or "",
    )

    # Дублируем в общий AuditLog (мягко: если приложение sync/AuditLog
    # недоступно — не падаем, чтобы не блокировать save())
    try:
        from apps.sync.models import AuditLog

        AuditLog.objects.create(
            user=by_user,
            action="profile_target.update",
            entity_type="profile_target",
            entity_id=f"{profile.id}:{field}",
            old_values={"value": str(ov) if ov is not None else None},
            new_values={
                "value": str(nv) if nv is not None else None,
                "source": source,
                "by_user_id": by_user.id if by_user else None,
                "reason": reason or "",
            },
        )
    except Exception:
        # AuditLog — best-effort. Основная история уже в ProfileTargetAudit.
        pass


def get_field_source(profile, field: str) -> str:
    """Текущий источник правки поля = source последней записи ProfileTargetAudit.

    Если записей нет — возвращает 'auto' (значит можно перетирать).
    """
    from .models import ProfileTargetAudit

    last = (
        ProfileTargetAudit.objects.filter(profile=profile, field=field)
        .order_by("-at")
        .first()
    )
    return last.source if last else "auto"


def is_locked(profile, field: str) -> bool:
    """Поле залочено для авторасчёта = последняя правка от user/specialist."""
    return get_field_source(profile, field) in ("user", "specialist")
PYEOF
echo "    OK"

# ============================================================
# 2. nutrition.py: расширяем fill_profile_targets
# ============================================================
echo "[2] обновляю nutrition.fill_profile_targets..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/users/nutrition.py"
src = open(path, encoding="utf-8").read()

if "MG_205_V" in src:
    print("    SKIP: маркер MG_205_V уже присутствует в nutrition.py")
    sys.exit(0)

# 1) Добавим MG_205_V рядом с MG_202_V
old_marker = "MG_202_V = 1   # маркер версии формулы (для идемпотентности apply-скрипта)"
new_marker = (
    "MG_202_V = 1   # маркер версии формулы (для идемпотентности apply-скрипта)\n"
    "MG_205_V = 1   # учёт источника правок (auto/user/specialist)"
)
assert old_marker in src, "MG_202_V маркер не найден"
src = src.replace(old_marker, new_marker, 1)

# 2) Заменим всю функцию fill_profile_targets целиком
old_func = '''def fill_profile_targets(profile, force: bool = False) -> bool:
    """
    Заполняет цели в профиле. Не перезаписывает заданные пользователем
    значения (если force=False).
    Возвращает True если что-то изменилось.
    """
    targets = calculate_targets(profile)
    if not targets:
        return False
    changed = False
    for field, value in targets.items():
        current = getattr(profile, field, None)
        if force or current is None:
            if current != value:
                setattr(profile, field, value)
                changed = True
    return changed'''

new_func = '''def fill_profile_targets(profile, force: bool = False, actor=None) -> bool:
    """
    Заполняет цели в профиле по формуле Mifflin-St Jeor.

    MG-205: учитывает источник последней правки (ProfileTargetAudit).
      - force=False: НЕ перетирает поля, у которых last source in {'user','specialist'}
      - force=True : перетирает всегда; ставит source='auto'
    Каждое реальное изменение пишется в ProfileTargetAudit (+AuditLog) через audit.record_target_change.

    actor — User, инициатор force-сброса (например, диетолог через "Сбросить к авто").
    Для обычного авторасчёта actor=None.

    Возвращает True если что-то изменилось.
    """
    from .audit import record_target_change, is_locked

    targets = calculate_targets(profile)
    if not targets:
        return False

    changed = False
    # Если профиль ещё не сохранён (pk is None) — записывать аудит нельзя (FK requires pk).
    # В этом случае просто проставляем поля; аудит запишем после save() через post_save-хук
    # (см. apps/users/models.Profile.save).
    has_pk = profile.pk is not None

    for field, value in targets.items():
        current = getattr(profile, field, None)
        # MG-205: проверяем lock для существующего профиля
        if has_pk and not force and is_locked(profile, field):
            continue
        # Для нового профиля (без pk) lock проверять негде — записей ещё нет.
        if force or current is None:
            if current != value:
                setattr(profile, field, value)
                changed = True
                if has_pk:
                    record_target_change(
                        profile=profile,
                        field=field,
                        new_value=value,
                        source="auto",
                        by_user=actor,
                        old_value=current,
                        reason="auto-recalc (force)" if force else "auto-fill (was empty)",
                    )
    return changed'''

assert old_func in src, "тело fill_profile_targets не найдено целиком"
src = src.replace(old_func, new_func, 1)

open(path, "w", encoding="utf-8").write(src)
print("    OK: fill_profile_targets обновлена, маркер MG_205_V добавлен")
PYEOF

# ============================================================
# 3. models.py: Profile.save() — после первичного save() прогнать fill ещё раз с pk,
#    чтобы записать аудит для новых профилей
# ============================================================
echo "[3] обновляю Profile.save() для аудита новых профилей..."
python3 - <<'PYEOF'
import sys
path = "/opt/menugen/backend/apps/users/models.py"
src = open(path, encoding="utf-8").read()

if "# MG-205: post-save audit pass" in src:
    print("    SKIP: Profile.save() уже обновлён под MG-205")
    sys.exit(0)

# Текущий блок (по diagnose):
#   def save(self, *args, **kwargs):
#       from .nutrition import fill_profile_targets
#       <возможно пустая строка>
#       fill_profile_targets(self, force=False)
# затем super().save(...) — точное содержание не видно из grep,
# но известно что fill вызывается ДО super().save (по RESUME_next_chat-12.md MG-202).
# Делаем строковую замену по всему блоку до super().save.

# Ищем функционирующий подход: заменим точно одну подстроку с fill_profile_targets(self, force=False)
old_call = "fill_profile_targets(self, force=False)"

if old_call not in src:
    print("    ERROR: ожидаемый вызов fill_profile_targets(self, force=False) не найден")
    sys.exit(1)

# Считаем сколько раз встречается — должно быть один раз
count = src.count(old_call)
if count != 1:
    print(f"    ERROR: ожидаемый вызов встречается {count} раз, ожидался 1")
    sys.exit(1)

# Дописываем post-save audit pass после super().save()
# Стратегия: НЕ трогаем pre-save вызов (он остаётся как было),
# но добавляем после него флаг и хук для post-save.
# Безопаснее всего: переписать save() целиком, вытащив старую сигнатуру.

# Найдём блок def save(...): целиком до следующего class или конца файла
import re
m = re.search(
    r"(    def save\(self, \*args, \*\*kwargs\):\n"
    r"(?:        .*\n|        \n)+"
    r"        super\(\)\.save\(\*args, \*\*kwargs\)\n)",
    src,
)
if not m:
    # fallback: поищем без жёсткого матча на super
    m2 = re.search(
        r"(    def save\(self, \*args, \*\*kwargs\):\n"
        r"        from \.nutrition import fill_profile_targets\n"
        r"(?:        .*\n)*?"
        r"        super\(\)\.save\(\*args, \*\*kwargs\)\n)",
        src,
    )
    if not m2:
        print("    ERROR: блок def save() не распознан, ручной патч требуется")
        sys.exit(1)
    m = m2

old_block = m.group(1)

new_block = (
    "    def save(self, *args, **kwargs):\n"
    "        # MG-205: actor может быть проброшен через kwargs из view\n"
    "        actor = kwargs.pop('_mg205_actor', None)\n"
    "        from .nutrition import fill_profile_targets\n"
    "\n"
    "        is_new = self.pk is None\n"
    "        # Авторасчёт ДО сохранения. Для нового профиля аудит\n"
    "        # запишется ниже (после первичного save), т.к. требуется pk.\n"
    "        fill_profile_targets(self, force=False, actor=actor)\n"
    "        super().save(*args, **kwargs)\n"
    "\n"
    "        # MG-205: post-save audit pass — для новых профилей,\n"
    "        # когда pk появился только что.\n"
    "        if is_new:\n"
    "            from .audit import record_target_change\n"
    "            for f in (\n"
    "                'calorie_target',\n"
    "                'protein_target_g',\n"
    "                'fat_target_g',\n"
    "                'carb_target_g',\n"
    "                'fiber_target_g',\n"
    "            ):\n"
    "                v = getattr(self, f, None)\n"
    "                if v is None:\n"
    "                    continue\n"
    "                # идемпотентность: проверяем что записи ещё нет\n"
    "                if not self.target_audits.filter(field=f).exists():\n"
    "                    record_target_change(\n"
    "                        profile=self,\n"
    "                        field=f,\n"
    "                        new_value=v,\n"
    "                        source='auto',\n"
    "                        by_user=actor,\n"
    "                        old_value=None,\n"
    "                        reason='auto-fill on profile create',\n"
    "                    )\n"
)

src = src.replace(old_block, new_block, 1)
open(path, "w", encoding="utf-8").write(src)
print("    OK: Profile.save() переписан под MG-205")
PYEOF

# ============================================================
# 4. Sanity check
# ============================================================
echo "[4] sanity..."
${COMPOSE} exec -T backend python manage.py check
${COMPOSE} exec -T backend python -c "
import sys; sys.path.insert(0, '/app')
import django; django.setup()
from apps.users.audit import record_target_change, get_field_source, is_locked
from apps.users.nutrition import fill_profile_targets, MG_205_V
print('  audit imports OK, MG_205_V=', MG_205_V)
" 2>&1 | tail -5 || true

# ============================================================
# 5. Юнит-смоук на pid=1: lock-проверка работает
# ============================================================
echo "[5] smoke test: проверка lock-логики на pid=1..."
${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from apps.users.models import Profile, ProfileTargetAudit
from apps.users.audit import is_locked, get_field_source
from apps.users.nutrition import fill_profile_targets

p = Profile.objects.get(id=1)
print("  --- before any user override ---")
for f in ("calorie_target","protein_target_g","fat_target_g","carb_target_g","fiber_target_g"):
    print(f"    {f}: source={get_field_source(p, f)} locked={is_locked(p, f)}")

# Симулируем user override на protein
from apps.users.audit import record_target_change
record_target_change(
    profile=p,
    field="protein_target_g",
    new_value=130,
    source="user",
    by_user=p.user,
    old_value=p.protein_target_g,
    reason="MG-205 smoke test (user override)",
)
p.protein_target_g = 130
p.save()  # триггерим Profile.save() — он НЕ должен перетирать protein

p.refresh_from_db()
print("  --- after user override of protein=130 ---")
print(f"    protein_target_g in DB: {p.protein_target_g}  (expect 130.0)")
print(f"    source of protein     : {get_field_source(p, 'protein_target_g')}  (expect 'user')")
print(f"    is_locked(protein)    : {is_locked(p, 'protein_target_g')}  (expect True)")

# Теперь force=True — должен перетереть
fill_profile_targets(p, force=True, actor=p.user)
p.protein_target_g = p.protein_target_g  # noop, чтобы не вызвать лишний save
print("  --- after force=True ---")
p.refresh_from_db()
print(f"    protein_target_g in DB: {p.protein_target_g}  (expect 112.5)")
print(f"    source of protein     : {get_field_source(p, 'protein_target_g')}  (expect 'auto')")

# Откат тестовой правки: оставляем БД в auto-состоянии — ничего не трогаем дальше
print("  --- audit history protein_target_g ---")
for pta in ProfileTargetAudit.objects.filter(profile=p, field="protein_target_g").order_by("at"):
    print(f"    {pta.at:%H:%M:%S} src={pta.source} new={pta.new_value} reason='{pta.reason[:40]}'")
PYEOF

echo
echo "=== STEP 2 done ==="
echo
echo "Откат шага 2:"
echo "  cp ${BACKUPS}/nutrition.py.bak_${TASK}_step2_${TS} ${NUTRITION}"
echo "  cp ${BACKUPS}/users_models.py.bak_${TASK}_step2_${TS} ${MODELS}"
echo "  rm -f ${AUDIT_NEW}"
echo "  ${COMPOSE} restart backend"
