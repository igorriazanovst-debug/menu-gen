#!/usr/bin/env bash
# MG-205 apply STEP 1/4: модель ProfileTargetAudit + миграция + seed
# Идемпотентен: проверяет наличие класса ProfileTargetAudit перед добавлением.
# Запуск: bash /opt/menugen/backend/scripts/mg_205_apply_1_model.sh

set -eu
PROJECT_ROOT="/opt/menugen"
BACKEND="${PROJECT_ROOT}/backend"
COMPOSE="docker compose -f ${PROJECT_ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
TASK="mg205"

USERS_MODELS="${BACKEND}/apps/users/models.py"
BACKUPS="${PROJECT_ROOT}/backups"
mkdir -p "${BACKUPS}"

echo "=== MG-205 apply STEP 1 ==="
echo "TS=${TS}"

# ---------- 0. Бэкапы ----------
echo "[0] backups..."
${COMPOSE} exec -T db pg_dump -U menugen_user -d menugen --no-owner --no-acl \
  | gzip > "${BACKUPS}/before_${TASK}_step1_${TS}.sql.gz"
cp "${USERS_MODELS}" "${BACKUPS}/users_models.py.bak_${TASK}_${TS}"
echo "    DB     : ${BACKUPS}/before_${TASK}_step1_${TS}.sql.gz"
echo "    models : ${BACKUPS}/users_models.py.bak_${TASK}_${TS}"

# ---------- 1. Добавление модели ProfileTargetAudit в models.py ----------
echo "[1] добавляю класс ProfileTargetAudit..."
python3 - <<'PYEOF'
import io, re, sys
path = "/opt/menugen/backend/apps/users/models.py"
src = open(path, encoding="utf-8").read()

if "class ProfileTargetAudit" in src:
    print("    SKIP: ProfileTargetAudit уже существует")
    sys.exit(0)

if "MG_205_V" in src:
    print("    SKIP: маркер MG_205_V найден — модель добавлена ранее")
    sys.exit(0)

addition = '''

# ============================================================
# MG-205: аудит источника правок целей КБЖУ
# ============================================================
MG_205_V = 1


class ProfileTargetAudit(models.Model):
    """История правок полей КБЖУ профиля.

    Источник изменения: 'auto' (рассчитал fill_profile_targets),
    'user' (поставил сам пользователь), 'specialist' (диетолог/тренер).
    Текущий источник для поля = source последней записи (по at desc).
    """

    class Field(models.TextChoices):
        CALORIE = "calorie_target", "calorie_target"
        PROTEIN = "protein_target_g", "protein_target_g"
        FAT = "fat_target_g", "fat_target_g"
        CARB = "carb_target_g", "carb_target_g"
        FIBER = "fiber_target_g", "fiber_target_g"

    class Source(models.TextChoices):
        AUTO = "auto", "auto"
        USER = "user", "user"
        SPECIALIST = "specialist", "specialist"

    profile = models.ForeignKey(
        "Profile", on_delete=models.CASCADE, related_name="target_audits"
    )
    field = models.CharField(max_length=32, choices=Field.choices)
    source = models.CharField(max_length=16, choices=Source.choices)
    by_user = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_target_edits",
    )
    old_value = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    new_value = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    reason = models.TextField(blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profile_target_audit"
        indexes = [
            models.Index(fields=["profile", "field", "-at"]),
        ]
        ordering = ["-at"]

    def __str__(self):
        return f"PTA(pid={self.profile_id}, {self.field}={self.new_value}, src={self.source})"
'''

# Дописываем в самый конец файла
if not src.endswith("\n"):
    src += "\n"
src += addition

open(path, "w", encoding="utf-8").write(src)
print("    OK: класс добавлен")
PYEOF

# ---------- 2. makemigrations ----------
echo "[2] makemigrations users..."
${COMPOSE} exec -T backend python manage.py makemigrations users

# ---------- 3. migrate ----------
echo "[3] migrate users..."
${COMPOSE} exec -T backend python manage.py migrate users

# ---------- 4. Data-migration: seed существующих targets как source='auto' ----------
echo "[4] seed: существующие targets → ProfileTargetAudit(source='auto')..."
${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from apps.users.models import Profile, ProfileTargetAudit
from decimal import Decimal

FIELDS = [
    ("calorie_target", ProfileTargetAudit.Field.CALORIE),
    ("protein_target_g", ProfileTargetAudit.Field.PROTEIN),
    ("fat_target_g", ProfileTargetAudit.Field.FAT),
    ("carb_target_g", ProfileTargetAudit.Field.CARB),
    ("fiber_target_g", ProfileTargetAudit.Field.FIBER),
]

created = 0
skipped = 0
for p in Profile.objects.all():
    for attr, field_choice in FIELDS:
        val = getattr(p, attr)
        if val is None:
            continue
        # идемпотентность: если уже есть аудит-запись по этому полю — пропускаем
        if ProfileTargetAudit.objects.filter(profile=p, field=field_choice).exists():
            skipped += 1
            continue
        ProfileTargetAudit.objects.create(
            profile=p,
            field=field_choice,
            source=ProfileTargetAudit.Source.AUTO,
            by_user=None,
            old_value=None,
            new_value=Decimal(str(val)),
            reason="MG-205 initial seed (existing values assumed auto-calculated)",
        )
        created += 1

print(f"    seeded: {created}, skipped: {skipped}")
PYEOF

# ---------- 5. sanity ----------
echo "[5] sanity..."
${COMPOSE} exec -T backend python manage.py check
${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from apps.users.models import Profile, ProfileTargetAudit
print("  Profile count        :", Profile.objects.count())
print("  ProfileTargetAudit ct:", ProfileTargetAudit.objects.count())
for pta in ProfileTargetAudit.objects.all().order_by("profile_id", "field"):
    print(f"    pid={pta.profile_id} {pta.field}={pta.new_value} src={pta.source} at={pta.at:%Y-%m-%d %H:%M}")
PYEOF

echo
echo "=== STEP 1 done ==="
echo
echo "Откат шага 1:"
echo "  cp ${BACKUPS}/users_models.py.bak_${TASK}_${TS} ${USERS_MODELS}"
echo "  ${COMPOSE} exec -T backend python manage.py migrate users 0003"
echo "  rm -f ${BACKEND}/apps/users/migrations/0004_*.py"
echo "  gunzip -c ${BACKUPS}/before_${TASK}_step1_${TS}.sql.gz | ${COMPOSE} exec -T db psql -U menugen_user -d menugen"
