// MG_SCANSRC: строка КБЖУ для показа при скане штрих-кода.
//
// Цифры приходили в ответе и раньше, но нигде не показывались: товар молча
// подставлялся по имени, а его КБЖУ всплывало потом — уже в расчётах меню и
// дневника. Увидеть их удобнее в тот момент, когда сканируешь упаковку и
// можешь сверить с этикеткой.
import type { Product } from '../types';

const num = (v: string | number | null | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : parseFloat(String(v));
  return Number.isFinite(n) ? n : null;
};

const round = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** «120 ккал · Б 5 · Ж 3.2 · У 12 (на 100 г)» либо null, если данных нет. */
export const productKbjuLine = (p: Product | null | undefined): string | null => {
  if (!p) return null;
  const parts: string[] = [];
  const cals = num(p.calories_per_100g);
  if (cals !== null) parts.push(`${round(cals)} ккал`);
  const n = p.nutrition ?? {};
  for (const [key, label] of [
    ['proteins', 'Б'],
    ['fats', 'Ж'],
    ['carbs', 'У'],
  ] as const) {
    const v = num(n[key]);
    if (v !== null) parts.push(`${label} ${round(v)}`);
  }
  if (parts.length === 0) return null;
  return `${parts.join(' · ')} (на 100 г)`;
};
