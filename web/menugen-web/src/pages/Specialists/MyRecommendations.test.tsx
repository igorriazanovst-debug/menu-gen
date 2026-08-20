// MG_TRAINER: рекомендации у клиента.
import { periodLabel } from './MyRecommendations';

describe('periodLabel', () => {
  test('оба конца — интервал', () => {
    expect(periodLabel('2026-03-01', '2026-03-14')).toBe('2026-03-01 — 2026-03-14');
  });

  test('только начало — открытый интервал', () => {
    // «с 1 марта» и «без срока» — разные вещи: первое ещё действует.
    expect(periodLabel('2026-03-01', null)).toBe('с 2026-03-01');
  });

  test('только конец', () => {
    expect(periodLabel(null, '2026-03-14')).toBe('до 2026-03-14');
  });

  test('ничего не задано', () => {
    expect(periodLabel(null, null)).toBe('без срока');
  });
});
