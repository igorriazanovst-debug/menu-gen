// FILL_FROM_MENU_V5: что показать после «Заполнить из меню».
//
// Поводом стал реальный случай на dev: импорт создал 7 записей на 21 августа,
// а дневник перескочил на 20-е — дату начала плана. Выглядело как «ничего не
// произошло», хотя записи были на месте.
import { importOutcome } from './importOutcome';

describe('importOutcome', () => {
  test('переводит на дату самой ранней записи, а не на дату начала плана', () => {
    const r = importOutcome({
      created: 7,
      skipped: 0,
      entries: [{ date: '2026-08-23' }, { date: '2026-08-21' }, { date: '2026-08-22' }],
    });

    expect(r.jumpDate).toBe('2026-08-21');
    expect(r.keepOpen).toBe(false);
    expect(r.message).toContain('7');
  });

  test('повторный импорт объясняет, почему ничего не создалось', () => {
    // Раньше окно просто закрывалось — неотличимо от поломки.
    const r = importOutcome({ created: 0, skipped: 5, entries: [{ date: '2026-08-21' }] });

    expect(r.keepOpen).toBe(true);
    expect(r.message).toContain('уже были добавлены');
    expect(r.jumpDate).toBe('2026-08-21');
  });

  test('пустой ответ не выдумывает сообщение', () => {
    const r = importOutcome({ created: 0, skipped: 0, entries: [] });

    expect(r.message).toBe('');
    expect(r.jumpDate).toBeNull();
  });

  test('битая дата не роняет разбор', () => {
    const r = importOutcome({ created: 1, skipped: 0, entries: [{ date: 'не дата' }] });

    expect(r.jumpDate).toBe('не дата');
    expect(r.message).toContain('не дата');
  });
});
