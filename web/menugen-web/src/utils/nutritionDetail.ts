// MG_NUTRIDETAIL: сколько чисел показывать в строках еды.
//
// Настройка отображения, а не данных: числа у записи те же, меняется только
// то, что из них видно. Живёт в аккаунте (Profile.nutrition_detail), поэтому
// одна и та же в вебе и в приложении — иначе один и тот же дневник выглядел
// бы в браузере и на телефоне по-разному, и настройка превратилась бы в две.
import type { UserProfile } from '../types';

export type NutritionDetail = 'short' | 'normal' | 'detailed';

export const NUTRITION_DETAIL_OPTIONS: { value: NutritionDetail; label: string; hint: string }[] = [
  { value: 'short', label: 'Кратко', hint: 'Только калории' },
  { value: 'normal', label: 'Обычно', hint: 'Калории и БЖУ' },
  { value: 'detailed', label: 'Подробно', hint: 'Калории, БЖУ и вес порции' },
];

/** Выбор человека. Незнакомое значение — умолчание, а не пустой экран:
 *  сервер может оказаться новее фронта. */
export const detailOf = (profile?: UserProfile | null): NutritionDetail => {
  const raw = profile?.nutrition_detail;
  return raw === 'short' || raw === 'detailed' ? raw : 'normal';
};

export const showsMacros = (d: NutritionDetail): boolean => d !== 'short';
export const showsGrams = (d: NutritionDetail): boolean => d === 'detailed';

/** «Б 12 · Ж 8 · У 30 г» — буквами, а не словами.
 *
 * В заголовке приёма стоят полные слова, и это правильно: там есть место и
 * там же расшифровка. В строке записи полные слова не помещаются рядом с
 * названием блюда и обрезаются — то есть пропадает то, ради чего их
 * показывают.
 *
 * Пусто — когда чисел нет вовсе: «Б 0 · Ж 0 · У 0 г» это не данные, а шум. */
export const macrosShort = (proteins: number, fats: number, carbs: number): string => {
  if (proteins <= 0 && fats <= 0 && carbs <= 0) return '';
  const n = (v: number): string => {
    if (v <= 0) return '0';
    // Доли грамма — только у мелких значений: «Б 12,3» в строке это вид
    // точности, которой у таблиц КБЖУ нет, а «У 0,7» — настоящее число.
    return v >= 10 ? `${Math.round(v)}` : `${Math.round(v * 10) / 10}`;
  };
  return `Б ${n(proteins)} · Ж ${n(fats)} · У ${n(carbs)} г`;
};

// MG_FOODSCALE: размер шрифта в списках еды.
export type FoodTextScale = 'small' | 'normal' | 'large';

export const FOOD_SCALE_OPTIONS: { value: FoodTextScale; label: string }[] = [
  { value: 'small', label: 'Мелкий' },
  { value: 'normal', label: 'Обычный' },
  { value: 'large', label: 'Крупный' },
];

export const scaleOf = (profile?: UserProfile | null): FoodTextScale => {
  const raw = profile?.food_text_scale;
  return raw === 'small' || raw === 'large' ? raw : 'normal';
};

/** Множитель к обычному размеру. Умеренный намеренно: в браузере поверх него
 *  работает и собственный зум страницы. */
export const scaleFactor = (s: FoodTextScale): number =>
  s === 'small' ? 0.9 : s === 'large' ? 1.15 : 1;
