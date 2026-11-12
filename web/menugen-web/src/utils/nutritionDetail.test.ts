// MG_NUTRIDETAIL: строка БЖУ и чтение настройки.
//
// Числа у записи те же — меняется только то, что из них видно. Проверяется
// то, на чём такие вещи ломаются молча: округление, пустота и незнакомое
// значение с сервера.
import { detailOf, macrosShort, showsGrams, showsMacros } from './nutritionDetail';

describe('macrosShort', () => {
  test('буквами, граммы один раз в конце', () => {
    // Полные слова рядом с названием блюда не помещаются и обрезаются — то
    // есть пропадает то, ради чего их показывают.
    expect(macrosShort(12, 8, 30)).toBe('Б 12 · Ж 8 · У 30 г');
  });

  test('мелкие значения не округляются в ноль', () => {
    expect(macrosShort(13, 12, 0.7)).toBe('Б 13 · Ж 12 · У 0.7 г');
  });

  test('крупные значения — целые', () => {
    expect(macrosShort(89.4, 51, 167.2)).toBe('Б 89 · Ж 51 · У 167 г');
  });

  test('без чисел строки нет вовсе', () => {
    // «Б 0 · Ж 0 · У 0 г» — это утверждение, а не «не знаем».
    expect(macrosShort(0, 0, 0)).toBe('');
  });
});

describe('detailOf', () => {
  test('по умолчанию — калории и БЖУ', () => {
    expect(detailOf(null)).toBe('normal');
    expect(detailOf({ activity_level: 'moderate', goal: 'maintain' })).toBe('normal');
  });

  test('выбор человека', () => {
    expect(detailOf({ activity_level: 'm', goal: 'g', nutrition_detail: 'short' })).toBe('short');
    expect(detailOf({ activity_level: 'm', goal: 'g', nutrition_detail: 'detailed' })).toBe('detailed');
  });

  test('незнакомое значение — умолчание, а не пустой экран', () => {
    // Сервер может оказаться новее фронта.
    expect(detailOf({ activity_level: 'm', goal: 'g', nutrition_detail: 'всё' as never })).toBe('normal');
  });
});

describe('что показывает режим', () => {
  test('кратко — только калории', () => {
    expect(showsMacros('short')).toBe(false);
    expect(showsGrams('short')).toBe(false);
  });

  test('обычно — калории и БЖУ', () => {
    expect(showsMacros('normal')).toBe(true);
    expect(showsGrams('normal')).toBe(false);
  });

  test('подробно — ещё и вес порции', () => {
    expect(showsMacros('detailed')).toBe(true);
    expect(showsGrams('detailed')).toBe(true);
  });
});
