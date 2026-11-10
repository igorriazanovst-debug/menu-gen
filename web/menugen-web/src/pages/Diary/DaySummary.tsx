// MG_DAYSUM: вкладка «Итоги дня».
//
// Отвечает на главный вопрос дня одним взглядом: сколько съедено из нормы и
// сколько осталось. До этого ответа не было вовсе — дневник показывал, ЧТО
// съедено, а чтобы понять, много это или мало, надо было считать в голове.
//
// Четыре правила, по которым здесь считается:
//
// **Сравниваем с нормой человека, а не с планом меню.** Сводка над списком еды
// сравнивает факт с запланированным — это другой вопрос («выполнил ли план»).
// Здесь вопрос «сколько мне ещё можно», и ответ на него даёт `calorie_target`
// из профиля. Нормы нет — кольца нет: нарисовать его от выдуманной нормы
// значит соврать в самом заметном месте экрана.
//
// **Факт — это съеденное.** Плановая запись без галочки показана бледной
// частью полосы: видно, что день ещё не закрыт, но в сумму она не идёт.
//
// **Расход не вычитается.** Норма уже содержит коэффициент активности, и
// прибавка за тренировку посчитала бы его дважды (см.
// backend/apps/diary/workout_calories.py). Потраченное стоит отдельной
// плиткой — его видно, но на остаток оно не влияет.
//
// **Проценты БЖУ считаются от съеденного, а не от нормы.** Вопрос «чего в моём
// рационе больше» не зависит от того, задана ли норма.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { diaryApi } from '../../api/diary';
import { Card } from '../../components/ui/Card';
import { MEAL_SLOT_LABELS, MEAL_SLOTS_BY_PLAN } from '../../types';
import { nutriVal, slotOf, visibleSlots } from '../../utils/diaryNutrition';
import type { DiaryDayStats, DiaryEntry, MealPlan, UserProfile } from '../../types';

/** Калорийность грамма (коэффициенты Атуотера) — числа общепринятые. */
const KCAL_PER_GRAM = { proteins: 4, fats: 9, carbs: 4 } as const;

const MACRO_COLORS = { proteins: '#588157', fats: '#F4A261', carbs: '#7CB342' } as const;

/** Цвет перебора — один на весь экран: и кольцо, и полосы.
 *
 * Намеренно не оранжевый акцент: он равен цвету жиров, и перебор по жирам
 * оранжевым по оранжевому был бы невидим ровно там, где его чаще всего и
 * видят. И намеренно не красный: съесть лишнее — не ошибка приложения. */
const OVER_COLOR = '#E2725B';

/** Тысячи узким пробелом: «1 480» читается быстрее, чем «1480». */
const thousands = (v: number): string =>
  Math.round(v).toLocaleString('ru-RU').replace(/ /g, ' ');

const grams = (v: number): string => (v >= 10 ? `${Math.round(v)}` : v.toFixed(1));

const num = (raw: unknown): number | null => {
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : null;
  if (typeof raw === 'string') {
    const v = Number(raw.replace(',', '.'));
    return Number.isFinite(v) ? v : null;
  }
  return null;
};

interface Props {
  date: string;
  memberId?: number;
  stats: DiaryDayStats | null;
  entries: DiaryEntry[];
  waterMl: number;
  profile?: UserProfile | null;
}

export const DaySummary: React.FC<Props> = ({ date, memberId, stats, entries, waterMl, profile }) => {
  // Вес за этот день. Только показ: правится на вкладке «Тело», и второго
  // места ввода для одного числа здесь нет намеренно — два поля расходятся.
  const [weight, setWeight] = useState<string | null>(null);

  const loadWeight = useCallback(async () => {
    try {
      const rows = await diaryApi.getWeight(90, memberId);
      setWeight(rows.find((p) => p.date === date)?.weight_kg ?? null);
    } catch {
      setWeight(null);
    }
  }, [date, memberId]);

  useEffect(() => { loadWeight(); }, [loadWeight]);

  const actual = stats?.actual ?? { calories: 0, proteins: 0, fats: 0, carbs: 0 };
  const planned = stats?.planned ?? { calories: 0, proteins: 0, fats: 0, carbs: 0 };
  const burned = stats?.burned ?? 0;
  const target = profile?.calorie_target ?? null;

  const meals = useMemo(() => {
    const plan: MealPlan = profile?.meal_plan_type ?? '3';
    const rows = visibleSlots(entries, MEAL_SLOTS_BY_PLAN[plan]).map((slot) => ({
      slot,
      // В приём идёт только отмеченное съеденным: плановое ждёт галочки.
      kcal: entries
        .filter((e) => slotOf(e) === slot && e.is_eaten)
        .reduce((sum, e) => sum + nutriVal(e, 'calories'), 0),
    }));
    // Масштаб — дневная норма: видно не только, какой приём крупнее, но и
    // сколько от дня он занял, а полосы в сумме дают заполненность кольца.
    // Нормы нет — меряем по самому крупному приёму: это хуже (непонятно, много
    // это или мало), но честнее, чем полосы от выдуманного числа.
    const top = rows.reduce((m, r) => Math.max(m, r.kcal), 0);
    const norm = profile?.calorie_target ?? null;
    return { rows, scale: norm && norm > 0 ? norm : top, norm };
  }, [entries, profile?.meal_plan_type, profile?.calorie_target]);

  const macroKcal =
    actual.proteins * KCAL_PER_GRAM.proteins +
    actual.fats * KCAL_PER_GRAM.fats +
    actual.carbs * KCAL_PER_GRAM.carbs;

  const left = target === null ? null : target - actual.calories;

  const ring = () => {
    const r = 38;
    const c = 2 * Math.PI * r;
    const ratio = target && target > 0 ? Math.min(1, Math.max(0, actual.calories / target)) : 0;
    const pct = target && target > 0 ? Math.round((actual.calories / target) * 100) : 0;
    // Перебор показываем цветом, а не полосой длиннее круга: круг всё равно
    // замкнётся, и человек решит, что всё ровно.
    const over = left !== null && left < 0;
    return (
      <div className="relative shrink-0" style={{ width: 96, height: 96 }}>
        <svg width="96" height="96" viewBox="0 0 96 96" className="-rotate-90">
          <circle cx="48" cy="48" r={r} fill="none" stroke="#E2E6E2" strokeWidth="11" />
          <circle cx="48" cy="48" r={r} fill="none" stroke={over ? OVER_COLOR : '#7CB342'}
                  strokeWidth="11" strokeLinecap="round" strokeDasharray={`${ratio * c} ${c}`} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-tight">
          <span className="text-xl font-bold text-chocolate">{pct}%</span>
          <span className="text-[10px] text-gray-500">от цели</span>
        </div>
      </div>
    );
  };

  const macroLine = (label: string, key: 'proteins' | 'fats' | 'carbs', targetG: number | null) => {
    const a = actual[key];
    const p = planned[key];
    const share = macroKcal > 0 ? Math.round((a * KCAL_PER_GRAM[key] / macroKcal) * 100) : null;
    // Полоса мерится нормой, если она есть; иначе планом — хоть какой-то
    // масштаб. Нет ни того, ни другого — полоса просто пустая.
    const scale = targetG && targetG > 0 ? targetG : (p > 0 ? p : 0);
    const part = (v: number) => (scale > 0 ? Math.min(100, (v / scale) * 100) : 0);
    // Перебор считается только от нормы: план меню нормой не является, и
    // «съел больше, чем планировал» — не повод тревожить человека.
    const over = !!targetG && targetG > 0 && a > targetG;
    const fill = over ? OVER_COLOR : MACRO_COLORS[key];
    return (
      <div key={key} className="mt-3">
        <div className="flex items-baseline gap-2 text-sm">
          <span className="w-24 text-chocolate">{label}</span>
          {share !== null && <span className="text-xs text-gray-500">{share}% калорий</span>}
          <span className="ml-auto text-xs text-gray-500">
            {targetG ? `${grams(a)} / ${grams(targetG)} г` : `${grams(a)} г`}
          </span>
        </div>
        <div className="mt-1 h-[7px] rounded-full bg-rice overflow-hidden relative">
          {/* Бледным — запланированное, плотным — съеденное. */}
          <div className="absolute inset-y-0 left-0 rounded-full"
               style={{ width: `${part(Math.max(a, p))}%`, backgroundColor: fill, opacity: 0.28 }} />
          <div className="absolute inset-y-0 left-0 rounded-full"
               style={{ width: `${part(a)}%`, backgroundColor: fill }} />
        </div>
      </div>
    );
  };

  const tile = (title: string, value: string) => (
    <div className="rounded-xl bg-rice px-3 py-2 flex-1 min-w-[120px]">
      <div className="text-xs text-gray-500">{title}</div>
      <div className="text-sm font-semibold text-chocolate">{value}</div>
    </div>
  );

  return (
    <div className="space-y-4">
      <Card className="p-4">
        {target === null ? (
          // Нормы нет — вместо кольца приглашение её посчитать. Съеденное всё
          // равно показываем: это честное число, и от нормы оно не зависит.
          <div>
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold text-chocolate">{thousands(actual.calories)}</span>
              <span className="text-sm text-gray-500 pb-1">ккал съедено</span>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              Цель по калориям не задана — не с чем сравнивать.
            </p>
            <Link to="/profile/kbju-calculator"
                  className="inline-block mt-2 text-sm text-avocado hover:underline">
              Посчитать
            </Link>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            {ring()}
            <div>
              <div className="text-3xl font-bold text-chocolate leading-tight">
                {thousands(actual.calories)}
              </div>
              <div className="text-sm text-gray-500">
                съедено из {thousands(target)} ккал
              </div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-2xl font-bold"
                   style={{ color: left! < 0 ? OVER_COLOR : '#7CB342' }}>
                {left! >= 0 ? thousands(left!) : `+${thousands(-left!)}`}
              </div>
              <div className="text-sm text-gray-500">{left! >= 0 ? 'осталось' : 'перебор'}</div>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4">
        <div className="text-sm font-semibold text-chocolate">Белки, жиры, углеводы</div>
        {macroLine('Белки', 'proteins', num(profile?.protein_target_g))}
        {macroLine('Жиры', 'fats', num(profile?.fat_target_g))}
        {macroLine('Углеводы', 'carbs', num(profile?.carb_target_g))}
        {planned.calories > actual.calories && (
          <p className="text-xs text-gray-500 mt-3">
            Бледным — запланированное, но ещё не отмеченное съеденным.
          </p>
        )}
      </Card>

      <Card className="p-4">
        <div className="text-sm font-semibold text-chocolate mb-1">По приёмам</div>
        {meals.rows.map(({ slot, kcal }) => (
          <div key={slot} className="mt-3 flex items-center gap-3">
            <span className="w-24 text-sm text-chocolate shrink-0">{MEAL_SLOT_LABELS[slot]}</span>
            <div className="flex-1 h-2 rounded-full bg-rice overflow-hidden">
              <div className="h-full"
                   style={{
                     width: `${meals.scale > 0 ? Math.min(100, (kcal / meals.scale) * 100) : 0}%`,
                     // Один приём съел дневную норму целиком — это тот же
                     // перебор, и цвет тот же, что у кольца.
                     backgroundColor: meals.norm && kcal > meals.norm ? OVER_COLOR : '#7CB342',
                   }} />
            </div>
            <span className="w-24 text-right text-xs text-gray-500 shrink-0">
              {kcal > 0 ? `${thousands(kcal)} ккал` : '—'}
            </span>
          </div>
        ))}
      </Card>

      <Card className="p-4">
        <div className="text-sm font-semibold text-chocolate mb-3">Прочее за день</div>
        <div className="flex flex-wrap gap-3">
          {tile('Вода', waterMl === 0 ? '—' : `${thousands(waterMl)} мл`)}
          {tile('Вес', weight === null ? '—' : `${weight} кг`)}
          {/* Потраченное на занятиях. Отдельной плиткой и без знака «минус»: на
              остаток калорий оно не влияет. */}
          {tile('Потрачено', burned === 0 ? '—' : `${thousands(burned)} ккал`)}
        </div>
      </Card>
    </div>
  );
};
