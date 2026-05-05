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
