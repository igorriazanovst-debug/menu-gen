#!/bin/bash
# /opt/menugen/web/scripts/mg_205ui_apply_web.sh
# MG-205-UI этап C (web): types + api + TargetField + ProfilePage + FamilyMemberEditModal.
set -euo pipefail

ROOT=/opt/menugen
WEB=$ROOT/web/menugen-web
SRC=$WEB/src
TS=$(date +%Y%m%d_%H%M%S)
BAK=$ROOT/backups
mkdir -p "$BAK"

TYPES=$SRC/types/index.ts
API_FAMILY=$SRC/api/family.ts
API_USERS=$SRC/api/users.ts
PROFILE_PAGE=$SRC/pages/Profile/ProfilePage.tsx
FAMILY_MODAL=$SRC/components/family/FamilyMemberEditModal.tsx
TARGETFIELD=$SRC/components/profile/TargetField.tsx

echo "=== MG-205-UI web @ $TS ==="

# ─────── 1) Бэкапы ───────
echo "[1/6] Backups..."
cp "$TYPES"        "$BAK/web_types_index.ts.bak_mg205ui_${TS}"
cp "$API_FAMILY"   "$BAK/web_api_family.ts.bak_mg205ui_${TS}"
[ -f "$API_USERS" ] && cp "$API_USERS" "$BAK/web_api_users.ts.bak_mg205ui_${TS}" || true
cp "$PROFILE_PAGE" "$BAK/web_ProfilePage.tsx.bak_mg205ui_${TS}"
cp "$FAMILY_MODAL" "$BAK/web_FamilyMemberEditModal.tsx.bak_mg205ui_${TS}"

# ─────── 2) types/index.ts ───────
echo "[2/6] Patch types/index.ts..."
python3 <<PYEOF
from pathlib import Path
p = Path("$TYPES")
src = p.read_text()
if "MG_205UI_V_types" in src:
    print("  already patched"); raise SystemExit(0)

inject = """
// MG_205UI_V_types = 1
export type TargetSource = 'auto' | 'user' | 'specialist';

export interface TargetMeta {
  source: TargetSource;
  by_user: { id: number; name: string } | null;
  at: string | null;
}

export type TargetField =
  | 'calorie_target'
  | 'protein_target_g'
  | 'fat_target_g'
  | 'carb_target_g'
  | 'fiber_target_g';

export type TargetsMeta = Partial<Record<TargetField, TargetMeta>>;

export interface TargetAuditEntry {
  id: number;
  field: TargetField;
  source: TargetSource;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  at: string;
  by_user: { id: number; name: string } | null;
}
"""

# Добавляем targets_meta в UserProfile (если не добавлено)
import re
if "targets_meta?:" not in src:
    src = re.sub(
        r"(targets_calculated\?\: NutritionTargets \| null;)",
        r"\1\n  targets_meta?: TargetsMeta;",
        src,
        count=1,
    )

# Inject types в начало файла (после первой строки)
src = src.rstrip() + "\n" + inject + "\n"
p.write_text(src)
print("  patched ✓")
PYEOF

# ─────── 3) api/users.ts (новый) + расширение api/family.ts ───────
echo "[3/6] Create api/users.ts..."
cat > "$API_USERS" <<'TS_EOF'
// MG_205UI_V_api_users = 1
import client from './client';
import type { TargetField, TargetAuditEntry, User } from '../types';

export const usersApi = {
  getTargetHistory: (field: TargetField) =>
    client.get<TargetAuditEntry[]>(`/users/me/targets/${field}/history/`),

  resetTarget: (field: TargetField) =>
    client.post<User>(`/users/me/targets/${field}/reset/`),
};
TS_EOF

echo "[3/6] Patch api/family.ts..."
python3 <<PYEOF
from pathlib import Path
import re
p = Path("$API_FAMILY")
src = p.read_text()
if "MG_205UI_V_api_family" in src:
    print("  already patched"); raise SystemExit(0)

# Добавим импорт TargetField, TargetAuditEntry если отсутствует
if "TargetAuditEntry" not in src:
    src = re.sub(
        r"import type \{ Family, FamilyMember, UserProfile \} from '\.\./types';",
        "import type { Family, FamilyMember, UserProfile, TargetField, TargetAuditEntry } from '../types';",
        src,
        count=1,
    )

# Добавим методы в объект familyApi (перед закрывающей }
addition = """
  // MG_205UI_V_api_family = 1
  getMemberTargetHistory: (memberId: number, field: TargetField) =>
    client.get<TargetAuditEntry[]>(\`/family/members/\${memberId}/targets/\${field}/history/\`),
  resetMemberTarget: (memberId: number, field: TargetField) =>
    client.post<FamilyMember>(\`/family/members/\${memberId}/targets/\${field}/reset/\`),
"""
src = re.sub(
    r"(updateMember:.*?\),\s*\n)(\};)",
    r"\1" + addition + r"\2",
    src,
    count=1,
    flags=re.DOTALL,
)
p.write_text(src)
print("  patched ✓")
PYEOF

# ─────── 4) Component TargetField.tsx ───────
echo "[4/6] Create components/profile/TargetField.tsx..."
mkdir -p "$(dirname $TARGETFIELD)"
cat > "$TARGETFIELD" <<'TSX_EOF'
// MG_205UI_V_target_field = 1
import React, { useState, useEffect, useCallback } from 'react';
import type { TargetField as TF, TargetMeta, TargetAuditEntry } from '../../types';

interface Props {
  label: string;          // "Ккал", "Белок"…
  unit: string;           // "ккал", "г"
  value: string | number | null | undefined;
  field: TF;              // 'calorie_target' и т.д.
  meta?: TargetMeta;      // последняя запись аудита
  bgClass: string;        // напр. 'bg-tomato/10 text-tomato'
  /**
   * Источник истории: либо текущий пользователь (`{kind:'me'}`),
   * либо член семьи (`{kind:'member', memberId, getHistory, onReset}`).
   * Это позволяет переиспользовать компонент в Profile и в Family.
   */
  loader: TargetLoader;
  /** Колбэк после успешного reset — родитель должен перезагрузить data. */
  onResetDone?: () => void;
  /** true если у пользователя нет прав на reset (read-only режим). */
  readOnly?: boolean;
}

export type TargetLoader = {
  getHistory: (field: TF) => Promise<TargetAuditEntry[]>;
  reset: (field: TF) => Promise<void>;
};

const formatNum = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isNaN(n) ? '—' : n.toFixed(0);
};

const sourceBadge: Record<string, { label: string; cls: string }> = {
  auto:       { label: 'auto',     cls: 'bg-gray-100  text-gray-600  border-gray-200' },
  user:       { label: 'вручную',  cls: 'bg-blue-100  text-blue-700  border-blue-200' },
  specialist: { label: 'специалист', cls: 'bg-purple-100 text-purple-700 border-purple-200' },
};

const formatDate = (iso?: string | null) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return iso; }
};

export const TargetField: React.FC<Props> = ({
  label, unit, value, field, meta, bgClass, loader, onResetDone, readOnly,
}) => {
  const [open, setOpen] = useState(false);
  const [hist, setHist] = useState<TargetAuditEntry[] | null>(null);
  const [loadErr, setLoadErr] = useState<string>('');
  const [resetting, setResetting] = useState(false);

  const src = meta?.source ?? 'auto';
  const badge = sourceBadge[src] ?? sourceBadge.auto;

  const loadHistory = useCallback(async () => {
    setLoadErr(''); setHist(null);
    try {
      const arr = await loader.getHistory(field);
      setHist(arr);
    } catch (e: any) {
      setLoadErr(e?.message ?? 'Не удалось загрузить историю');
    }
  }, [loader, field]);

  useEffect(() => {
    if (open && hist === null) loadHistory();
  }, [open, hist, loadHistory]);

  const handleReset = async () => {
    setResetting(true);
    try {
      await loader.reset(field);
      onResetDone?.();
      setHist(null);  // история обновится при следующем открытии
    } catch (e) { /* ignore */ }
    finally { setResetting(false); }
  };

  return (
    <div className={`relative px-3 py-2 rounded-xl ${bgClass} border border-transparent`}>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] uppercase tracking-wide opacity-70">{label}</span>
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className={`text-[9px] uppercase font-medium px-1.5 py-0.5 rounded border ${badge.cls} hover:opacity-80 transition`}
          title="Источник правки. Нажмите для истории"
        >
          {badge.label}
        </button>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-lg font-bold leading-none">{formatNum(value)}</span>
        <span className="text-[10px] opacity-60">{unit}</span>
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 bg-white rounded-xl border border-gray-200 shadow-lg p-3 text-xs text-chocolate min-w-[220px]">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold">{label} — история</span>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-700">✕</button>
          </div>

          {loadErr && <div className="text-red-600 mb-2">{loadErr}</div>}
          {hist === null && !loadErr && <div className="text-gray-400">Загрузка…</div>}
          {hist && hist.length === 0 && <div className="text-gray-400">Записей нет</div>}

          {hist && hist.length > 0 && (
            <ul className="space-y-1.5 max-h-56 overflow-y-auto">
              {hist.map(e => (
                <li key={e.id} className="flex items-start gap-2">
                  <span className={`mt-0.5 px-1.5 py-0.5 rounded border text-[9px] uppercase ${(sourceBadge[e.source] ?? sourceBadge.auto).cls}`}>
                    {(sourceBadge[e.source] ?? sourceBadge.auto).label}
                  </span>
                  <div className="flex-1">
                    <div className="text-gray-900">
                      {e.old_value ?? '—'} → <strong>{e.new_value ?? '—'}</strong>
                    </div>
                    <div className="text-gray-400">
                      {formatDate(e.at)}
                      {e.by_user && <> · {e.by_user.name}</>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {!readOnly && src !== 'auto' && (
            <button
              type="button"
              onClick={handleReset}
              disabled={resetting}
              className="mt-3 w-full text-xs px-3 py-2 rounded-lg bg-tomato text-white hover:bg-tomato/90 disabled:opacity-50"
            >
              {resetting ? 'Сброс…' : 'Сбросить к авто'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
TSX_EOF
echo "  created ✓"

# ─────── 5) ProfilePage.tsx — заменить локальный MacroPill на TargetField ───────
echo "[5/6] Patch pages/Profile/ProfilePage.tsx..."
cat > "$PROFILE_PAGE" <<'TSX_EOF'
// MG_205UI_V_profile_page = 1
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { setUser } from '../../store/slices/authSlice';
import { authApi } from '../../api/auth';
import { usersApi } from '../../api/users';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { TargetField, type TargetLoader } from '../../components/profile/TargetField';
import { getErrorMessage } from '../../utils/api';
import type { MealPlan, NutritionTargets, UserProfile, TargetField as TF, TargetsMeta } from '../../types';

const MEAL_PLAN_OPTIONS: { value: MealPlan; label: string; hint: string }[] = [
  { value: '3', label: '3 приёма', hint: 'завтрак / обед / ужин' },
  { value: '5', label: '5 приёмов', hint: '+ перекусы между ними' },
];

export const ProfilePage: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);

  const [name, setName]   = useState(user?.name ?? '');
  const [mealPlan, setMealPlan] = useState<MealPlan>(user?.profile?.meal_plan_type ?? '3');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError]     = useState('');

  useEffect(() => {
    setName(user?.name ?? '');
    setMealPlan(user?.profile?.meal_plan_type ?? '3');
  }, [user?.id, user?.name, user?.profile?.meal_plan_type]);

  const targets: NutritionTargets | null = useMemo(() => {
    const p = user?.profile;
    if (!p) return null;
    if (p.calorie_target && p.protein_target_g) {
      return {
        calorie_target:   p.calorie_target,
        protein_target_g: String(p.protein_target_g),
        fat_target_g:     String(p.fat_target_g ?? ''),
        carb_target_g:    String(p.carb_target_g ?? ''),
        fiber_target_g:   String(p.fiber_target_g ?? ''),
      };
    }
    return p.targets_calculated ?? null;
  }, [user?.profile]);

  const meta: TargetsMeta = user?.profile?.targets_meta ?? {};

  const profileFilled = !!(user?.profile?.birth_year && user?.profile?.height_cm && user?.profile?.weight_kg);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setSuccess(''); setError('');
    try {
      const payload: Partial<UserProfile> = { meal_plan_type: mealPlan };
      const { data } = await authApi.updateMe({ name, profile: payload });
      dispatch(setUser(data));
      setSuccess('Профиль обновлён!');
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setSaving(false); }
  };

  const reloadMe = useCallback(async () => {
    try {
      const { data } = await authApi.me();
      dispatch(setUser(data));
    } catch { /* ignore */ }
  }, [dispatch]);

  // TargetLoader для текущего пользователя
  const meLoader: TargetLoader = useMemo(() => ({
    getHistory: async (f: TF) => (await usersApi.getTargetHistory(f)).data,
    reset:      async (f: TF) => { await usersApi.resetTarget(f); await reloadMe(); },
  }), [reloadMe]);

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold text-chocolate">Профиль</h1>

      <Card className="p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-tomato/10 flex items-center justify-center text-3xl font-bold text-tomato">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div>
            <p className="font-semibold text-chocolate text-lg">{user?.name}</p>
            <p className="text-sm text-gray-500">{user?.email ?? user?.phone}</p>
          </div>
        </div>

        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <Input label="Имя" value={name} onChange={(e) => setName(e.target.value)} error={error} />
          <Input label="Email" value={user?.email ?? ''} disabled />

          <div>
            <label className="block text-sm font-medium text-chocolate mb-2">
              План приёмов пищи
            </label>
            <div className="grid grid-cols-2 gap-2">
              {MEAL_PLAN_OPTIONS.map((opt) => {
                const active = mealPlan === opt.value;
                return (
                  <button
                    type="button"
                    key={opt.value}
                    onClick={() => setMealPlan(opt.value)}
                    className={
                      'p-3 rounded-xl border text-left transition ' +
                      (active
                        ? 'border-tomato bg-tomato/10 text-chocolate'
                        : 'border-gray-200 bg-white hover:border-tomato/50 text-gray-700')
                    }
                  >
                    <div className="font-semibold">{opt.label}</div>
                    <div className="text-xs opacity-70">{opt.hint}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <Button type="submit" loading={saving}>Сохранить</Button>
        </form>
      </Card>

      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-1">Целевые КБЖУ</h2>
        <p className="text-xs text-gray-500 mb-4">
          Бейдж показывает источник правки: <span className="font-medium">auto</span> — рассчитано формулой,
          {' '}<span className="font-medium">вручную</span> — вы изменили сами,
          {' '}<span className="font-medium">специалист</span> — поставил ваш диетолог.
          Нажмите на бейдж, чтобы увидеть историю и сбросить к авто.
        </p>

        {!profileFilled && (
          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-yellow-800 text-sm">
            Заполните рост, вес и год рождения в Django Admin — после этого появятся целевые КБЖУ.
          </div>
        )}

        {profileFilled && targets && (
          <div className="grid grid-cols-5 gap-2">
            <TargetField label="Ккал"  unit="ккал" value={targets.calorie_target}    field="calorie_target"    meta={meta.calorie_target}    bgClass="bg-tomato/10 text-tomato"           loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Белок" unit="г"    value={targets.protein_target_g}  field="protein_target_g"  meta={meta.protein_target_g}  bgClass="bg-blue-50 text-blue-700"           loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Жиры"  unit="г"    value={targets.fat_target_g}      field="fat_target_g"      meta={meta.fat_target_g}      bgClass="bg-amber-50 text-amber-700"         loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Углев" unit="г"    value={targets.carb_target_g}     field="carb_target_g"     meta={meta.carb_target_g}     bgClass="bg-emerald-50 text-emerald-700"     loader={meLoader} onResetDone={reloadMe} />
            <TargetField label="Клетч" unit="г"    value={targets.fiber_target_g}    field="fiber_target_g"    meta={meta.fiber_target_g}    bgClass="bg-purple-50 text-purple-700"       loader={meLoader} onResetDone={reloadMe} />
          </div>
        )}

        {profileFilled && !targets && (
          <p className="text-sm text-gray-500">Не удалось рассчитать цели — проверьте параметры профиля.</p>
        )}
      </Card>
    </div>
  );
};
TSX_EOF
echo "  written ✓"

# ─────── 6) FamilyMemberEditModal.tsx — заменить локальный MacroPill на TargetField ───────
echo "[6/6] Patch FamilyMemberEditModal.tsx..."
cat > "$FAMILY_MODAL" <<'TSX_EOF'
// MG_205UI_V_family_modal = 1
import React, { useState, useMemo, useCallback } from 'react';
import type { FamilyMember, MealPlan, TargetField as TF, TargetsMeta } from '../../types';
import { familyApi } from '../../api/family';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { TargetField, type TargetLoader } from '../profile/TargetField';
import { getErrorMessage } from '../../utils/api';

interface Props {
  member: FamilyMember;
  onClose: () => void;
  onSaved: (updated: FamilyMember) => void;
}

export const FamilyMemberEditModal: React.FC<Props> = ({
  member, onClose, onSaved,
}) => {
  const [name, setName] = useState(member.name);
  const [mealPlan, setMealPlan] = useState<MealPlan>(
    (member.profile?.meal_plan_type as MealPlan) ?? '3'
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [currentMember, setCurrentMember] = useState<FamilyMember>(member);

  const profile = currentMember.profile;
  const meta: TargetsMeta = profile?.targets_meta ?? {};

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

  const memberLoader: TargetLoader = useMemo(() => ({
    getHistory: async (f: TF) => (await familyApi.getMemberTargetHistory(member.id, f)).data,
    reset:      async (f: TF) => {
      const { data } = await familyApi.resetMemberTarget(member.id, f);
      setCurrentMember(data);
      onSaved(data);
    },
  }), [member.id, onSaved]);

  const reloadFromParent = useCallback(() => {
    // меняем целиком в родителе через onSaved (см. FamilyPage.onMemberSaved → load())
    // здесь ничего; reload произошёл внутри memberLoader.reset
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div className="w-full max-w-lg my-8" onClick={(e) => e.stopPropagation()}>
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-chocolate">
              Редактировать: {currentMember.name}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            >
              ✕
            </button>
          </div>

          <div>
            <label className="block text-sm text-gray-600 mb-1">Имя</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Имя участника"
            />
          </div>

          {profile && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Дневные цели
                <span className="ml-2 text-xs text-gray-400">бейдж = источник; нажмите для истории</span>
              </label>
              <div className="grid grid-cols-5 gap-2">
                <TargetField label="Ккал"  unit="ккал" value={profile.calorie_target}    field="calorie_target"    meta={meta.calorie_target}    bgClass="bg-tomato/10 text-tomato"       loader={memberLoader} onResetDone={reloadFromParent} />
                <TargetField label="Белок" unit="г"    value={profile.protein_target_g}  field="protein_target_g"  meta={meta.protein_target_g}  bgClass="bg-blue-50 text-blue-700"       loader={memberLoader} onResetDone={reloadFromParent} />
                <TargetField label="Жиры"  unit="г"    value={profile.fat_target_g}      field="fat_target_g"      meta={meta.fat_target_g}      bgClass="bg-amber-50 text-amber-700"     loader={memberLoader} onResetDone={reloadFromParent} />
                <TargetField label="Углев" unit="г"    value={profile.carb_target_g}     field="carb_target_g"     meta={meta.carb_target_g}     bgClass="bg-emerald-50 text-emerald-700" loader={memberLoader} onResetDone={reloadFromParent} />
                <TargetField label="Клетч" unit="г"    value={profile.fiber_target_g}    field="fiber_target_g"    meta={meta.fiber_target_g}    bgClass="bg-purple-50 text-purple-700"   loader={memberLoader} onResetDone={reloadFromParent} />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Изменения сохраняются автоматически; история показывает кто и когда менял.
              </p>
            </div>
          )}

          <div>
            <label className="block text-sm text-gray-600 mb-2">Приёмов пищи в день</label>
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
            <Button variant="ghost" onClick={onClose} disabled={saving}>Отмена</Button>
            <Button onClick={handleSave} loading={saving}>Сохранить</Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
TSX_EOF
echo "  written ✓"

# ─────── 7) Verify ───────
echo ""
echo "── markers ──"
grep -nE "MG_205UI_V_" \
  $TYPES \
  $API_USERS \
  $API_FAMILY \
  $TARGETFIELD \
  $PROFILE_PAGE \
  $FAMILY_MODAL 2>/dev/null

echo ""
echo "── TypeScript check ──"
cd $WEB
if [ -f node_modules/.bin/tsc ]; then
  ./node_modules/.bin/tsc --noEmit 2>&1 | head -40 || true
else
  echo "  tsc not installed locally; skipping (build will catch errors)"
fi

echo ""
echo "=== DONE @ $TS ==="
echo "Backups in $BAK/*_mg205ui_${TS}*"
