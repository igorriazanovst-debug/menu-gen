// DIARY_V2
import React, { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { diaryApi } from '../../api/diary';
import { getErrorMessage } from '../../utils/api';
import { MEAL_LABELS } from '../../types';
import type { MealType } from '../../types';

interface Props {
  date: string;
  memberId?: number;
  onClose: () => void;
  onAdded: () => void;
}

const MEALS: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack'];

export const AddDiaryEntryModal: React.FC<Props> = ({ date, memberId, onClose, onAdded }) => {
  const [mealType, setMealType] = useState<MealType>('breakfast');
  const [name, setName] = useState('');
  const [qty, setQty] = useState('1');
  const [cal, setCal] = useState('');
  const [prot, setProt] = useState('');
  const [fat, setFat] = useState('');
  const [carb, setCarb] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const num = (v: string) => {
    const n = parseFloat(v.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  };

  const save = async () => {
    if (!name.trim()) { setError('Укажите название блюда'); return; }
    setSaving(true); setError('');
    const nutrition: Record<string, { value: string; unit: string }> = {};
    if (cal) nutrition.calories = { value: String(num(cal)), unit: 'ккал' };
    if (prot) nutrition.proteins = { value: String(num(prot)), unit: 'г' };
    if (fat) nutrition.fats = { value: String(num(fat)), unit: 'г' };
    if (carb) nutrition.carbs = { value: String(num(carb)), unit: 'г' };
    try {
      await diaryApi.create({
        date,
        meal_type: mealType,
        custom_name: name.trim(),
        quantity: num(qty) || 1,
        is_eaten: true,
        nutrition: Object.keys(nutrition).length ? nutrition : undefined,
      }, memberId);
      onAdded();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
         onClick={onClose}>
      <Card className="w-full max-w-md p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-4">Добавить вручную</h2>

        <label className="block text-xs text-gray-500 mb-1">Приём пищи</label>
        <div className="flex flex-wrap gap-2 mb-4">
          {MEALS.map((m) => (
            <button key={m} type="button" onClick={() => setMealType(m)}
              className={`px-3 py-1.5 rounded-xl text-sm transition ${
                mealType === m ? 'bg-tomato text-white' : 'bg-rice text-chocolate'
              }`}>
              {MEAL_LABELS[m]}
            </button>
          ))}
        </div>

        <label className="block text-xs text-gray-500 mb-1">Название</label>
        <Input value={name} onChange={(e) => setName(e.target.value)}
               placeholder="Например, Овсянка с бананом" className="mb-4" />

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Количество (порций)</label>
            <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} min="0" step="0.5" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Калории (ккал)</label>
            <Input type="number" value={cal} onChange={(e) => setCal(e.target.value)} min="0" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Белки (г)</label>
            <Input type="number" value={prot} onChange={(e) => setProt(e.target.value)} min="0" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Жиры (г)</label>
            <Input type="number" value={fat} onChange={(e) => setFat(e.target.value)} min="0" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Углеводы (г)</label>
            <Input type="number" value={carb} onChange={(e) => setCarb(e.target.value)} min="0" />
          </div>
        </div>

        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Отмена</Button>
          <Button onClick={save} disabled={saving}>{saving ? 'Сохранение…' : 'Добавить'}</Button>
        </div>
      </Card>
    </div>
  );
};
