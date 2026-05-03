import React, { useEffect, useMemo, useState } from 'react';
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { setUser } from '../../store/slices/authSlice';
import { authApi } from '../../api/auth';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { getErrorMessage } from '../../utils/api';
import type { MealPlan, NutritionTargets, UserProfile } from '../../types';

const MEAL_PLAN_OPTIONS: { value: MealPlan; label: string; hint: string }[] = [
  { value: '3', label: '3 приёма', hint: 'завтрак / обед / ужин' },
  { value: '5', label: '5 приёмов', hint: '+ перекусы между ними' },
];

const num = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(0);
};

interface MacroPillProps {
  label: string;
  value: string;
  unit: string;
  color: string;
}
const MacroPill: React.FC<MacroPillProps> = ({ label, value, unit, color }) => (
  <div className={`flex flex-col items-center justify-center px-3 py-2 rounded-xl ${color}`}>
    <span className="text-xs uppercase tracking-wide opacity-70">{label}</span>
    <span className="text-lg font-bold">{value}</span>
    <span className="text-[10px] opacity-60">{unit}</span>
  </div>
);

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

          {/* meal_plan_type — план приёмов пищи */}
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

      {/* Целевые КБЖУ */}
      <Card className="p-6">
        <h2 className="text-lg font-bold text-chocolate mb-1">Целевые КБЖУ</h2>
        <p className="text-xs text-gray-500 mb-4">
          Рассчитываются автоматически по формуле Mifflin-St Jeor на основе ваших параметров.
        </p>

        {!profileFilled && (
          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-yellow-800 text-sm">
            Заполните рост, вес и год рождения в Django Admin — после этого появятся целевые КБЖУ.
          </div>
        )}

        {profileFilled && targets && (
          <div className="grid grid-cols-5 gap-2">
            <MacroPill label="Ккал"  value={num(targets.calorie_target)}    unit="ккал" color="bg-tomato/10 text-tomato" />
            <MacroPill label="Белок" value={num(targets.protein_target_g)}  unit="г"    color="bg-blue-50 text-blue-700" />
            <MacroPill label="Жиры"  value={num(targets.fat_target_g)}      unit="г"    color="bg-amber-50 text-amber-700" />
            <MacroPill label="Углев" value={num(targets.carb_target_g)}     unit="г"    color="bg-emerald-50 text-emerald-700" />
            <MacroPill label="Клетч" value={num(targets.fiber_target_g)}    unit="г"    color="bg-purple-50 text-purple-700" />
          </div>
        )}

        {profileFilled && !targets && (
          <p className="text-sm text-gray-500">Не удалось рассчитать цели — проверьте параметры профиля.</p>
        )}
      </Card>
    </div>
  );
};
