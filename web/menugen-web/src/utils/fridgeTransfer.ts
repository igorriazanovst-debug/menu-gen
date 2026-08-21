// MG_SHOP2FRIDGE: перенос купленного из списка покупок в холодильник.
//
// Кнопка отправляла всё купленное разом и без вопросов. Отменить перенос
// нечем — убирать позиции пришлось бы вручную из холодильника, — поэтому
// сначала показываем в окне переноса, что именно уедет (MG_SHELFLIFE:
// там же правятся сроки годности).
import type { ShoppingV2Item } from '../types';

/** Что уедет в холодильник: купленное, ещё не добавленное и съедобное. */
export const fridgeCandidates = (items: ShoppingV2Item[]): ShoppingV2Item[] =>
  items.filter((it) => it.is_purchased && !it.in_fridge && it.fridge_eligible);
