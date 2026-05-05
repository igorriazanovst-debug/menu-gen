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
