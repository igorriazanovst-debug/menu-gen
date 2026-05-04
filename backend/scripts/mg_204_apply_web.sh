#!/usr/bin/env bash
# MG-204 apply (web only): types + api/family + FamilyMemberEditModal + DayNutritionSummary
# + интеграция в FamilyPage и MenuPage
#
# Идемпотентен: маркер MG_204_V_<part> = 1
# Бэкапы: .bak_mg204_<TS>

set -euo pipefail

WEB="/opt/menugen/web/menugen-web"
SRC="$WEB/src"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUPS="/opt/menugen/backups"
mkdir -p "$BACKUPS"

MARK_TYPES="MG_204_V_types = 1"
MARK_API="MG_204_V_api = 1"
MARK_FAM="MG_204_V_family = 1"
MARK_MENU="MG_204_V_menu = 1"
MARK_SUM="MG_204_V_summary = 1"

bak() {
  local f="$1"
  local name="$(basename "$f")"
  cp "$f" "$BACKUPS/${name}.bak_mg204_${TS}"
  echo "  backup → $BACKUPS/${name}.bak_mg204_${TS}"
}

echo "=========================================="
echo "MG-204 APPLY (web only)  TS=$TS"
echo "=========================================="
echo

# ── 1. types/index.ts ──────────────────────────────────────────────────────────
echo "### 1. types/index.ts: расширяем FamilyMember ###"
T="$SRC/types/index.ts"
if grep -q "$MARK_TYPES" "$T"; then
  echo "  уже применено (маркер $MARK_TYPES)"
else
  bak "$T"
  python3 <<PYEOF
import re
path = "$T"
s = open(path, encoding='utf-8').read()

# Заменяем интерфейс FamilyMember целиком
new_block = """// $MARK_TYPES
export interface FamilyMember {
  id: number; user_id: number; name: string; email?: string;
  avatar_url?: string; role: 'head' | 'member' | 'owner'; joined_at: string;
  allergies?: string[];
  disliked_products?: string[];
  profile?: UserProfile | null;
}"""

pat = re.compile(
    r"export interface FamilyMember \{[^}]*\}",
    re.DOTALL,
)
if not pat.search(s):
    raise SystemExit("FamilyMember interface not found in types/index.ts")
s2 = pat.sub(new_block, s, count=1)
open(path, 'w', encoding='utf-8').write(s2)
print("  patched FamilyMember")
PYEOF
fi
echo

# ── 2. api/family.ts ───────────────────────────────────────────────────────────
echo "### 2. api/family.ts: добавляем updateMember ###"
F="$SRC/api/family.ts"
if grep -q "$MARK_API" "$F"; then
  echo "  уже применено"
else
  bak "$F"
  cat > "$F" <<'TS_EOF'
// MG_204_V_api = 1
import client from './client';
import type { Family, FamilyMember, UserProfile } from '../types';

export interface FamilyMemberUpdatePayload {
  name?: string;
  allergies?: string[];
  disliked_products?: string[];
  profile?: Partial<UserProfile>;
}

export const familyApi = {
  get: () => client.get<Family>('/family/'),
  rename: (name: string) => client.patch<Family>('/family/', { name }),
  invite: (email?: string, phone?: string) =>
    client.post('/family/invite/', { email, phone }),
  removeMember: (memberId: number) =>
    client.delete(`/family/members/${memberId}/`),
  updateMember: (memberId: number, payload: FamilyMemberUpdatePayload) =>
    client.patch<FamilyMember>(`/family/members/${memberId}/update/`, payload),
};
TS_EOF
  echo "  rewrote $F"
fi
echo

# ── 3. components/family/FamilyMemberEditModal.tsx ─────────────────────────────
echo "### 3. components/family/FamilyMemberEditModal.tsx ###"
DIR="$SRC/components/family"
mkdir -p "$DIR"
EDIT_MODAL="$DIR/FamilyMemberEditModal.tsx"
if [ -f "$EDIT_MODAL" ] && grep -q "$MARK_FAM" "$EDIT_MODAL"; then
  echo "  уже создан"
else
  [ -f "$EDIT_MODAL" ] && bak "$EDIT_MODAL"
  cat > "$EDIT_MODAL" <<'TSX_EOF'
// MG_204_V_family = 1
import React, { useState } from 'react';
import type { FamilyMember, MealPlan } from '../../types';
import { familyApi } from '../../api/family';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { getErrorMessage } from '../../utils/api';

interface Props {
  member: FamilyMember;
  onClose: () => void;
  onSaved: (updated: FamilyMember) => void;
}

const num = (v: string | number | null | undefined) =>
  v === null || v === undefined || v === '' ? '—' : String(v);

const MacroPill: React.FC<{
  label: string;
  value: string;
  unit: string;
  color: string;
}> = ({ label, value, unit, color }) => (
  <div className={`px-3 py-2 rounded-xl ${color}`}>
    <div className="text-xs opacity-70">{label}</div>
    <div className="font-semibold text-sm">
      {value} <span className="text-xs font-normal">{unit}</span>
    </div>
  </div>
);

export const FamilyMemberEditModal: React.FC<Props> = ({
  member, onClose, onSaved,
}) => {
  const [name, setName] = useState(member.name);
  const [mealPlan, setMealPlan] = useState<MealPlan>(
    (member.profile?.meal_plan_type as MealPlan) ?? '3'
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const profile = member.profile;

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const payload = {
        name: name.trim() || undefined,
        profile: { meal_plan_type: mealPlan },
      };
      const { data } = await familyApi.updateMember(member.id, payload);
      onSaved(data);
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg my-8"
        onClick={(e) => e.stopPropagation()}
      >
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-chocolate">
              Редактировать: {member.name}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            >
              ✕
            </button>
          </div>

          {/* имя */}
          <div>
            <label className="block text-sm text-gray-600 mb-1">Имя</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Имя участника"
            />
          </div>

          {/* КБЖУ — read only */}
          {profile && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Дневные цели
                <span className="ml-2 text-xs text-gray-400">
                  рассчитано автоматически
                </span>
              </label>
              <div className="grid grid-cols-5 gap-2">
                <MacroPill label="Ккал"  value={num(profile.calorie_target)}    unit="ккал" color="bg-tomato/10 text-tomato" />
                <MacroPill label="Белок" value={num(profile.protein_target_g)}  unit="г"    color="bg-blue-50 text-blue-700" />
                <MacroPill label="Жиры"  value={num(profile.fat_target_g)}      unit="г"    color="bg-amber-50 text-amber-700" />
                <MacroPill label="Углев" value={num(profile.carb_target_g)}     unit="г"    color="bg-emerald-50 text-emerald-700" />
                <MacroPill label="Клетч" value={num(profile.fiber_target_g)}    unit="г"    color="bg-purple-50 text-purple-700" />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                На основе пола, роста, веса, активности и цели. Изменить можно в профиле участника.
              </p>
            </div>
          )}

          {/* meal_plan_type */}
          <div>
            <label className="block text-sm text-gray-600 mb-2">
              Приёмов пищи в день
            </label>
            <div className="flex gap-2">
              {(['3', '5'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setMealPlan(v)}
                  className={`px-4 py-2 rounded-xl border transition ${
                    mealPlan === v
                      ? 'bg-tomato text-white border-tomato'
                      : 'bg-white text-chocolate border-gray-200 hover:border-tomato'
                  }`}
                >
                  {v === '3' ? '3 приёма' : '5 приёмов'}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose} disabled={saving}>
              Отмена
            </Button>
            <Button onClick={handleSave} loading={saving}>
              Сохранить
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
TSX_EOF
  echo "  created $EDIT_MODAL"
fi
echo

# ── 4. components/menu/DayNutritionSummary.tsx ─────────────────────────────────
echo "### 4. components/menu/DayNutritionSummary.tsx ###"
DIR2="$SRC/components/menu"
mkdir -p "$DIR2"
SUM="$DIR2/DayNutritionSummary.tsx"
if [ -f "$SUM" ] && grep -q "$MARK_SUM" "$SUM"; then
  echo "  уже создан"
else
  [ -f "$SUM" ] && bak "$SUM"
  cat > "$SUM" <<'TSX_EOF'
// MG_204_V_summary = 1
import React from 'react';
import type { MenuItem, NutritionTargets } from '../../types';

interface Props {
  items: MenuItem[];        // все MenuItem за конкретный day_offset
  targets?: NutritionTargets | null;
}

interface Totals {
  calories: number;
  proteins: number;
  fats: number;
  carbs: number;
  fiber: number;
}

const numToFloat = (v: string | number | undefined | null): number => {
  if (v === undefined || v === null || v === '') return 0;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n) ? n : 0;
};

function sumTotals(items: MenuItem[]): Totals {
  return items.reduce<Totals>(
    (acc, it) => {
      const n = it.recipe?.nutrition;
      if (!n) return acc;
      const q = it.quantity ?? 1;
      acc.calories += numToFloat(n.calories?.value) * q;
      acc.proteins += numToFloat(n.proteins?.value) * q;
      acc.fats     += numToFloat(n.fats?.value)     * q;
      acc.carbs    += numToFloat(n.carbs?.value)    * q;
      acc.fiber    += numToFloat(n.fiber?.value)    * q;
      return acc;
    },
    { calories: 0, proteins: 0, fats: 0, carbs: 0, fiber: 0 },
  );
}

/** % от цели; 0 если цель не задана / 0 */
const pct = (actual: number, target: number) =>
  target > 0 ? Math.round((actual / target) * 100) : 0;

/** Цвет полоски: зелёный 85-115%, жёлтый 60-130%, красный иначе */
const barColor = (p: number): string => {
  if (p === 0) return 'bg-gray-300';
  if (p >= 85 && p <= 115) return 'bg-green-500';
  if (p >= 60 && p <= 130) return 'bg-amber-500';
  return 'bg-red-500';
};

interface RowProps {
  label: string;
  actual: number;
  target: number;
  unit: string;
  fractionDigits?: number;
}

const NutrRow: React.FC<RowProps> = ({ label, actual, target, unit, fractionDigits = 0 }) => {
  const p = pct(actual, target);
  const widthPct = Math.min(p, 130); // визуально режем до 130%
  const fmt = (n: number) =>
    fractionDigits > 0 ? n.toFixed(fractionDigits) : Math.round(n).toString();
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="text-gray-700 tabular-nums">
          {fmt(actual)}
          {target > 0 && <span className="text-gray-400"> / {fmt(target)} {unit}</span>}
          {target === 0 && <span className="text-gray-400"> {unit}</span>}
          {target > 0 && <span className="ml-2 text-gray-400">{p}%</span>}
        </span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor(p)} transition-all`}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  );
};

export const DayNutritionSummary: React.FC<Props> = ({ items, targets }) => {
  if (!items || items.length === 0) return null;

  const t = sumTotals(items);
  const tgt = targets ?? null;

  return (
    <div className="px-3 py-3 bg-rice/40 rounded-xl border border-gray-100 space-y-2">
      <div className="text-xs font-medium text-chocolate/80">
        Итог за день
        {!tgt && (
          <span className="ml-2 text-gray-400 font-normal">
            (цели не заданы — заполните профиль)
          </span>
        )}
      </div>
      <NutrRow label="Калории" actual={t.calories} target={numToFloat(tgt?.calorie_target)}    unit="ккал" />
      <NutrRow label="Белок"   actual={t.proteins} target={numToFloat(tgt?.protein_target_g)}  unit="г" fractionDigits={1} />
      <NutrRow label="Жиры"    actual={t.fats}     target={numToFloat(tgt?.fat_target_g)}      unit="г" fractionDigits={1} />
      <NutrRow label="Углев"   actual={t.carbs}    target={numToFloat(tgt?.carb_target_g)}     unit="г" fractionDigits={1} />
      <NutrRow label="Клетч"   actual={t.fiber}    target={numToFloat(tgt?.fiber_target_g)}    unit="г" fractionDigits={1} />
    </div>
  );
};
TSX_EOF
  echo "  created $SUM"
fi
echo

# ── 5. FamilyPage.tsx — кнопка редактирования + модалка ────────────────────────
echo "### 5. FamilyPage.tsx: кнопка ✎ + интеграция модалки ###"
FP="$SRC/pages/Family/FamilyPage.tsx"
if grep -q "$MARK_FAM" "$FP"; then
  echo "  уже применено"
else
  bak "$FP"
  cat > "$FP" <<'TSX_EOF'
// MG_204_V_family = 1
import React, { useEffect, useState } from 'react';
import { familyApi } from '../../api/family';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { Family, FamilyMember } from '../../types';
import { FamilyMemberEditModal } from '../../components/family/FamilyMemberEditModal';

export const FamilyPage: React.FC = () => {
  const [family, setFamily] = useState<Family | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');
  const [editing, setEditing] = useState<FamilyMember | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await familyApi.get();
      setFamily(data);
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true); setInviteError(''); setInviteSuccess('');
    try {
      await familyApi.invite(inviteEmail.trim());
      setInviteSuccess(`${inviteEmail} успешно приглашён!`);
      setInviteEmail('');
      load();
    } catch (e) { setInviteError(getErrorMessage(e)); }
    finally { setInviting(false); }
  };

  const handleRemove = async (memberId: number, name: string) => {
    if (!window.confirm(`Удалить ${name} из семьи?`)) return;
    try {
      await familyApi.removeMember(memberId);
      load();
    } catch (e) { alert(getErrorMessage(e)); }
  };

  const onMemberSaved = () => {
    // перезагружаем семью, чтобы получить обновлённый профиль
    load();
  };

  if (loading) return <PageSpinner />;
  if (error) return (
    <div className="text-center py-16">
      <p className="text-red-600">{error}</p>
      <Button variant="ghost" className="mt-4" onClick={load}>Повторить</Button>
    </div>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-chocolate">Семья</h1>

      {family && (
        <>
          <Card className="p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-tomato/10 flex items-center justify-center text-2xl">👨‍👩‍👧</div>
              <div>
                <h2 className="font-semibold text-chocolate text-lg">{family.name}</h2>
                <p className="text-sm text-gray-500">Глава: {family.owner_name}</p>
              </div>
            </div>

            <h3 className="font-medium text-chocolate mb-3">
              Участники ({family.members.length})
            </h3>
            <div className="space-y-2">
              {family.members.map((m) => (
                <div key={m.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-rice">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-avocado/10 flex items-center justify-center font-semibold text-avocado text-sm">
                      {m.name[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-chocolate">{m.name}</p>
                      <div className="flex items-center gap-2">
                        {m.email && <p className="text-xs text-gray-400">{m.email}</p>}
                        {m.profile?.calorie_target && (
                          <span className="text-xs text-gray-400">
                            · {m.profile.calorie_target} ккал · {m.profile.meal_plan_type ?? '3'} прм
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge color={(m.role === 'head' || m.role === 'owner') ? 'red' : 'gray'}>
                      {(m.role === 'head' || m.role === 'owner') ? 'Глава' : 'Участник'}
                    </Badge>
                    <button
                      onClick={() => setEditing(m)}
                      className="text-xs text-gray-500 hover:text-tomato transition px-2 py-1 rounded hover:bg-white"
                      title="Редактировать"
                    >
                      ✎
                    </button>
                    {(m.role !== 'head' && m.role !== 'owner') && (
                      <button onClick={() => handleRemove(m.id, m.name)}
                        className="text-xs text-red-400 hover:text-red-600 transition">
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Invite */}
          <Card className="p-5">
            <h2 className="font-semibold text-chocolate mb-4">Пригласить участника</h2>
            {inviteSuccess && (
              <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
                {inviteSuccess}
              </div>
            )}
            <form onSubmit={handleInvite} className="flex gap-3">
              <Input
                className="flex-1"
                placeholder="Email участника"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                error={inviteError}
              />
              <Button type="submit" loading={inviting}>Пригласить</Button>
            </form>
          </Card>
        </>
      )}

      {editing && (
        <FamilyMemberEditModal
          member={editing}
          onClose={() => setEditing(null)}
          onSaved={onMemberSaved}
        />
      )}
    </div>
  );
};
TSX_EOF
  echo "  rewrote $FP"
fi
echo

# ── 6. MenuPage.tsx — встраиваем DayNutritionSummary ───────────────────────────
echo "### 6. MenuPage.tsx: встраиваем DayNutritionSummary над каждым днём ###"
MP="$SRC/pages/Menu/MenuPage.tsx"
if grep -q "$MARK_MENU" "$MP"; then
  echo "  уже применено"
else
  bak "$MP"
  python3 <<PYEOF
import re
path = "$MP"
s = open(path, encoding='utf-8').read()

# 6.1. Добавить импорт DayNutritionSummary + NutritionTargets после импорта типов меню
import_anchor = "import { MEAL_LABELS, COMPONENT_ROLE_LABELS, COMPONENT_ROLE_ICONS } from '../../types';"
import_addon = (
    "\nimport type { NutritionTargets } from '../../types'; // $MARK_MENU"
    "\nimport { DayNutritionSummary } from '../../components/menu/DayNutritionSummary';"
)
if import_addon.strip() not in s:
    if import_anchor not in s:
        raise SystemExit("MenuPage import anchor not found")
    s = s.replace(import_anchor, import_anchor + import_addon, 1)

# 6.2. Внутри MenuGrid (props: menu, onRefresh, onDelete) — найти место,
# где идёт цикл по дням и добавить <DayNutritionSummary /> над контентом дня.
#
# Опорная строка из diagnose:
#     const dayItems = (menu.items ?? []).filter(i => i.day_offset === day);
#
# Вставим выше (внутри map'а дней) подгрузку targets из useAppSelector.
# Чтобы targets были доступны — добавим строку в MenuGrid: const targets = ...

# 6.2.a Добавить в начало MenuGrid: получение targets из стора
# Anchor: const MenuGrid: React.FC<MenuGridProps> = ({ menu, onRefresh, onDelete }) => {
mg_anchor = re.search(
    r"(const MenuGrid: React\.FC<MenuGridProps> = \(\{[^)]*\}\) => \{\n)",
    s
)
if not mg_anchor:
    raise SystemExit("MenuGrid component declaration not found")

inject_targets = (
    "  // $MARK_MENU\n"
    "  const userProfile = useAppSelector(state => state.auth.user?.profile);\n"
    "  const targets: NutritionTargets | null = (\n"
    "    userProfile && userProfile.calorie_target\n"
    "      ? {\n"
    "          calorie_target:   userProfile.calorie_target,\n"
    "          protein_target_g: String(userProfile.protein_target_g ?? ''),\n"
    "          fat_target_g:     String(userProfile.fat_target_g ?? ''),\n"
    "          carb_target_g:    String(userProfile.carb_target_g ?? ''),\n"
    "          fiber_target_g:   String(userProfile.fiber_target_g ?? ''),\n"
    "        }\n"
    "      : (userProfile?.targets_calculated ?? null)\n"
    "  );\n"
)

if "$MARK_MENU" not in s:
    s = s[:mg_anchor.end()] + inject_targets + s[mg_anchor.end():]

# 6.2.b Вставить <DayNutritionSummary items={dayItems} targets={targets} /> сразу
# ПОСЛЕ строки "const dayItems = (menu.items ?? []).filter(i => i.day_offset === day);"
day_anchor = "const dayItems = (menu.items ?? []).filter(i => i.day_offset === day);"
if day_anchor not in s:
    raise SystemExit("dayItems anchor not found")

# вставка делается один раз: ищем блок, где сразу за этим идёт return JSX дня
# Чтобы попасть аккуратно — вставим JSX сводки прямо в ту JSX-секцию,
# которая идёт после dayItems. Используем маркер MealCard (упоминание <MealCard) —
# непосредственно перед ним добавим <DayNutritionSummary .../>.
#
# Strategy: внутри блока, где dayItems вычисляются, найти первое появление "<MealCard"
# ПОСЛЕ позиции dayItems и вставить DayNutritionSummary в контейнер ВЫШЕ цикла приёмов.
#
# Из diagnose: после dayItems идёт JSX с <MealCard ... /> (строка 537).
# Найдём строку, начинающуюся с "<MealCard" после dayItems anchor.

di = s.find(day_anchor)
mc_pos = s.find("<MealCard", di)
if mc_pos < 0:
    raise SystemExit("<MealCard usage not found after dayItems")

# Идём назад от mc_pos до начала строки/первого открывающего JSX контейнера —
# вставим DayNutritionSummary прямо ПЕРЕД этим первым <MealCard.
# Найдём начало строки, где он находится (для отступа).
line_start = s.rfind("\n", 0, mc_pos) + 1
indent = ""
i = line_start
while i < mc_pos and s[i] in " \t":
    indent += s[i]
    i += 1

inject_summary = (
    f"{indent}{{/* MG-204: дневная сводка КБЖУ */}}\n"
    f"{indent}<DayNutritionSummary items={{dayItems}} targets={{targets}} />\n"
)

# Если уже есть вставка — пропустим
if "<DayNutritionSummary" not in s:
    s = s[:line_start] + inject_summary + s[line_start:]

open(path, 'w', encoding='utf-8').write(s)
print("  patched MenuPage")
PYEOF
fi
echo

# ── 7. Проверка tsc ────────────────────────────────────────────────────────────
echo "### 7. npx tsc --noEmit ###"
cd "$WEB"
if npx tsc --noEmit 2>&1 | tee /tmp/mg_204_tsc.log; then
  echo
  echo "tsc OK"
else
  echo
  echo "tsc вернул ненулевой код. См. /tmp/mg_204_tsc.log"
fi
echo

echo "=========================================="
echo "MG-204 APPLY DONE  TS=$TS"
echo "=========================================="
echo
echo "Откат:"
echo "  cp $BACKUPS/index.ts.bak_mg204_$TS                       $SRC/types/index.ts"
echo "  cp $BACKUPS/family.ts.bak_mg204_$TS                      $SRC/api/family.ts"
echo "  cp $BACKUPS/FamilyPage.tsx.bak_mg204_$TS                 $SRC/pages/Family/FamilyPage.tsx"
echo "  cp $BACKUPS/MenuPage.tsx.bak_mg204_$TS                   $SRC/pages/Menu/MenuPage.tsx"
echo "  rm -f $SRC/components/family/FamilyMemberEditModal.tsx"
echo "  rm -f $SRC/components/menu/DayNutritionSummary.tsx"
