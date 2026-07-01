// MG_204_V_summary — DIARY_CHART: калораж дня цветной донат-диаграммой (как в mobile).
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

const fmt = (v: number, digits = 0) =>
  digits > 0 ? v.toFixed(digits) : Math.round(v).toString();

// Цвета макросов — как в mobile MenuSummaryCard: У синий, Ж янтарный, Б томат.
const CARB_COLOR = '#5B9BD5';
const FAT_COLOR = '#FBBF24';
const PRO_COLOR = '#F26B5E';

// DIARY_CHART: донат распределения калорий по макросам (SVG, без зависимостей).
const MacroDonut: React.FC<{ carbCal: number; fatCal: number; proCal: number; size?: number }> =
({ carbCal, fatCal, proCal, size = 60 }) => {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const cx = size / 2;
  const cy = size / 2;
  const total = carbCal + fatCal + proCal;
  const segs = [
    { v: carbCal, color: CARB_COLOR },
    { v: fatCal, color: FAT_COLOR },
    { v: proCal, color: PRO_COLOR },
  ];
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90 shrink-0">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E5E7EB" strokeWidth={stroke} />
      {total > 0 && segs.map((s, i) => {
        if (s.v <= 0) return null;
        const len = (s.v / total) * c;
        const el = (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={s.color} strokeWidth={stroke}
            strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} />
        );
        offset += len;
        return el;
      })}
    </svg>
  );
};

const Legend: React.FC<{ color: string; label: string; grams: number }> = ({ color, label, grams }) => (
  <span className="inline-flex items-center gap-1.5 text-xs text-gray-600">
    <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
    {fmt(grams, 1)} г {label}
  </span>
);

export const DayNutritionSummary: React.FC<Props> = ({ items, targets }) => {
  if (!items || items.length === 0) return null;

  const t = sumTotals(items);
  const tgt = targets ?? null;
  const calTarget = numToFloat(tgt?.calorie_target);
  const calPct = calTarget > 0 ? Math.round((t.calories / calTarget) * 100) : null;

  const carbCal = t.carbs * 4;
  const fatCal = t.fats * 9;
  const proCal = t.proteins * 4;

  return (
    <div className="px-3 py-3 bg-rice/40 rounded-xl border border-border">
      <div className="flex items-center gap-4">
        <MacroDonut carbCal={carbCal} fatCal={fatCal} proCal={proCal} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-lg font-bold text-chocolate">{fmt(t.calories)} ккал</span>
            {calTarget > 0 && (
              <span className="text-xs text-gray-400">
                / {fmt(calTarget)} ккал · {calPct}%
              </span>
            )}
            {!tgt && <span className="text-xs text-gray-400">(цели не заданы)</span>}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
            <Legend color={CARB_COLOR} label="У" grams={t.carbs} />
            <Legend color={FAT_COLOR} label="Ж" grams={t.fats} />
            <Legend color={PRO_COLOR} label="Б" grams={t.proteins} />
            {t.fiber > 0 && (
              <span className="inline-flex items-center gap-1.5 text-xs text-gray-500">
                Клетчатка {fmt(t.fiber, 1)} г
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
