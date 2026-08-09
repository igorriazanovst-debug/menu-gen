// MG_SHOP2FRIDGE: перенос купленного из списка покупок в холодильник.
//
// Кнопка отправляла всё купленное разом и без вопросов. Отменить перенос
// нечем — убирать позиции пришлось бы вручную из холодильника, — поэтому
// сначала спрашиваем и показываем, что именно уедет.
import type { ShoppingV2Item } from '../types';

/** Что уедет в холодильник: купленное, ещё не добавленное и съедобное. */
export const fridgeCandidates = (items: ShoppingV2Item[]): ShoppingV2Item[] =>
  items.filter((it) => it.is_purchased && !it.in_fridge && it.fridge_eligible);

/** Текст подтверждения: сколько позиций и какие именно. */
export const fridgeConfirmText = (candidates: ShoppingV2Item[], maxNames = 5): string => {
  const names = candidates.map((it) => it.name);
  const shown = names.slice(0, maxNames).join(', ');
  const rest = names.length - maxNames;
  const list = rest > 0 ? `${shown} и ещё ${rest}` : shown;
  return `Добавить в холодильник: ${candidates.length}?\n\n${list}`;
};
