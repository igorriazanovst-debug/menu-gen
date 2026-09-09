// DIARY_EATALL_V1: групповая отметка «съедено».
//
// MG_EATFLAG: правило поменялось — теперь отмечать можно любую запись, и
// групповое действие берёт все показанные. Прежние проверки описывали старое
// устройство, где у записи, добавленной руками, галочки не было вовсе: факт
// считался по правилу «отмечено ИЛИ добавлено руками», и её отметка ничего не
// меняла. Со стороны это выглядело поломкой — в приёме из трёх строк снять
// галочку можно было только с плановой.
import { allEaten, isPlanned, toMark } from './markEaten';

const plan = (id: number, eaten = false) => ({ id, is_eaten: eaten, is_planned: true });
const manual = (id: number, eaten = true) => ({
  id,
  is_eaten: eaten,
  is_planned: false,
  planned_menu_item: null,
});

describe('toMark', () => {
  test('отмечает все неотмеченные записи', () => {
    expect(toMark([plan(1), plan(2, true), plan(3)])).toEqual({ ids: [1, 3], eaten: true });
  });

  test('повторное нажатие снимает отметки', () => {
    expect(toMark([plan(1, true), plan(2, true)])).toEqual({ ids: [1, 2], eaten: false });
  });

  test('записи, добавленные руками, тоже отмечаются группой', () => {
    // Раньше они выпадали из группового действия, потому что не имели галочки
    // поштучно. Теперь имеют — значит и группой их брать надо.
    expect(toMark([plan(1), manual(2, false)])).toEqual({ ids: [1, 2], eaten: true });
  });

  test('всё отмечено — нажатие снимает всё, включая ручные', () => {
    expect(toMark([plan(1, true), manual(2)])).toEqual({ ids: [1, 2], eaten: false });
  });
});

describe('allEaten', () => {
  test('пустой список не считается отмеченным', () => {
    expect(allEaten([])).toBe(false);
  });

  test('учитывает все записи, а не только плановые', () => {
    expect(allEaten([plan(1, true), manual(2)])).toBe(true);
    expect(allEaten([plan(1, true), manual(2, false)])).toBe(false);
  });
});

describe('isPlanned', () => {
  // Признак остался: по нему считается «план» в итогах дня и подписывается
  // строка. К возможности снять галочку он больше отношения не имеет.
  test('связь с меню — тоже план', () => {
    expect(isPlanned({ id: 1, planned_menu_item: 42 })).toBe(true);
  });

  test('запись руками планом не является', () => {
    expect(isPlanned({ id: 1, planned_menu_item: null })).toBe(false);
  });
});
