#!/usr/bin/env bash
# MG-606.B fix-2 — переписать test_trial_premium_200 под новую логику
# Старая семантика (trial → 200 на GET) теперь некорректна:
#   trial без перехода в active НЕ даёт «реального опыта» и read закрыт.
# Новая: trial — POST работает (фича активна), GET 403.
#
# Расположение: /opt/menugen/backend/scripts/patch_606b_fix_trial.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606b_fix_trial.sh 2>&1 | tee /tmp/patch_606b_fix_trial.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

TEST="${BACKEND}/apps/diary/tests/test_mg_605c_permissions.py"

BAKDIR="${ROOT}/backups/606b_fix_trial_${TS}"
mkdir -p "$BAKDIR"
cp "$TEST" "$BAKDIR/test_mg_605c_permissions.py.bak"
echo "Backup → $BAKDIR/"

python3 <<'PYEOF'
TEST = "/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py"
src = open(TEST).read()

old_block = '''    def test_trial_premium_200(self, db):
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
        assert client.get("/api/v1/diary/").status_code == 200'''

new_block = '''    def test_trial_premium_write_ok_read_forbidden(self, db):
        # MG-606.B: одинокий trial (без active в истории) НЕ даёт «реального опыта».
        # GET — 403, POST — 201 (фича активна, пока триал идёт).
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
        assert client.get("/api/v1/diary/").status_code == 403
        resp = client.post(
            "/api/v1/diary/",
            {
                "date": str(date.today()),
                "meal_type": "breakfast",
                "custom_name": "X",
                "quantity": 1,
                "nutrition": {"calories": {"value": 100}},
            },
            format="json",
        )
        assert resp.status_code == 201'''

assert old_block in src, "Старый блок test_trial_premium_200 не найден"
src = src.replace(old_block, new_block)
open(TEST, "w").write(src)
print("✓ test_trial_premium_200 → test_trial_premium_write_ok_read_forbidden")
PYEOF

# Проверка
echo
echo "--- TestPremiumGate тесты после фикса ---"
grep -nE "def test_" "$TEST" | head -10

# Прогон только TestPremiumGate
echo
echo "===================================================================="
echo "Прогон TestPremiumGate (sanity)"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/diary/tests/test_mg_605c_permissions.py::TestPremiumGate -v --tb=short

# Полный регресс diary
echo
echo "===================================================================="
echo "Регресс diary"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/diary/ --tb=short 2>&1 | tail -25

# Регресс subscriptions
echo
echo "===================================================================="
echo "Регресс subscriptions"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/subscriptions/ --tb=short 2>&1 | tail -10

echo
echo "PATCH-606.B fix-trial — финиш"
