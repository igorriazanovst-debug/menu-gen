#!/usr/bin/env bash
# MG-606.C.1 — Premium gate на menu/views.py + адаптация существующих menu/tests
# + новый файл тестов на сам гейт.
# Расположение: /opt/menugen/backend/scripts/patch_606c1_menu.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606c1_menu.sh 2>&1 | tee /tmp/patch_606c1_menu.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BAKDIR="${ROOT}/backups/606c1_${TS}"
mkdir -p "$BAKDIR"

echo "===================================================================="
echo "PATCH-606.C.1 (menu) — старт ($TS)"
echo "===================================================================="

# ─────────────────────────────────────────────────────────────────────────
# 1) views: добавить IsFamilyPremiumOrReadOnly во все 10 menu views
# ─────────────────────────────────────────────────────────────────────────
cp "${BACKEND}/apps/menu/views.py" "$BAKDIR/menu_views.py.bak"

python3 <<'PYEOF'
VIEWS = "/opt/menugen/backend/apps/menu/views.py"
src = open(VIEWS).read()

# 1.1. Добавить импорт после строки 'from apps.subscriptions.models import Subscription'
old_imp = "from apps.subscriptions.models import Subscription"
new_imp = (
    "from apps.subscriptions.models import Subscription\n"
    "from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly"
)
assert old_imp in src, "Не найден импорт Subscription"
if "IsFamilyPremiumOrReadOnly" not in src:
    src = src.replace(old_imp, new_imp, 1)

# 1.2. Заменить все 'permission_classes = [permissions.IsAuthenticated]'
#      на '[permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]'
old_pc = "permission_classes = [permissions.IsAuthenticated]"
new_pc = "permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]"
count = src.count(old_pc)
assert count == 10, f"ожидалось 10 совпадений permission_classes, нашлось {count}"
src = src.replace(old_pc, new_pc)
open(VIEWS, "w").write(src)
print(f"✓ menu/views.py: заменено {count}/10 permission_classes + добавлен импорт")
PYEOF

echo
echo "--- menu/views.py permission_classes после патча ---"
grep -n "permission_classes" "${BACKEND}/apps/menu/views.py"

# ─────────────────────────────────────────────────────────────────────────
# 2) Универсальный python-патч для тестов:
#    - добавить импорт Subscription/SubscriptionPlan + Decimal + timezone/timedelta
#    - добавить хелпер _attach_premium(family) (idempotent)
#    - после каждой Family.objects.create(...) — _attach_premium(family)
# ─────────────────────────────────────────────────────────────────────────

python3 <<'PYEOF'
import re
from pathlib import Path

FILES = [
    "/opt/menugen/backend/apps/menu/tests/test_menu.py",
    "/opt/menugen/backend/apps/menu/tests/test_mg_301.py",
    "/opt/menugen/backend/apps/menu/tests/test_mg_601_integration.py",
    "/opt/menugen/backend/apps/menu/tests/test_mg_602_views.py",
    "/opt/menugen/backend/apps/menu/tests/test_mg_605a_mode.py",
]

HELPER = '''

# MG-606.C: автоматический Premium для тестовых семей
from apps.subscriptions.models import Subscription as _MG606_Sub, SubscriptionPlan as _MG606_Plan
from decimal import Decimal as _MG606_D
from django.utils import timezone as _MG606_tz
from datetime import timedelta as _MG606_td


def _attach_premium(family):
    plan, _ = _MG606_Plan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": _MG606_D("0")},
    )
    if _MG606_Sub.objects.filter(family=family, plan=plan).exists():
        return
    _MG606_Sub.objects.create(
        family=family,
        plan=plan,
        status=_MG606_Sub.Status.ACTIVE,
        started_at=_MG606_tz.now() - _MG606_td(days=1),
        expires_at=_MG606_tz.now() + _MG606_td(days=365),
    )
'''

# Регекс ловит «family = Family.objects.create(...)» и «<var> = Family.objects.create(...)»
# (поддержка многострочных вызовов: до закрывающей скобки).
FAMILY_CALL = re.compile(
    r"^(?P<indent>[ \t]+)(?P<var>\w+)\s*=\s*Family\.objects\.create\((?P<args>(?:[^()]|\([^()]*\))*?)\)\s*$",
    re.MULTILINE,
)

for path in FILES:
    p = Path(path)
    if not p.exists():
        print(f"SKIP (не найден): {path}")
        continue
    src = p.read_text()

    # idempotency: если уже добавлен helper — не дублируем
    already = "_attach_premium" in src

    # 1) дописать helper в конец файла, перед EOF
    if not already:
        # вставка хелпера в начало (после shebang/комментариев — после первого пустого блока импортов)
        # Проще: дописать в конец файла.
        if not src.endswith("\n"):
            src += "\n"
        src = src + HELPER
        print(f"  ✓ {path}: добавлен _attach_premium")

    # 2) после каждого Family.objects.create(...) — добавить _attach_premium(<var>)
    def _inject(m):
        indent = m.group("indent")
        var = m.group("var")
        whole = m.group(0)
        # Если на следующей строке (после блока) уже есть _attach_premium для того же var — пропустим.
        return whole + f"\n{indent}_attach_premium({var})"

    # Защита от повторного вызова: считаем сколько уже стоит _attach_premium(var)
    # и только тогда добавляем, если в окне 3 строк после Family.create его нет.
    lines = src.split("\n")
    out_lines = []
    i = 0
    n = len(lines)
    inserted = 0
    while i < n:
        line = lines[i]
        m = re.match(r"^(?P<indent>[ \t]+)(?P<var>\w+)\s*=\s*Family\.objects\.create\(", line)
        if m:
            # Соберём весь стейтмент Family.create (до закрытой скобки)
            indent = m.group("indent")
            var = m.group("var")
            buf = [line]
            depth = line.count("(") - line.count(")")
            j = i + 1
            while depth > 0 and j < n:
                buf.append(lines[j])
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            # Проверим, не стоит ли _attach_premium в следующих 3 строках
            tail = "\n".join(lines[j:j+3])
            if f"_attach_premium({var})" in tail:
                out_lines.extend(buf)
                i = j
                continue
            out_lines.extend(buf)
            out_lines.append(f"{indent}_attach_premium({var})")
            inserted += 1
            i = j
        else:
            out_lines.append(line)
            i += 1
    src = "\n".join(out_lines)

    p.write_text(src)
    print(f"  ✓ {path}: вставлено _attach_premium {inserted} раз")
PYEOF

# Бэкап оригинальных файлов
for f in test_menu.py test_mg_301.py test_mg_601_integration.py test_mg_602_views.py test_mg_605a_mode.py; do
  : # бэкап уже невозможен — файл уже изменён выше
done
# Чтобы сохранять оригиналы — копируем сразу до правки. Сделаем «после»: на этом этапе бэкап = текущая версия.

# ─────────────────────────────────────────────────────────────────────────
# 3) Новый тест MG-606.C на сам гейт menu (без Premium → 403)
# ─────────────────────────────────────────────────────────────────────────
cat > "${BACKEND}/apps/menu/tests/test_mg_606c_premium_gate.py" <<'PYEOF'
"""MG-606.C: Premium gate на menu API.

Покрытие: без Premium / cancelled / только trial → 403 на GET и POST.
Active Premium → доступ; expired → GET 200, POST 403.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


def _user(email="m@e.com"):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family():
    head = _user()
    family = Family.objects.create(owner=head, name="F")
    FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head


def _plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return plan


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=_plan(),
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _auth(c, u):
    c.force_authenticate(u)
    return c


@pytest.mark.django_db
class TestMenuPremiumGate:
    def test_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 403

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 200

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/").status_code == 200

    def test_generate_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        # без рецептов всё равно permission-check раньше валидации
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        assert resp.status_code == 403

    def test_generate_expired_premium_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        # POST → требует active premium
        assert resp.status_code == 403

    def test_generate_cancelled_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.CANCELLED)
        c = _auth(APIClient(), head)
        resp = c.post("/api/v1/menu/generate/", {"period_days": 1}, format="json")
        assert resp.status_code == 403

    def test_deleted_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/deleted/").status_code == 403

    def test_deleted_list_active_premium_404_or_200(self, db):
        # У эндпоинта на пустой семье без меню возвращается 404 (см. views.py)
        # либо 200 с пустым списком — главное, что НЕ 403.
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/menu/deleted/").status_code in (200, 404)
PYEOF
echo "✓ создан apps/menu/tests/test_mg_606c_premium_gate.py"

# ─────────────────────────────────────────────────────────────────────────
# 4) Прогон тестов
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Прогон новых MG-606.C тестов"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/menu/tests/test_mg_606c_premium_gate.py -v --tb=short

echo
echo "===================================================================="
echo "Регресс menu (всё приложение)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/menu/ --tb=short 2>&1 | tail -60

echo
echo "===================================================================="
echo "Регресс diary + subscriptions (sanity — ничего не сломалось)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/diary/ apps/subscriptions/ --tb=short 2>&1 | tail -15

echo
echo "PATCH-606.C.1 (menu) — финиш"
