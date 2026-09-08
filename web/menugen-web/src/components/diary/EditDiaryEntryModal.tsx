// MG_DIARYEDIT: правка записи дневника.
//
// В вебе правки не было вовсе: запись можно было только удалить и завести
// заново, набрав всё руками. Меняются все поля, которые у записи есть, — приём,
// название, вес, число порций и КБЖУ.
//
// Название у записи из рецепта не редактируется: оно берётся из самого рецепта,
// и своя надпись поверх него означала бы, что в дневнике одно, а в карточке
// рецепта другое.
import React, { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { diaryApi } from '../../api/diary';
import { getErrorMessage } from '../../utils/api';
import { MEAL_SLOT_LABELS, MEAL_SLOT_ORDER } from '../../types';
import type { DiaryEntry, MealSlot } from '../../types';

interface Props {
  entry: DiaryEntry;
  onClose: () => void;
  onSaved: () => void;
}

// Число из string | number | {value} | null — КБЖУ приходит в разных видах.
const toNum = (v: unknown): number => {
  if (v == null) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  if (typeof v === 'string') {
    const n = parseFloat(v.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  }
  if (typeof v === 'object' && 'value' in (v as Record<string, unknown>)) {
    return toNum((v as { value: unknown }).value);
  }
  return 0;
};

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10));

export const EditDiaryEntryModal: React.FC<Props> = ({ entry, onClose, onSaved }) => {
  const nutrition = entry.nutrition as Record<string, unknown> | undefined;
  const isRecipe = entry.recipe != null;

  const [slot, setSlot] = useState<MealSlot>(
    (entry.meal_slot ?? (entry.meal_type === 'snack' ? 'snack1' : entry.meal_type)) as MealSlot);
  const [name, setName] = useState(entry.recipe_title ?? entry.custom_name ?? '');
  const [quantity, setQuantity] = useState(fmt(entry.quantity ?? 1));
  const [grams, setGrams] = useState(entry.grams == null ? '' : String(entry.grams));
  const [cal, setCal] = useState(fmt(toNum(nutrition?.calories)));
  const [prot, setProt] = useState(fmt(toNum(nutrition?.proteins)));
  const [fat, setFat] = useState(fmt(toNum(nutrition?.fats)));
  const [carb, setCarb] = useState(fmt(toNum(nutrition?.carbs)));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Вес, с которым запись открыли: от него считается пересчёт, поэтому он
  // берётся из самой записи и не меняется, пока окно открыто. Иначе двойное
  // нажатие «Пересчитать» умножало бы дважды.
  const gramsAtOpen = entry.grams ?? null;

  const num = (v: string) => {
    const n = parseFloat(v.replace(',', '.'));
    return Number.isFinite(n) ? n : NaN;
  };

  // MG_DIARYGRAMS: пересчитать КБЖУ под новый вес.
  //
  // По кнопке, а не молча при вводе: человек может править и вес, и цифры
  // руками, и незаметный пересчёт затирал бы только что введённое.
  const rescale = () => {
    const to = num(grams);
    if (!gramsAtOpen || gramsAtOpen <= 0 || !Number.isFinite(to) || to <= 0) return;
    const k = to / gramsAtOpen;
    setCal(fmt(Math.round(toNum(nutrition?.calories) * k)));
    setProt(fmt(Math.round(toNum(nutrition?.proteins) * k * 10) / 10));
    setFat(fmt(Math.round(toNum(nutrition?.fats) * k * 10) / 10));
    setCarb(fmt(Math.round(toNum(nutrition?.carbs) * k * 10) / 10));
    // Название вида «Творог, 120 г» тоже про вес — иначе оно начнёт врать.
    setName((prev) => prev.replace(/,\s*\d+(?:[.,]\d+)?\s*г\s*$/, `, ${Math.round(to)} г`));
    setError('');
  };

  const save = async () => {
    if (!isRecipe && !name.trim()) { setError('Укажите название'); return; }
    const q = num(quantity);
    if (!Number.isFinite(q) || q <= 0) { setError('Количество порций должно быть больше 0'); return; }
    const g = grams.trim() ? num(grams) : null;
    if (g !== null && (!Number.isFinite(g) || g <= 0)) { setError('Вес должен быть больше 0'); return; }

    setSaving(true); setError('');
    try {
      await diaryApi.patch(entry.id, {
        meal_slot: slot,
        quantity: q,
        grams: g === null ? null : Math.round(g),
        nutrition: {
          calories: { value: String(Math.round(num(cal) || 0)), unit: 'ккал' },
          proteins: { value: String(num(prot) || 0), unit: 'г' },
          fats: { value: String(num(fat) || 0), unit: 'г' },
          carbs: { value: String(num(carb) || 0), unit: 'г' },
        },
        // Имя правим только у ручной записи — см. шапку файла.
        ...(isRecipe ? {} : { custom_name: name.trim() }),
      });
      onSaved();
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
      <Card className="w-full max-w-md p-5 max-h-[90vh] overflow-y-auto"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="font-semibold text-chocolate mb-4">Изменить запись</h2>

        <label className="block text-xs text-gray-500 mb-1">Приём пищи</label>
        <div className="flex flex-wrap gap-2 mb-4">
          {MEAL_SLOT_ORDER.map((s) => (
            <button key={s} type="button" onClick={() => setSlot(s)}
              className={`px-3 py-1.5 rounded-xl text-sm transition ${
                slot === s ? 'bg-tomato text-white' : 'bg-rice text-chocolate'
              }`}>
              {MEAL_SLOT_LABELS[s]}
            </button>
          ))}
        </div>

        <label className="block text-xs text-gray-500 mb-1">Название</label>
        <Input value={name} disabled={isRecipe}
               onChange={(e) => setName(e.target.value)} className="mb-1" />
        {isRecipe && (
          <p className="text-xs text-gray-400 mb-3">
            Название берётся из рецепта и здесь не меняется.
          </p>
        )}

        <div className="grid grid-cols-2 gap-3 mt-3 mb-1">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Вес порции (г)</label>
            <Input value={grams} inputMode="decimal"
                   onChange={(e) => setGrams(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Количество порций</label>
            <Input value={quantity} inputMode="decimal"
                   onChange={(e) => setQuantity(e.target.value)} />
          </div>
        </div>
        {gramsAtOpen ? (
          <button type="button" onClick={rescale}
                  className="text-xs text-avocado hover:underline mb-3">
            Пересчитать КБЖУ под новый вес
          </button>
        ) : (
          <p className="text-xs text-gray-400 mb-3">
            У этой записи вес не сохранён — впишите его, а КБЖУ поправьте вручную.
          </p>
        )}

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Калории (ккал)</label>
            <Input value={cal} inputMode="decimal" onChange={(e) => setCal(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Белки (г)</label>
            <Input value={prot} inputMode="decimal" onChange={(e) => setProt(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Жиры (г)</label>
            <Input value={fat} inputMode="decimal" onChange={(e) => setFat(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Углеводы (г)</label>
            <Input value={carb} inputMode="decimal" onChange={(e) => setCarb(e.target.value)} />
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={save} loading={saving}>Сохранить</Button>
        </div>
      </Card>
    </div>
  );
};
