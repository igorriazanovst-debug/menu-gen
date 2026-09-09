// DIARY_EATALL_V1: какие записи затронет «съесть всё».
//
// MG_EATFLAG: все, что показаны. Раньше групповое действие трогало только
// плановые записи — потому что у ручных галочки не было вовсе: факт считался по
// правилу «отмечено ИЛИ добавлено руками», и отметка у них ничего не меняла.
// Теперь правило одно для всех — съедено то, что отмечено, — и отмечать можно
// каждую строку. Значит, и «съедено всё» обязано брать каждую: иначе оно снова
// отставало бы от того, что человек видит.

export interface MarkableEntry {
  id: number;
  is_eaten?: boolean;
  is_planned?: boolean;
  planned_menu_item?: number | null;
}

/** Плановая запись: явный флаг или связь с меню (наследие).
 *
 * Осталась не для отметок, а для разметки: по ней считается «план» в итогах
 * дня и рисуется подпись у строки. К тому, можно ли снять галочку, отношения
 * больше не имеет.
 */
export const isPlanned = (e: MarkableEntry): boolean =>
  e.is_planned === true || (e.planned_menu_item !== null && e.planned_menu_item !== undefined);

/** Все ли записи уже отмечены съеденными. Пусто — значит нет. */
export const allEaten = (entries: MarkableEntry[]): boolean =>
  entries.length > 0 && entries.every((e) => e.is_eaten === true);

/**
 * Кого менять при нажатии. Возвращает id и целевое состояние: если отмечено всё —
 * снимаем, иначе доотмечаем недостающие. Уже стоящие галочки не трогаем, чтобы
 * не слать лишние запросы.
 */
export const toMark = (entries: MarkableEntry[]): { ids: number[]; eaten: boolean } => {
  const eaten = !allEaten(entries);
  return { ids: entries.filter((e) => (e.is_eaten === true) !== eaten).map((e) => e.id), eaten };
};
