// MG_SPECUI: подписи и оценки для карточки клиента.
//
// Вынесено из компонентов: это те решения, из-за которых специалист поймёт
// цифру правильно или неправильно, и проверять их надо тестами, а не глазами.

export const FOOD_GROUP_LABELS: Record<string, string> = {
  grain: 'Зерновые',
  protein: 'Белковые',
  vegetable: 'Овощи',
  fruit: 'Фрукты',
  dairy: 'Молочные',
  oil: 'Масла и жиры',
  other: 'Прочее',
  unknown: 'Без группы',
};

export const PROTEIN_TYPE_LABELS: Record<string, string> = {
  animal: 'Животный',
  plant: 'Растительный',
  mixed: 'Смешанный',
};

export const TARGET_FIELD_LABELS: Record<string, string> = {
  calorie_target: 'Калории',
  protein_target_g: 'Белки',
  fat_target_g: 'Жиры',
  carb_target_g: 'Углеводы',
  fiber_target_g: 'Клетчатка',
};

export const TARGET_SOURCE_LABELS: Record<string, string> = {
  auto: 'расчёт',
  user: 'клиент',
  specialist: 'специалист',
};

export const labelFor = (dict: Record<string, string>, key: string): string => dict[key] ?? key;

/** Соблюдение плана в процентах от дней с записями. */
export const adherencePercent = (daysOnPlan: number, daysTracked: number): number | null => {
  if (!daysTracked) return null;
  return Math.round((daysOnPlan * 100) / daysTracked);
};

/**
 * Насколько среднее отклоняется от цели, в процентах со знаком.
 * null — если цели нет: писать «0%» там, где цель не задана, значит соврать.
 */
export const deviationPercent = (actual: number, target: number | null): number | null => {
  if (!target) return null;
  return Math.round(((actual - target) * 100) / target);
};

/**
 * Насколько ответу можно верить. Считается по доле записей с рецептом:
 * состав известен только у них, и при низкой доле числа ни о чём не говорят.
 */
export const coverageNote = (percent: number): string => {
  if (percent >= 80) return '';
  if (percent >= 50) return 'Часть записей — своей едой, состав по ним неизвестен.';
  return 'Больше половины записей — своей едой. Разбор состава ненадёжен.';
};

/** Подпись к динамике веса: знак важнее числа. */
export const weightTrend = (changeKg: number | null): string => {
  if (changeKg === null || changeKg === 0) return 'без изменений';
  const sign = changeKg > 0 ? '+' : '−';
  return `${sign}${Math.abs(changeKg).toFixed(1)} кг`;
};

/** Вода в литрах на день с записью — среднее, а не сумма за период. */
export const waterPerDay = (totalMl: number, daysLogged: number): string => {
  if (!daysLogged) return '—';
  return `${(totalMl / daysLogged / 1000).toFixed(1)} л/день`;
};
