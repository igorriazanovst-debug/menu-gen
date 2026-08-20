// MG_TRAINER: динамика веса в карточке дневника.
import { weightDelta } from './weightDelta';

const point = (date: string, weight_kg: string) => ({ id: 1, date, weight_kg, note: '' });

describe('weightDelta', () => {
  test('разница между первым и последним замером', () => {
    expect(weightDelta([point('2026-03-01', '81.0'), point('2026-03-08', '79.5')])).toBe(-1.5);
  });

  test('одной точки мало для динамики', () => {
    // Показать «0 кг» по единственному замеру — соврать про стабильный вес.
    expect(weightDelta([point('2026-03-01', '81.0')])).toBeNull();
    expect(weightDelta([])).toBeNull();
  });

  test('нечисловое значение не ломает расчёт', () => {
    expect(weightDelta([point('2026-03-01', 'нет'), point('2026-03-08', '79.5')])).toBeNull();
  });
});
