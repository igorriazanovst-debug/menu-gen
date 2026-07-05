// MG_ALLERGEN14 — обязательные к маркировке аллергены (ТР ТС 022/2011,
// EU 1169/2011). Зеркалит backend apps/common/allergens.py (ключи совпадают).
export interface AllergenDef {
  key: string;
  label: string;
  group: string;
  full: string;
}

export const ALLERGENS: AllergenDef[] = [
  { key: 'gluten', label: 'Глютен (злаки)', group: 'Злаки', full: 'Злаки, содержащие глютен: пшеница (в т.ч. полба, камут), рожь, ячмень, овёс' },
  { key: 'crustaceans', label: 'Ракообразные', group: 'Морепродукты', full: 'Ракообразные и продукты их переработки (крабы, креветки, омары и др.)' },
  { key: 'eggs', label: 'Яйца', group: 'Яйца', full: 'Яйца и продукты их переработки' },
  { key: 'fish', label: 'Рыба', group: 'Рыба', full: 'Рыба и продукты её переработки' },
  { key: 'peanuts', label: 'Арахис', group: 'Орехи/бобовые', full: 'Арахис и продукты его переработки' },
  { key: 'soy', label: 'Соя', group: 'Бобовые', full: 'Соя и продукты её переработки' },
  { key: 'milk', label: 'Молоко', group: 'Молочные продукты', full: 'Молоко и продукты его переработки (включая лактозу)' },
  { key: 'nuts', label: 'Орехи', group: 'Орехи', full: 'Орехи: миндаль, фундук, грецкий, кешью, пекан, бразильский, фисташки, макадамия' },
  { key: 'celery', label: 'Сельдерей', group: 'Овощи', full: 'Сельдерей и продукты его переработки' },
  { key: 'mustard', label: 'Горчица', group: 'Приправы', full: 'Горчица и продукты её переработки' },
  { key: 'sesame', label: 'Кунжут', group: 'Семена', full: 'Кунжут и продукты его переработки' },
  { key: 'sulphites', label: 'Диоксид серы и сульфиты', group: 'Добавки', full: 'Диоксид серы и сульфиты в концентрации более 10 мг/кг (мг/л)' },
  { key: 'lupin', label: 'Люпин', group: 'Бобовые', full: 'Люпин и продукты его переработки' },
  { key: 'molluscs', label: 'Моллюски', group: 'Морепродукты', full: 'Моллюски и продукты их переработки (устрицы, мидии, кальмары и др.)' },
];

const BY_KEY: Record<string, AllergenDef> = {};
ALLERGENS.forEach((a) => {
  BY_KEY[a.key] = a;
});

export const ALLERGEN_KEYS = ALLERGENS.map((a) => a.key);

/** Человекочитаемая метка по ключу; для кастомных/неизвестных — само значение. */
export function allergenLabel(key: string): string {
  return BY_KEY[key]?.label ?? key;
}

/** true, если значение — один из 14 стандартных ключей. */
export function isKnownAllergen(key: string): boolean {
  return !!BY_KEY[key];
}
