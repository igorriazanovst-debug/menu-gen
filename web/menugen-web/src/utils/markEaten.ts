// DIARY_EATALL_V1: какие записи затронет «съесть всё».
//
// Отмечать можно только плановые записи: у записи, добавленной руками, факт и
// есть сам факт — галочки у неё нет. Групповое действие обязано жить по тому же
// правилу, иначе оно тронет то, что поштучно тронуть нельзя.

export interface MarkableEntry {
  id: number;
  is_eaten?: boolean;
  is_planned?: boolean;
  planned_menu_item?: number | null;
}

/** Плановая запись: явный флаг или связь с меню (наследие). */
export const isPlanned = (e: MarkableEntry): boolean =>
  e.is_planned === true || (e.planned_menu_item !== null && e.planned_menu_item !== undefined);

/** Все ли плановые записи уже отмечены съеденными. Пусто — значит нет. */
export const allEaten = (entries: MarkableEntry[]): boolean => {
  const plan = entries.filter(isPlanned);
  return plan.length > 0 && plan.every((e) => e.is_eaten === true);
};

/**
 * Кого menять при нажатии. Возвращает id и целевое состояние: если отмечено всё —
 * снимаем, иначе доотмечаем недостающие. Уже стоящие галочки не трогаем, чтобы
 * не слать лишние запросы.
 */
export const toMark = (entries: MarkableEntry[]): { ids: number[]; eaten: boolean } => {
  const plan = entries.filter(isPlanned);
  const eaten = !allEaten(entries);
  return { ids: plan.filter((e) => (e.is_eaten === true) !== eaten).map((e) => e.id), eaten };
};
