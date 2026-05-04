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
