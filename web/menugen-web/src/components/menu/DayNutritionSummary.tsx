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
