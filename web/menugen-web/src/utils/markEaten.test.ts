// DIARY_EATALL_V1: групповая отметка «съедено».
import { allEaten, isPlanned, toMark } from './markEaten';

const plan = (id: number, eaten = false) => ({ id, is_eaten: eaten, is_planned: true });
const manual = (id: number) => ({ id, is_eaten: true, is_planned: false, planned_menu_item: null });

describe('toMark', () => {
  test('отмечает все неотмеченные плановые записи', () => {
    expect(toMark([plan(1), plan(2, true), plan(3)])).toEqual({ ids: [1, 3], eaten: true });
  });

  test('повторное нажатие снимает отметки', () => {
    expect(toMark([plan(1, true), plan(2, true)])).toEqual({ ids: [1, 2], eaten: false });
  });

  test('не трогает записи, добавленные руками', () => {
    // У них нет галочки поштучно — значит и группой их менять нельзя.
    expect(toMark([plan(1), manual(2)])).toEqual({ ids: [1], eaten: true });
  });

  test('без плановых записей менять нечего', () => {
    expect(toMark([manual(2)])).toEqual({ ids: [], eaten: true });
  });
});

describe('allEaten', () => {
  test('пустой список не считается отмеченным', () => {
    expect(allEaten([])).toBe(false);
  });

  test('учитывает только плановые', () => {
    expect(allEaten([plan(1, true), manual(2)])).toBe(true);
  });
});

describe('isPlanned', () => {
  test('связь с меню — тоже план', () => {
    expect(isPlanned({ id: 1, planned_menu_item: 42 })).toBe(true);
  });

  test('запись руками планом не является', () => {
    expect(isPlanned({ id: 1, planned_menu_item: null })).toBe(false);
  });
});
