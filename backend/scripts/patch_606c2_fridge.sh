#!/usr/bin/env bash
# MG-606.C.2 — Premium gate на fridge/views.py + адаптация тестов + новый тест-файл
# Расположение: /opt/menugen/backend/scripts/patch_606c2_fridge.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606c2_fridge.sh 2>&1 | tee /tmp/patch_606c2_fridge.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)
BAKDIR="${ROOT}/backups/606c2_${TS}"
mkdir -p "$BAKDIR"

echo "===================================================================="
echo "PATCH-606.C.2 (fridge) — старт ($TS)"
echo "===================================================================="

# ─────────────────────────────────────────────────────────────────────────
# 1) views: добавить IsFamilyPremiumOrReadOnly во все 4 fridge views
# ─────────────────────────────────────────────────────────────────────────
cp "${BACKEND}/apps/fridge/views.py" "$BAKDIR/fridge_views.py.bak"

python3 <<'PYEOF'
VIEWS = "/opt/menugen/backend/apps/fridge/views.py"
src = open(VIEWS).read()

# 1.1. Добавить импорт после первого 'from apps.family.models import FamilyMember'
old_imp = "from apps.family.models import FamilyMember"
new_imp = (
    "from apps.family.models import FamilyMember\n"
    "from apps.subscriptions.permissions import IsFamilyPremiumOrReadOnly"
)
assert old_imp in src, "не найден импорт FamilyMember"
if "IsFamilyPremiumOrReadOnly" not in src:
    src = src.replace(old_imp, new_imp, 1)

# 1.2. Заменить все 'permission_classes = [permissions.IsAuthenticated]'
old_pc = "permission_classes = [permissions.IsAuthenticated]"
new_pc = "permission_classes = [permissions.IsAuthenticated, IsFamilyPremiumOrReadOnly]"
count = src.count(old_pc)
assert count == 4, f"ожидалось 4 совпадений, нашлось {count}"
src = src.replace(old_pc, new_pc)
open(VIEWS, "w").write(src)
print(f"✓ fridge/views.py: {count}/4 permission_classes + импорт")
PYEOF

echo
echo "--- fridge/views.py permission_classes после патча ---"
grep -n "permission_classes" "${BACKEND}/apps/fridge/views.py"

# ─────────────────────────────────────────────────────────────────────────
# 2) Адаптировать fridge/test_fridge.py — добавить _attach_premium в user_with_family
# ─────────────────────────────────────────────────────────────────────────
cp "${BACKEND}/apps/fridge/tests/test_fridge.py" "$BAKDIR/test_fridge.py.bak"

python3 <<'PYEOF'
import re

TEST = "/opt/menugen/backend/apps/fridge/tests/test_fridge.py"
src = open(TEST).read()

if "_attach_premium" in src:
    print("✓ test_fridge.py уже содержит _attach_premium — пропуск")
else:
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
    if not src.endswith("\n"):
        src += "\n"
    src = src + HELPER
    print("✓ test_fridge.py: добавлен _attach_premium")

# Вставка вызова после каждого Family.objects.create
lines = src.split("\n")
out = []
i = 0
n = len(lines)
inserted = 0
while i < n:
    line = lines[i]
    m = re.match(r"^(?P<indent>[ \t]+)(?P<var>\w+)\s*=\s*Family\.objects\.create\(", line)
    if m:
        indent = m.group("indent")
        var = m.group("var")
        buf = [line]
        depth = line.count("(") - line.count(")")
        j = i + 1
        while depth > 0 and j < n:
            buf.append(lines[j])
            depth += lines[j].count("(") - lines[j].count(")")
            j += 1
        tail = "\n".join(lines[j:j+3])
        if f"_attach_premium({var})" in tail:
            out.extend(buf)
            i = j
            continue
        out.extend(buf)
        out.append(f"{indent}_attach_premium({var})")
        inserted += 1
        i = j
    else:
        out.append(line)
        i += 1
src = "\n".join(out)
open(TEST, "w").write(src)
print(f"✓ test_fridge.py: вставлено _attach_premium {inserted} раз")
PYEOF

# ─────────────────────────────────────────────────────────────────────────
# 3) Новый тест-файл MG-606.C на сам гейт fridge
# ─────────────────────────────────────────────────────────────────────────
cat > "${BACKEND}/apps/fridge/tests/test_mg_606c_premium_gate.py" <<'PYEOF'
"""MG-606.C: Premium gate на fridge API.

Покрытие: без Premium → 403, active → 200, expired (active+истёкший по дате) → GET 200, POST 403.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
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
    p, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return p


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family, plan=_plan(), status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _auth(c, u):
    c.force_authenticate(u)
    return c


@pytest.mark.django_db
class TestFridgePremiumGate:
    def test_list_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 403

    def test_list_active_premium_200(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 200

    def test_create_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 403

    def test_create_active_premium_201(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 201

    def test_list_expired_premium_200_readonly(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get(reverse("fridge-list")).status_code == 200

    def test_create_expired_premium_403(self, db):
        family, head = _family()
        _sub(family, Subscription.Status.ACTIVE, expires_in_days=-1)
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-list"), {"name": "Молоко"}, format="json")
        assert resp.status_code == 403

    def test_barcode_scan_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        resp = c.post(reverse("fridge-scan"), {"barcode": "1234567890"}, format="json")
        assert resp.status_code == 403

    def test_product_search_no_premium_403(self, db):
        family, head = _family()
        c = _auth(APIClient(), head)
        # search — GET, но без премиум-истории → 403
        assert c.get("/api/v1/fridge/products/").status_code == 403
PYEOF
echo "✓ создан apps/fridge/tests/test_mg_606c_premium_gate.py"

# ─────────────────────────────────────────────────────────────────────────
# 4) Прогоны
# ─────────────────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Прогон MG-606.C fridge"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/fridge/tests/test_mg_606c_premium_gate.py -v --tb=short

echo
echo "===================================================================="
echo "Регресс fridge"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/fridge/ -v --tb=short

echo
echo "===================================================================="
echo "Sanity: diary + subscriptions + menu"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/diary/ apps/subscriptions/ apps/menu/ --tb=short 2>&1 | tail -10

echo
echo "PATCH-606.C.2 (fridge) — финиш"
