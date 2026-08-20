// DIARY_TOTALS_V1: почему в итоге дня нули.
import { dayTotalsHint } from './dayTotalsHint';

describe('dayTotalsHint', () => {
  test('план есть, факта нет — объясняем, что нужно отметить съеденное', () => {
    // Ровно этот случай выглядел как поломка: «0 / 747 ккал».
    expect(dayTotalsHint({ calories: 747 }, { calories: 0 })).toContain('отмечено съеденным');
  });

  test('пустой день — предлагаем заполнить', () => {
    expect(dayTotalsHint({ calories: 0 }, { calories: 0 })).toContain('заполните из меню');
  });

  test('факт появился — подсказка молчит', () => {
    expect(dayTotalsHint({ calories: 747 }, { calories: 320 })).toBe('');
  });

  test('еда без плана — тоже молчит', () => {
    // Съел, не планируя: нули не о чем объяснять.
    expect(dayTotalsHint({ calories: 0 }, { calories: 500 })).toBe('');
  });
});
