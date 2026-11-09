// MG_DAYSUM: чтение КБЖУ записи дневника — одно место на весь фронт.
//
// Поле `nutrition` за свою жизнь побывало в трёх видах: число, строка и
// `{value, unit}`. Разбор этого лежал копией в каждом экране, который считал
// суммы, и копии однажды разошлись бы на одной и той же записи — а это
// означает две разные суммы за один день на двух соседних экранах.
import { MEAL_SLOT_ORDER } from '../types';
import type { DiaryEntry, MealSlot } from '../types';

export type MacroKey = 'calories' | 'proteins' | 'fats' | 'carbs';

/** Значение КБЖУ записи с учётом количества порций. */
export const nutriVal = (e: DiaryEntry, key: MacroKey): number => {
  const raw = (e.nutrition as Record<string, unknown> | undefined)?.[key];
  let n = 0;
  if (typeof raw === 'number') n = raw;
  else if (typeof raw === 'string') n = parseFloat(raw.replace(',', '.'));
  else if (raw && typeof raw === 'object' && 'value' in (raw as object)) {
    n = parseFloat(String((raw as { value: unknown }).value).replace(',', '.'));
  }
  return Number.isFinite(n) ? n * (e.quantity ?? 1) : 0;
};

/** MG_MEALSLOT: слот записи. Запасной путь по `meal_type` — для ответа из
 * офлайн-кэша, снятого до того, как слот появился. */
export const slotOf = (e: DiaryEntry): MealSlot =>
  (e.meal_slot ?? (e.meal_type === 'snack' ? 'snack1' : e.meal_type)) as MealSlot;

/** Разделы дня: раскладка человека плюс любой слот, где записи всё-таки есть
 * (на случай недавней смены раскладки). Порядок — по ходу дня. */
export const visibleSlots = (entries: DiaryEntry[], plan: MealSlot[]): MealSlot[] => {
  const used = new Set(entries.map(slotOf));
  return MEAL_SLOT_ORDER.filter((s) => plan.includes(s) || used.has(s));
};
