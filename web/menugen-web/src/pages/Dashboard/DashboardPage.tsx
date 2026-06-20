// MG_SKIN: dashboard redesign — health-tracker layout (.Diet reference).
// Все цвета через семантические токены (bg-surface, text-muted, bg-primary…),
// поэтому оба скина работают автоматически.
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { diaryApi } from '../../api/diary';
import { Card } from '../../components/ui/Card';
import { Ring } from '../../components/ui/Ring';
import { PageSpinner } from '../../components/ui/Spinner';
import { MEAL_LABELS } from '../../types';
import type { DiaryEntry, DiaryDayStats, MealType } from '../../types';

const WATER_GOAL_ML = 2000;
const MEAL_ORDER: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack'];
const WEEKDAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

const iso = (d: Date) => d.toISOString().split('T')[0];
const emptyBucket = { calories: 0, proteins: 0, fats: 0, carbs: 0 };

// Калории одной записи дневника (nutrition может быть number | {value}).
const entryKcal = (e: DiaryEntry): number => {
  const raw = (e.nutrition as Record<string, unknown> | undefined)?.calories;
  let n = 0;
  if (typeof raw === 'number') n = raw;
  else if (typeof raw === 'string') n = parseFloat(raw);
  else if (raw && typeof raw === 'object' && 'value' in (raw as object)) {
    n = parseFloat(String((raw as { value: unknown }).value));
  }
  return Number.isFinite(n) ? n * (e.quantity ?? 1) : 0;
};

export const DashboardPage: React.FC = () => {
  const user = useAppSelector((s) => s.auth.user);

  const [stats7, setStats7] = useState<DiaryDayStats[]>([]);
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [waterMl, setWaterMl] = useState(0);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);

  const today = useMemo(() => new Date(), []);
  const todayStr = iso(today);

  useEffect(() => {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    Promise.allSettled([
      diaryApi.stats(iso(from), todayStr).then((s) => setStats7(s)),
      diaryApi.list({ date: todayStr }).then((e) => setEntries(e)),
      diaryApi.getWater(todayStr).then((w) => setWaterMl(w.water_ml ?? 0)),
    ]).finally(() => setLoading(false));
  }, [today, todayStr]);

  // Цели из профиля (targets_calculated → плоские поля → 0).
  const p = user?.profile;
  const targets = {
    calories: Number(p?.calorie_target ?? p?.targets_calculated?.calorie_target ?? 0),
    proteins: Number(p?.protein_target_g ?? p?.targets_calculated?.protein_target_g ?? 0),
    fats:     Number(p?.fat_target_g ?? p?.targets_calculated?.fat_target_g ?? 0),
    carbs:    Number(p?.carb_target_g ?? p?.targets_calculated?.carb_target_g ?? 0),
  };

  const todayStats = stats7.find((s) => s.date === todayStr);
  const actual = todayStats?.actual ?? emptyBucket;
  const consumed = Math.round(actual.calories);
  const remaining = Math.max(0, Math.round(targets.calories - actual.calories));
  const budgetPct = targets.calories > 0 ? actual.calories / targets.calories : 0;

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <DashboardHeader name={user?.name} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Левая зона (2/3) */}
        <div className="space-y-6 xl:col-span-2">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <PromoCard />
            <ActivityCard stats={stats7} todayStr={todayStr} consumed={consumed} />
          </div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <DailyRecap actual={actual} targets={targets} />
            <DailyCalories entries={entries} remaining={remaining} hasTarget={targets.calories > 0} />
          </div>
        </div>

        {/* Правая зона (1/3) */}
        <div className="space-y-6">
          <CalendarCard offset={weekOffset} setOffset={setWeekOffset} today={today} />
          <CaloriesBudget consumed={consumed} target={targets.calories} pct={budgetPct} remaining={remaining} />
          <WaterCard waterMl={waterMl} setWaterMl={setWaterMl} date={todayStr} />
        </div>
      </div>
    </div>
  );
};

// ── Header ──────────────────────────────────────────────────────────────────
const DashboardHeader: React.FC<{ name?: string }> = ({ name }) => (
  <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
    <div>
      <h1 className="text-2xl font-bold text-text">
        Привет, {name ?? 'друг'} <span aria-hidden>🌱</span>
      </h1>
      <p className="mt-1 text-sm text-muted">Начнём жить здорово — прямо сейчас</p>
    </div>
    <div className="flex items-center gap-3">
      <label className="relative flex-1 lg:w-72">
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted">🔍</span>
        <input
          type="search"
          placeholder="Поиск рецептов, продуктов…"
          className="w-full rounded-2xl border border-border bg-surface py-2.5 pl-10 pr-4 text-sm text-text placeholder:text-muted outline-none focus:ring-2 focus:ring-primary/40"
        />
      </label>
      <Link
        to="/diary"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sidebar text-sidebar-fg transition hover:opacity-90"
        title="Дневник"
      >
        🔔
      </Link>
    </div>
  </header>
);

// ── Promo / challenge ─────────────────────────────────────────────────────────
const PromoCard: React.FC = () => (
  <Card className="relative flex min-h-[180px] flex-col justify-between overflow-hidden border-0 bg-gradient-to-br from-primary/25 via-primary/10 to-accent/15 p-6">
    <div className="relative z-10 max-w-[70%]">
      <h3 className="text-xl font-bold leading-snug text-text">
        Меню на 5 дней <span aria-hidden>🔥</span>
      </h3>
      <p className="mt-1 text-sm text-muted">
        Соберём здоровое меню под ваши цели за пару минут
      </p>
    </div>
    <Link
      to="/menu"
      className="relative z-10 flex h-11 w-11 items-center justify-center rounded-full bg-surface text-lg text-primary shadow-sm transition hover:bg-primary hover:text-primary-fg"
      title="Перейти к меню"
    >
      →
    </Link>
    <div className="pointer-events-none absolute -bottom-2 right-2 select-none text-[6rem] leading-none opacity-90">
      🥗
    </div>
  </Card>
);

// ── Daily activity (недельный тренд калорий) ──────────────────────────────────
const ActivityCard: React.FC<{ stats: DiaryDayStats[]; todayStr: string; consumed: number }> = ({
  stats, todayStr, consumed,
}) => {
  // Нормализуем последние 7 дней калорий в полилинию.
  const series = stats.map((s) => s.actual?.calories ?? 0);
  const max = Math.max(1, ...series, ...stats.map((s) => s.planned?.calories ?? 0));
  const W = 300;
  const H = 90;
  const points = (values: number[]) =>
    values
      .map((v, i) => {
        const x = values.length > 1 ? (i / (values.length - 1)) * W : W / 2;
        const y = H - (v / max) * H;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

  const planned = stats.map((s) => s.planned?.calories ?? 0);

  return (
    <Card className="flex flex-col justify-between border-0 bg-sidebar p-6 text-sidebar-fg">
      <div>
        <h3 className="text-lg font-bold">Активность за неделю</h3>
        <p className="mt-1 text-sm text-sidebar-muted">{consumed} ккал сегодня</p>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 h-24 w-full" preserveAspectRatio="none">
        {series.length > 1 && (
          <>
            <polyline
              points={points(planned)} fill="none"
              className="stroke-accent" strokeWidth={3}
              strokeLinecap="round" strokeLinejoin="round" opacity={0.6}
            />
            <polyline
              points={points(series)} fill="none"
              className="stroke-primary" strokeWidth={3}
              strokeLinecap="round" strokeLinejoin="round"
            />
          </>
        )}
        {series.length <= 1 && (
          <text x={W / 2} y={H / 2} textAnchor="middle" className="fill-sidebar-muted text-[12px]">
            Нет данных дневника
          </text>
        )}
      </svg>
      <div className="mt-2 flex items-center justify-between text-xs text-sidebar-muted">
        <span>7 дней назад</span>
        <span>{new Date(todayStr).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}</span>
      </div>
    </Card>
  );
};

// ── Daily recap (макросы) ─────────────────────────────────────────────────────
const DailyRecap: React.FC<{
  actual: { proteins: number; fats: number; carbs: number };
  targets: { proteins: number; fats: number; carbs: number };
}> = ({ actual, targets }) => {
  const rows = [
    { label: 'Углеводы', g: actual.carbs, target: targets.carbs, tile: 'bg-secondary/15 text-secondary' },
    { label: 'Белки', g: actual.proteins, target: targets.proteins, tile: 'bg-accent/20 text-accent' },
    { label: 'Жиры', g: actual.fats, target: targets.fats, tile: 'bg-primary/15 text-primary' },
  ];
  return (
    <Card className="p-6">
      <h3 className="mb-4 text-lg font-bold text-text">Итог по БЖУ</h3>
      <div className="space-y-4">
        {rows.map((r) => {
          const pct = r.target > 0 ? Math.min(100, Math.round((r.g / r.target) * 100)) : 0;
          return (
            <div key={r.label} className="flex items-center gap-3">
              <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${r.tile}`}>
                {Math.round(r.g)}<span className="text-[10px] font-medium">г</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted">{r.label}</span>
                  <span className="font-semibold text-text">{r.target > 0 ? `${pct}%` : '—'}</span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-alt">
                  <div className="h-full rounded-full bg-text transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

// ── Daily calories (приёмы пищи) ──────────────────────────────────────────────
const DailyCalories: React.FC<{ entries: DiaryEntry[]; remaining: number; hasTarget: boolean }> = ({
  entries, remaining, hasTarget,
}) => {
  const meals = MEAL_ORDER
    .map((mt) => {
      const items = entries.filter((e) => e.meal_type === mt);
      return {
        mt,
        kcal: Math.round(items.reduce((s, e) => s + entryKcal(e), 0)),
        names: items.map((e) => e.recipe_title ?? e.custom_name).filter(Boolean).slice(0, 2).join(', '),
        count: items.length,
      };
    })
    .filter((m) => m.count > 0);

  const tiles: Record<MealType, string> = {
    breakfast: 'bg-secondary/10',
    lunch: 'bg-accent/15',
    dinner: 'bg-primary/10',
    snack: 'bg-surface-alt',
  };

  return (
    <Card className="flex flex-col p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-bold text-text">Приёмы пищи</h3>
        <Link to="/diary" className="text-sm text-primary hover:underline">Дневник →</Link>
      </div>

      {meals.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center py-6 text-center">
          <div className="text-4xl">🍽</div>
          <p className="mt-2 text-sm text-muted">Сегодня записей ещё нет</p>
          <Link
            to="/diary"
            className="mt-3 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-fg transition hover:opacity-90"
          >
            Добавить приём
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {meals.map((m) => (
            <Link
              key={m.mt}
              to="/diary"
              className={`flex items-center justify-between rounded-2xl px-4 py-3 transition hover:opacity-90 ${tiles[m.mt]}`}
            >
              <div className="min-w-0">
                <p className="font-semibold text-text">{MEAL_LABELS[m.mt]}</p>
                {m.names && <p className="truncate text-xs text-muted">{m.names}</p>}
              </div>
              <span className="shrink-0 text-sm font-semibold text-text">{m.kcal} ккал</span>
            </Link>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
        <span className="text-sm text-muted">Осталось</span>
        <span className="text-sm font-semibold text-text">
          {hasTarget ? `${remaining} ккал` : 'задайте цель в профиле'}
        </span>
      </div>
    </Card>
  );
};

// ── Calendar (текущая неделя) ─────────────────────────────────────────────────
const CalendarCard: React.FC<{ offset: number; setOffset: (n: number) => void; today: Date }> = ({
  offset, setOffset, today,
}) => {
  const base = new Date(today);
  base.setDate(base.getDate() + offset * 7);
  const sunday = new Date(base);
  sunday.setDate(base.getDate() - base.getDay());
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(sunday);
    d.setDate(sunday.getDate() + i);
    return d;
  });
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  const monthLabel = base.toLocaleDateString('ru', { month: 'long', year: 'numeric' });

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-bold capitalize text-text">{monthLabel}</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setOffset(offset - 1)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition hover:bg-surface-alt hover:text-text"
            aria-label="Предыдущая неделя"
          >‹</button>
          <button
            onClick={() => setOffset(offset + 1)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition hover:bg-surface-alt hover:text-text"
            aria-label="Следующая неделя"
          >›</button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAYS.map((w) => (
          <div key={w} className="text-xs font-medium text-muted">{w}</div>
        ))}
        {days.map((d) => {
          const isToday = sameDay(d, today);
          return (
            <div
              key={d.toISOString()}
              className={[
                'mx-auto flex h-9 w-9 items-center justify-center rounded-xl text-sm transition',
                isToday ? 'bg-primary font-bold text-primary-fg' : 'text-text hover:bg-surface-alt',
              ].join(' ')}
            >
              {d.getDate()}
            </div>
          );
        })}
      </div>
    </Card>
  );
};

// ── Calories budget (кольцо) ──────────────────────────────────────────────────
const CaloriesBudget: React.FC<{ consumed: number; target: number; pct: number; remaining: number }> = ({
  consumed, target, pct, remaining,
}) => (
  <Card className="flex flex-col items-center p-6">
    <h3 className="mb-4 self-start text-lg font-bold text-text">Бюджет калорий</h3>
    <Ring value={pct} size={180} stroke={16} trackClass="stroke-surface-alt">
      <span className="text-3xl font-bold text-text">{consumed}</span>
      <span className="text-xs text-muted">съедено, ккал</span>
    </Ring>
    <div className="mt-4 flex w-full items-center justify-between text-sm">
      <span className="text-muted">Цель</span>
      <span className="font-semibold text-text">{target > 0 ? `${target} ккал` : '—'}</span>
    </div>
    {target > 0 && (
      <div className="mt-1 flex w-full items-center justify-between text-sm">
        <span className="text-muted">Осталось</span>
        <span className="font-semibold text-primary">{remaining} ккал</span>
      </div>
    )}
  </Card>
);

// ── Water tracker ─────────────────────────────────────────────────────────────
const WaterCard: React.FC<{ waterMl: number; setWaterMl: (n: number) => void; date: string }> = ({
  waterMl, setWaterMl, date,
}) => {
  const pct = Math.min(1, waterMl / WATER_GOAL_ML);
  const addWater = async (ml: number) => {
    const next = Math.max(0, waterMl + ml);
    setWaterMl(next); // optimistic
    try { await diaryApi.setWater(date, next); }
    catch { setWaterMl(waterMl); }
  };

  return (
    <Card className="flex items-center gap-5 bg-gradient-to-br from-secondary/15 to-primary/10 p-6">
      <Ring value={pct} size={92} stroke={10} colorClass="stroke-primary" trackClass="stroke-surface">
        <span className="text-sm font-bold text-text">{Math.round(pct * 100)}%</span>
      </Ring>
      <div className="flex-1">
        <h3 className="font-bold leading-snug text-text">Питьевой режим</h3>
        <p className="mt-0.5 text-xs text-muted">{waterMl} / {WATER_GOAL_ML} мл</p>
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => addWater(250)}
            className="rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-fg transition hover:opacity-90"
          >
            +250 мл
          </button>
          <button
            onClick={() => addWater(-250)}
            disabled={waterMl <= 0}
            className="rounded-xl border border-border px-3 py-1.5 text-xs font-semibold text-text transition hover:bg-surface-alt disabled:opacity-40"
          >
            −250 мл
          </button>
        </div>
      </div>
    </Card>
  );
};
