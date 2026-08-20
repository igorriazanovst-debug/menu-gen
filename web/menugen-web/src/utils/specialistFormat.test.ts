// MG_SPECUI: подписи и оценки в карточке клиента.
//
// Проверяется не вёрстка, а решения, из-за которых специалист поймёт цифру
// правильно или неправильно: чего не хватает — там должен быть прочерк, а не
// ноль, и низкое покрытие должно быть названо вслух.
import {
  adherencePercent,
  coverageNote,
  deviationPercent,
  labelFor,
  waterPerDay,
  weightTrend,
  FOOD_GROUP_LABELS,
} from './specialistFormat';

describe('adherencePercent', () => {
  test('считается от дней с записями, а не от всего периода', () => {
    expect(adherencePercent(2, 4)).toBe(50);
  });

  test('без записей — null, а не ноль процентов', () => {
    // Ноль сказал бы «клиент не соблюдал», хотя он просто не вёл дневник.
    expect(adherencePercent(0, 0)).toBeNull();
  });
});

describe('deviationPercent', () => {
  test('превышение цели даёт плюс', () => {
    expect(deviationPercent(2400, 2000)).toBe(20);
  });

  test('недобор даёт минус', () => {
    expect(deviationPercent(1600, 2000)).toBe(-20);
  });

  test('без цели отклонения нет', () => {
    // «0% к цели» при незаданной цели — выдумка.
    expect(deviationPercent(2400, null)).toBeNull();
    expect(deviationPercent(2400, 0)).toBeNull();
  });
});

describe('coverageNote', () => {
  test('высокое покрытие не требует оговорки', () => {
    expect(coverageNote(85)).toBe('');
  });

  test('среднее покрытие оговаривается', () => {
    expect(coverageNote(60)).toContain('своей едой');
  });

  test('низкое покрытие названо ненадёжным', () => {
    expect(coverageNote(30)).toContain('ненадёжен');
  });
});

describe('weightTrend', () => {
  test('снижение показывается со знаком минус', () => {
    expect(weightTrend(-1.5)).toBe('−1.5 кг');
  });

  test('набор показывается со знаком плюс', () => {
    expect(weightTrend(2)).toBe('+2.0 кг');
  });

  test('нет данных или нет изменений — словами', () => {
    expect(weightTrend(null)).toBe('без изменений');
    expect(weightTrend(0)).toBe('без изменений');
  });
});

describe('waterPerDay', () => {
  test('среднее за день, а не сумма за период', () => {
    expect(waterPerDay(7000, 4)).toBe('1.8 л/день');
  });

  test('без записей — прочерк', () => {
    expect(waterPerDay(0, 0)).toBe('—');
  });
});

describe('labelFor', () => {
  test('известный ключ переводится', () => {
    expect(labelFor(FOOD_GROUP_LABELS, 'vegetable')).toBe('Овощи');
  });

  test('незнакомый ключ показывается как есть', () => {
    // Лучше английский ключ на экране, чем пустое место.
    expect(labelFor(FOOD_GROUP_LABELS, 'seaweed')).toBe('seaweed');
  });
});
