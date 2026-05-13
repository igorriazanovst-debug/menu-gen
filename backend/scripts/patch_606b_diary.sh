#!/usr/bin/env bash
# MG-606.B — миграция diary с IsFamilyPremium на IsFamilyPremiumOrReadOnly
# Расположение: /opt/menugen/backend/scripts/patch_606b_diary.sh
# Запуск:
#   bash /opt/menugen/backend/scripts/patch_606b_diary.sh 2>&1 | tee /tmp/patch_606b.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

echo "===================================================================="
echo "PATCH-606.B — старт ($TS)"
echo "===================================================================="

# ── 1. Backup ─────────────────────────────────────────────────────────────
BAKDIR="${ROOT}/backups/606b_${TS}"
mkdir -p "$BAKDIR"
cp "${BACKEND}/apps/diary/views.py" "$BAKDIR/views.py.bak"
cp "${BACKEND}/apps/diary/tests/test_mg_605c_permissions.py" "$BAKDIR/test_mg_605c_permissions.py.bak"
echo "Backup → $BAKDIR/"

# ── 2. Патч diary/views.py через python ───────────────────────────────────
python3 <<PYEOF
import re

VIEWS = "${BACKEND}/apps/diary/views.py"
src = open(VIEWS).read()

# 2.1. Импорт: IsFamilyPremium → IsFamilyPremium, IsFamilyPremiumOrReadOnly
old_imp = "from apps.subscriptions.permissions import IsFamilyPremium"
new_imp = "from apps.subscriptions.permissions import IsFamilyPremium, IsFamilyPremiumOrReadOnly"
assert old_imp in src, "Не найден импорт IsFamilyPremium"
src = src.replace(old_imp, new_imp)

# 2.2. Все permission_classes [...IsFamilyPremium...] → ...IsFamilyPremiumOrReadOnly...
# Аккуратно: не трогаем строку импорта (она содержит "import").
# Заменяем только в permission_classes-строках.
new_lines = []
for line in src.split("\n"):
    if "permission_classes" in line and "IsFamilyPremium" in line and "IsFamilyPremiumOrReadOnly" not in line:
        new_line = line.replace("IsFamilyPremium", "IsFamilyPremiumOrReadOnly")
        new_lines.append(new_line)
    else:
        new_lines.append(line)
src = "\n".join(new_lines)

open(VIEWS, "w").write(src)
print("✓ diary/views.py пропатчен")
PYEOF

# ── 3. Проверить — все 5 permission_classes обновлены ────────────────────
echo
echo "--- permission_classes после патча ---"
grep -n "permission_classes" "${BACKEND}/apps/diary/views.py"

# ── 4. Переписать падающий тест test_expired_premium_403 ──────────────────
python3 <<'PYEOF'
TEST = "/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py"
src = open(TEST).read()

# Старый тест test_expired_premium_403 — изменить assert
old_block = '''    def test_expired_premium_403(self, db):
        family, head, _ = _make_family_with_premium(with_premium=False)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0")},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.EXPIRED,
            started_at=timezone.now() - timedelta(days=30),
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 403'''

# По новой логике (MG-606.B): expired → GET 200, write 403
new_block = '''    def test_expired_premium_read_ok_write_forbidden(self, db):
        # MG-606.B: после истечения подписки чтение остаётся, запись — нет.
        family, head, _ = _make_family_with_premium(with_premium=False)
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="premium",
            defaults={"name": "Premium", "price": Decimal("0")},
        )
        Subscription.objects.create(
            family=family,
            plan=plan,
            status=Subscription.Status.EXPIRED,
            started_at=timezone.now() - timedelta(days=30),
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = _auth(APIClient(), head)
        assert client.get("/api/v1/diary/").status_code == 200
        # запись — 403
        resp = client.post("/api/v1/diary/", {
            "date": str(date.today()),
            "meal_type": "breakfast",
            "custom_name": "X",
            "quantity": 1,
            "nutrition": {"calories": {"value": 100}},
        }, format="json")
        assert resp.status_code == 403'''

assert old_block in src, "Старый блок test_expired_premium_403 не найден"
src = src.replace(old_block, new_block)
open(TEST, "w").write(src)
print("✓ test_expired_premium_403 → test_expired_premium_read_ok_write_forbidden")
PYEOF

# ── 5. Новый тест-файл MG-606.B на гибкое поведение ───────────────────────
cat > "${BACKEND}/apps/diary/tests/test_mg_606b_premium_or_readonly.py" <<'PYEOF'
"""MG-606.B: тесты IsFamilyPremiumOrReadOnly на diary API.

Покрытие:
- active → GET 200, POST 201, PATCH 200, DELETE 204
- expired → GET 200, POST 403, PATCH 403, DELETE 403
- cancelled (без active в истории) → GET 403, POST 403
- никогда не было → GET 403, POST 403
- trial → POST 201 (active fallback), GET 403 (нет «опыта»)
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry
from apps.family.models import Family, FamilyMember
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


# ─── фабрики ───────────────────────────────────────────────────────────────

def _user(email):
    return User.objects.create_user(email=email, name="U", password="x12345")


def _family(email="head@e.com"):
    head = _user(email)
    family = Family.objects.create(owner=head, name="F")
    member = FamilyMember.objects.create(family=family, user=head, role=FamilyMember.Role.HEAD)
    return family, head, member


def _plan_premium():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "price": Decimal("0")},
    )
    return plan


def _sub(family, status, expires_in_days=30):
    now = timezone.now()
    return Subscription.objects.create(
        family=family,
        plan=_plan_premium(),
        status=status,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=expires_in_days),
    )


def _entry(member):
    return DiaryEntry.objects.create(
        member=member,
        date=date.today(),
        meal_type=DiaryEntry.MealType.BREAKFAST,
        custom_name="X",
        quantity=1,
        nutrition={"calories": {"value": 100}},
    )


def _auth(client, user):
    client.force_authenticate(user=user)
    return client


def _post_payload():
    return {
        "date": str(date.today()),
        "meal_type": "breakfast",
        "custom_name": "Toast",
        "quantity": 1,
        "nutrition": {"calories": {"value": 200}},
    }


# ─── 1. ACTIVE ─────────────────────────────────────────────────────────────

class TestActivePremium:
    def test_get_list_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_get_stats_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/stats/").status_code == 200

    def test_post_create_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.ACTIVE)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201

    def test_patch_own_ok(self, db):
        family, head, head_m = _family()
        _sub(family, Subscription.Status.ACTIVE)
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        r = c.patch(f"/api/v1/diary/{e.id}/", {"custom_name": "Y"}, format="json")
        assert r.status_code == 200

    def test_delete_own_ok(self, db):
        family, head, head_m = _family()
        _sub(family, Subscription.Status.ACTIVE)
        e = _entry(head_m)
        c = _auth(APIClient(), head)
        assert c.delete(f"/api/v1/diary/{e.id}/").status_code == 204


# ─── 2. EXPIRED ─────────────────────────────────────────────────────────────

class TestExpiredPremium:
    """Самая важная группа: read остаётся, write закрыт."""

    def test_get_list_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_get_stats_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/stats/").status_code == 200

    def test_get_water_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/water/").status_code == 200

    def test_get_detail_ok(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get(f"/api/v1/diary/{e.id}/").status_code == 200

    def test_post_create_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403

    def test_patch_forbidden(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.patch(f"/api/v1/diary/{e.id}/", {"custom_name": "Y"}, format="json").status_code == 403

    def test_delete_forbidden(self, db):
        family, head, head_m = _family()
        e = _entry(head_m)
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.delete(f"/api/v1/diary/{e.id}/").status_code == 403

    def test_water_post_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/water/", {"date": str(date.today()), "ml": 500}, format="json")
        assert r.status_code == 403


# ─── 3. CANCELLED only / no sub ─────────────────────────────────────────────

class TestNeverHadPremium:
    def test_no_sub_get_forbidden(self, db):
        family, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_no_sub_post_forbidden(self, db):
        family, head, _ = _family()
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403

    def test_cancelled_only_get_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.CANCELLED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_cancelled_only_post_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.CANCELLED, expires_in_days=-1)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403


# ─── 4. TRIAL только ────────────────────────────────────────────────────────

class TestTrialOnly:
    """trial: write можно (фича включена пока триал жив), но read-после-истечения нет — это не «реальный опыт»."""

    def test_get_forbidden(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.TRIAL)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 403

    def test_post_ok(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.TRIAL)
        c = _auth(APIClient(), head)
        r = c.post("/api/v1/diary/", _post_payload(), format="json")
        assert r.status_code == 201


# ─── 5. История: trial → active → expired ───────────────────────────────────

class TestHistoryActiveThenExpired:
    """Реальная история: был active, истёк, новой подписки нет. read должен сохраниться."""

    def test_get_ok_after_active_expired(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-30)
        c = _auth(APIClient(), head)
        assert c.get("/api/v1/diary/").status_code == 200

    def test_post_forbidden_after_active_expired(self, db):
        family, head, _ = _family()
        _sub(family, Subscription.Status.EXPIRED, expires_in_days=-30)
        c = _auth(APIClient(), head)
        assert c.post("/api/v1/diary/", _post_payload(), format="json").status_code == 403
PYEOF
echo "✓ создан apps/diary/tests/test_mg_606b_premium_or_readonly.py"

# ── 6. Прогон тестов ──────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Прогон новых тестов MG-606.B"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/diary/tests/test_mg_606b_premium_or_readonly.py -v --tb=short

echo
echo "===================================================================="
echo "Регресс diary (включая обновлённый 605C)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/diary/ -v --tb=short

echo
echo "===================================================================="
echo "Регресс subscriptions"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/subscriptions/ -v --tb=short 2>&1 | tail -15

echo
echo "PATCH-606.B — финиш"
