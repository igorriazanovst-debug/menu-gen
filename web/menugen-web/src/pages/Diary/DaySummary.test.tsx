// MG_DAYSUM + MG_WORKOUT: «Итоги дня» и физнагрузки в браузере.
//
// Главное, что проверяется, — чего мы НЕ делаем:
//
// * расход на тренировке НЕ прибавляется к остатку: норма уже содержит
//   коэффициент активности, и прибавка посчитала бы его дважды — человеку на
//   похудении приложение разрешило бы съесть лишнее;
// * без цели по калориям кольцо не рисуется: процент от выдуманной нормы — это
//   ложь в самом заметном месте экрана;
// * в факт идёт только отмеченное съеденным, плановое ждёт галочки.
//
// Фабрика мока: реальный api/diary тянет axios (ESM) через api/client.
jest.mock('../../api/diary', () => ({
  diaryApi: { getWeight: jest.fn() },
}));

import '@testing-library/jest-dom';

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DaySummary } from './DaySummary';
import { diaryApi } from '../../api/diary';
import type { DiaryDayStats, DiaryEntry, MealSlot, UserProfile } from '../../types';

const mockApi = diaryApi as jest.Mocked<typeof diaryApi>;

const bucket = (calories: number, proteins = 0, fats = 0, carbs = 0) =>
  ({ calories, proteins, fats, carbs });

const stats = (over: Partial<DiaryDayStats> = {}): DiaryDayStats => ({
  date: '2026-11-09',
  planned: bucket(0),
  actual: bucket(1480, 89, 51, 167),
  total: bucket(1480, 89, 51, 167),
  burned: 0,
  ...over,
});

const entry = (id: number, slot: MealSlot, kcal: number, eaten = true): DiaryEntry => ({
  id,
  date: '2026-11-09',
  meal_type: slot === 'snack1' || slot === 'snack2' ? 'snack' : (slot as 'breakfast' | 'lunch' | 'dinner'),
  meal_slot: slot,
  custom_name: `Еда ${id}`,
  nutrition: { calories: { value: String(kcal), unit: 'ккал' } },
  quantity: 1,
  is_eaten: eaten,
});

const profile = (over: Partial<UserProfile> = {}): UserProfile => ({
  activity_level: 'moderate',
  goal: 'maintain',
  calorie_target: 2000,
  protein_target_g: '110',
  fat_target_g: '67',
  carb_target_g: '225',
  meal_plan_type: '3',
  ...over,
});

const show = async (props: Partial<React.ComponentProps<typeof DaySummary>> = {}) => {
  render(
    <MemoryRouter>
      <DaySummary
        date="2026-11-09"
        memberId={undefined}
        stats={stats()}
        entries={[]}
        waterMl={1600}
        profile={profile()}
        {...props}
      />
    </MemoryRouter>,
  );
  // Вес подгружается отдельным запросом — ждём, пока он осядет.
  await waitFor(() => expect(mockApi.getWeight).toHaveBeenCalled());
};

describe('Итоги дня', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.getWeight.mockResolvedValue([
      { id: 1, date: '2026-11-09', weight_kg: '78.25', note: '' },
    ] as any);
  });

  it('кольцо считает съеденное от цели, а не от плана', async () => {
    await show({ stats: stats({ planned: bucket(2400) }) });

    expect(screen.getByText('74%')).toBeInTheDocument();
    expect(screen.getByText(/съедено из/)).toBeInTheDocument();
  });

  it('остаток — это цель минус съеденное', async () => {
    await show();

    expect(screen.getByText('осталось')).toBeInTheDocument();
    expect(screen.getByText('520')).toBeInTheDocument();
  });

  it('перебор назван перебором, а не отрицательным остатком', async () => {
    await show({ stats: stats({ actual: bucket(2300), total: bucket(2300) }) });

    expect(screen.getByText('перебор')).toBeInTheDocument();
    expect(screen.getByText('+300')).toBeInTheDocument();
    expect(screen.queryByText('осталось')).not.toBeInTheDocument();
  });

  it('без цели кольца нет, а есть ссылка в калькулятор', async () => {
    await show({ profile: profile({ calorie_target: undefined }) });

    expect(screen.queryByText('от цели')).not.toBeInTheDocument();
    expect(screen.getByText(/Цель по калориям не задана/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Посчитать' }))
      .toHaveAttribute('href', '/profile/kbju-calculator');
  });

  it('без цели съеденное всё равно показано', async () => {
    await show({ profile: profile({ calorie_target: undefined }) });

    expect(screen.getByText('ккал съедено')).toBeInTheDocument();
  });

  it('расход показан отдельно и остаток не меняет', async () => {
    // Ради этого правила всё и устроено именно так.
    await show({ stats: stats({ burned: 550 }) });

    expect(screen.getByText('Потрачено')).toBeInTheDocument();
    expect(screen.getByText('550 ккал')).toBeInTheDocument();
    expect(screen.getByText('520')).toBeInTheDocument(); // 2000 − 1480, и никак иначе
    expect(screen.queryByText('1 070')).not.toBeInTheDocument(); // 520 + 550
  });

  it('день без занятий цифрой не сорит', async () => {
    await show({ stats: stats({ burned: 0 }) });

    expect(screen.queryByText('0 ккал')).not.toBeInTheDocument();
  });

  it('в приём идёт только отмеченное съеденным', async () => {
    await show({
      entries: [
        entry(1, 'breakfast', 412),
        entry(2, 'lunch', 735, false),
      ],
    });

    expect(screen.getByText('412 ккал')).toBeInTheDocument();
    expect(screen.queryByText('735 ккал')).not.toBeInTheDocument();
  });

  it('перекусов при раскладке на три приёма нет', async () => {
    await show();

    expect(screen.getByText('Обед')).toBeInTheDocument();
    expect(screen.queryByText('Перекус 1')).not.toBeInTheDocument();
  });

  it('вода и вес показаны, но не правятся здесь', async () => {
    await show();

    expect(screen.getByText('1 600 мл')).toBeInTheDocument();
    expect(screen.getByText('78.25 кг')).toBeInTheDocument();
    expect(document.querySelectorAll('input')).toHaveLength(0);
  });

  it('без замера веса — прочерк, а не ноль', async () => {
    mockApi.getWeight.mockResolvedValue([] as any);

    await show();

    expect(screen.queryByText('0 кг')).not.toBeInTheDocument();
  });

  it('доля калорий считается от съеденного', async () => {
    // Белки 89 г → 356 ккал из 1483 (89·4 + 51·9 + 167·4) — это 24 %.
    // Вопрос «чего в рационе больше» не зависит от того, задана ли норма.
    await show({ profile: profile({ calorie_target: undefined }) });

    expect(screen.getByText('24% калорий')).toBeInTheDocument();
  });

  describe('Полосы', () => {
    // На телефоне полосы оказались пустыми при непустых числах: заливка
    // схлопывалась в ноль. В вебе вёрстка другая, но проверять надо то же —
    // саму заливку, а не подписи рядом с ней.
    const widths = () =>
      Array.from(document.querySelectorAll<HTMLElement>('div[style*="width"]'))
        .map((d) => d.style.width)
        .filter((w) => w && w !== '0%');

    it('полоса макроса заполнена по норме, а не пуста', async () => {
      // Белки 89 из 110 г — это 80.9 %.
      await show();

      expect(widths()).toContain(`${(89 / 110) * 100}%`);
    });

    it('полоса приёма мерится дневной нормой', async () => {
      // Обед 488 из нормы 2 000 — это 24.4 %, а не «весь приём целиком»
      // оттого, что он крупнейший за день.
      await show({
        entries: [entry(1, 'breakfast', 272), entry(2, 'lunch', 488)],
      });

      expect(widths()).toContain(`${(488 / 2000) * 100}%`);
    });

    it('без нормы приёмы мерятся самым крупным', async () => {
      await show({
        profile: profile({ calorie_target: undefined }),
        entries: [entry(1, 'breakfast', 272), entry(2, 'lunch', 488)],
      });

      expect(widths()).toContain('100%');
    });

    it('перебор отмечен своим цветом, а не цветом жиров', async () => {
      // Цвет перебора намеренно не оранжевый акцент: он равен цвету жиров, и
      // перебор по жирам был бы невидим.
      await show({ stats: stats({ actual: bucket(1480, 89, 90, 167) }) });

      const colors = Array.from(document.querySelectorAll<HTMLElement>('div[style*="background-color"]'))
        .map((d) => d.style.backgroundColor);

      expect(colors).toContain('rgb(226, 114, 91)'); // #E2725B
    });
  });
});
