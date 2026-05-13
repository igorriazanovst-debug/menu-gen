#!/usr/bin/env bash
# MG-606.B finalize — переписать test_expired_premium_403 под новую логику + регресс
# Расположение: /opt/menugen/backend/scripts/patch_606b_diary_finalize.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606b_diary_finalize.sh 2>&1 | tee /tmp/patch_606b_finalize.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

TEST="${BACKEND}/apps/diary/tests/test_mg_605c_permissions.py"

echo "===================================================================="
echo "PATCH-606.B-finalize — старт ($TS)"
echo "===================================================================="

# ── 1. Backup ─────────────────────────────────────────────────────────────
BAKDIR="${ROOT}/backups/606b_finalize_${TS}"
mkdir -p "$BAKDIR"
cp "$TEST" "$BAKDIR/test_mg_605c_permissions.py.bak"
echo "Backup → $BAKDIR/"

# ── 2. Замена точного блока (со status=ACTIVE + истёкшая дата) ────────────
python3 <<'PYEOF'
TEST = "/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py"
src = open(TEST).read()

old_block = '''    def test_expired_premium_403(self, db):
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
        assert client.get("/api/v1/diary/").status_code == 403'''

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
            status=Subscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=60),
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = _auth(APIClient(), head)
        # MG-606.B: GET доступен после истечения (статус ACTIVE в истории).
        assert client.get("/api/v1/diary/").status_code == 200
        # запись — 403
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
        assert resp.status_code == 403'''

assert old_block in src, "Старый блок не найден — файл уже изменён?"
src = src.replace(old_block, new_block)
open(TEST, "w").write(src)
print("✓ test_expired_premium_403 → test_expired_premium_read_ok_write_forbidden")
PYEOF

# ── 3. Проверка импорта date в test_mg_605c_permissions.py ────────────────
if ! grep -qE "^from datetime import.*\bdate\b" "$TEST"; then
  echo
  echo "ВНИМАНИЕ: 'date' не импортирован в test_mg_605c_permissions.py — добавляю."
  python3 <<'PYEOF'
TEST = "/opt/menugen/backend/apps/diary/tests/test_mg_605c_permissions.py"
src = open(TEST).read()

# Найти строку 'from datetime import ...' и добавить 'date'
import re
m = re.search(r"^(from datetime import )([^\n]+)$", src, re.MULTILINE)
if m:
    parts = [p.strip() for p in m.group(2).split(",")]
    if "date" not in parts:
        parts.append("date")
        new_line = m.group(1) + ", ".join(sorted(set(parts)))
        src = src[:m.start()] + new_line + src[m.end():]
        open(TEST, "w").write(src)
        print("✓ добавлен 'date' в from datetime import ...")
    else:
        print("✓ 'date' уже импортирован")
else:
    # Импорта вообще нет — добавим
    src = "from datetime import date\n" + src
    open(TEST, "w").write(src)
    print("✓ добавлен новый импорт 'from datetime import date'")
PYEOF
else
  echo "✓ 'date' уже импортирован в test_mg_605c_permissions.py"
fi

# ── 4. Подтверждение — показать новое имя теста ───────────────────────────
echo
echo "--- Тесты в test_mg_605c_permissions.py:TestPremiumGate ---"
grep -nE "def test_" "$TEST" | head -15

# ── 5. Прогон ─────────────────────────────────────────────────────────────
echo
echo "===================================================================="
echo "Прогон новых тестов MG-606.B"
echo "===================================================================="
$COMPOSE exec -T backend pytest \
  apps/diary/tests/test_mg_606b_premium_or_readonly.py -v --tb=short

echo
echo "===================================================================="
echo "Регресс diary (включая адаптированный 605C)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/diary/ -v --tb=short

echo
echo "===================================================================="
echo "Регресс subscriptions (sanity)"
echo "===================================================================="
$COMPOSE exec -T backend pytest apps/subscriptions/ --tb=short 2>&1 | tail -10

echo
echo "PATCH-606.B-finalize — финиш"
