#!/usr/bin/env bash
# MG-606.C.1 fix-no-family — 9 тестов test_no_family ожидали 404, теперь
# Premium gate возвращает 403 раньше. Логика «нет семьи → нет Premium».
# Переименовываем + меняем assert.
# Расположение: /opt/menugen/backend/scripts/patch_606c1_fix_no_family.sh
# Запуск: bash /opt/menugen/backend/scripts/patch_606c1_fix_no_family.sh 2>&1 | tee /tmp/patch_606c1_fix_no_family.log

set -eu
ROOT="${PROJECT_DIR:-/opt/menugen}"
BACKEND="${ROOT}/backend"
COMPOSE="docker compose -f ${ROOT}/docker-compose.yml"
TS=$(date +%Y%m%d_%H%M%S)

TEST="${BACKEND}/apps/menu/tests/test_mg_602_views.py"

BAKDIR="${ROOT}/backups/606c1_fix_no_family_${TS}"
mkdir -p "$BAKDIR"
cp "$TEST" "$BAKDIR/test_mg_602_views.py.bak"
echo "Backup → $BAKDIR/"

python3 <<'PYEOF'
TEST = "/opt/menugen/backend/apps/menu/tests/test_mg_602_views.py"
src = open(TEST).read()

# Заменяем каждый блок по сигнатуре. Все блоки заканчиваются "assert resp.status_code == 404"
# (кроме test_list_no_family_returns_empty — там 200).
# Меняем имя теста (404 → 403) и сам assert.

replacements = [
    # 1) test_no_family_returns_404 → test_no_family_returns_403_premium_gate
    (
        '''    def test_no_family_returns_404(self, client, db):
        u = _mk_user(email="nf@x.com", name="NF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-generate"),
                           {"period_days": 1, "start_date": str(datetime.date.today())},
                           format="json")
        assert resp.status_code == 404''',
        '''    def test_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → нет Premium → 403 от gate (раньше: 404 из view).
        u = _mk_user(email="nf@x.com", name="NF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-generate"),
                           {"period_days": 1, "start_date": str(datetime.date.today())},
                           format="json")
        assert resp.status_code == 403''',
    ),
    # 2) test_list_no_family_returns_empty → test_list_no_family_returns_403_premium_gate
    (
        '''    def test_list_no_family_returns_empty(self, client, db):
        u = _mk_user(email="nfl@x.com", name="NFL")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-list"))
        assert resp.status_code == 200
        assert resp.data == [] or resp.data.get("results", []) == []''',
        '''    def test_list_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → нет Premium → 403 от gate (раньше: 200 + пустой список).
        u = _mk_user(email="nfl@x.com", name="NFL")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-list"))
        assert resp.status_code == 403''',
    ),
    # 3) test_detail_no_family_returns_404
    (
        '''    def test_detail_no_family_returns_404(self, client, db):
        u = _mk_user(email="nfd@x.com", name="NFD")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-detail", args=[1]))
        assert resp.status_code == 404''',
        '''    def test_detail_no_family_returns_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="nfd@x.com", name="NFD")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-detail", args=[1]))
        assert resp.status_code == 403''',
    ),
    # 4) test_delete_no_family_404
    (
        '''    def test_delete_no_family_404(self, client, db):
        u = _mk_user(email="dnf@x.com", name="DNF")
        client.force_authenticate(u)
        resp = client.delete(reverse("menu-delete", args=[999]))
        assert resp.status_code == 404''',
        '''    def test_delete_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="dnf@x.com", name="DNF")
        client.force_authenticate(u)
        resp = client.delete(reverse("menu-delete", args=[999]))
        assert resp.status_code == 403''',
    ),
    # 5) test_quarantine_list_no_family_404
    (
        '''    def test_quarantine_list_no_family_404(self, client, db):
        u = _mk_user(email="qnf@x.com", name="QNF")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 404''',
        '''    def test_quarantine_list_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="qnf@x.com", name="QNF")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-quarantine"))
        assert resp.status_code == 403''',
    ),
    # 6) test_restore_no_family_404
    (
        '''    def test_restore_no_family_404(self, client, db):
        u = _mk_user(email="rnf@x.com", name="RNF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-restore", args=[999]))
        assert resp.status_code == 404''',
        '''    def test_restore_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="rnf@x.com", name="RNF")
        client.force_authenticate(u)
        resp = client.post(reverse("menu-restore", args=[999]))
        assert resp.status_code == 403''',
    ),
    # 7) test_swap_no_family_404
    (
        '''    def test_swap_no_family_404(self, client, db):
        u = _mk_user(email="snf@x.com", name="SNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[1, 1]),
                            {"recipe_id": 1}, format="json")
        assert resp.status_code == 404''',
        '''    def test_swap_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="snf@x.com", name="SNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("menu-item-swap", args=[1, 1]),
                            {"recipe_id": 1}, format="json")
        assert resp.status_code == 403''',
    ),
    # 8) test_shopping_no_family_404
    (
        '''    def test_shopping_no_family_404(self, client, db):
        u = _mk_user(email="snf2@x.com", name="SNF2")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-shopping-list", args=[1]))
        assert resp.status_code == 404''',
        '''    def test_shopping_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="snf2@x.com", name="SNF2")
        client.force_authenticate(u)
        resp = client.get(reverse("menu-shopping-list", args=[1]))
        assert resp.status_code == 403''',
    ),
    # 9) test_toggle_item_no_family_404
    (
        '''    def test_toggle_item_no_family_404(self, client, db):
        u = _mk_user(email="tnf@x.com", name="TNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("shopping-item-toggle", args=[1, 1]))
        assert resp.status_code == 404''',
        '''    def test_toggle_item_no_family_403_premium_gate(self, client, db):
        # MG-606.C: нет семьи → 403 от Premium gate.
        u = _mk_user(email="tnf@x.com", name="TNF")
        client.force_authenticate(u)
        resp = client.patch(reverse("shopping-item-toggle", args=[1, 1]))
        assert resp.status_code == 403''',
    ),
]

n_ok = 0
for old, new in replacements:
    if old not in src:
        print(f"  ✗ НЕ найден блок (первая строка): {old.splitlines()[0]}")
        continue
    src = src.replace(old, new)
    n_ok += 1
    print(f"  ✓ заменён: {old.splitlines()[0].strip()}")

open(TEST, "w").write(src)
print(f"\nИтого: {n_ok}/9 блоков заменено")
assert n_ok == 9, f"Не все блоки заменены ({n_ok}/9). Прерываю."
PYEOF

echo
echo "--- Проверка новых имён тестов ---"
grep -nE "def test_.*no_family" "$TEST"

# Прогон только test_mg_602_views.py
echo
echo "===================================================================="
echo "Прогон test_mg_602_views.py"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/menu/tests/test_mg_602_views.py -v --tb=short 2>&1 | tail -60

echo
echo "===================================================================="
echo "Полный регресс menu (sanity)"
echo "===================================================================="
$COMPOSE exec -T -e PYTHONUNBUFFERED=1 backend \
  pytest apps/menu/ --tb=short 2>&1 | tail -10

echo
echo "PATCH-606.C.1 fix-no-family — финиш"
