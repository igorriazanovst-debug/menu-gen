// DIARY_V2
import React, { useCallback, useEffect, useState } from 'react';
import { diaryApi } from '../../api/diary';
import { familyApi } from '../../api/family';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import { AddDiaryEntryModal } from '../../components/diary/AddDiaryEntryModal';
import { ImportMenuModal } from '../../components/diary/ImportMenuModal';
import { CopyFromDayModal } from '../../components/diary/CopyFromDayModal'; // DIARY_COPY_V3
import { PrintDiaryModal } from '../../components/diary/PrintDiaryModal'; // DIARY_HIER_PRINT_V5
import { getErrorMessage } from '../../utils/api';
import { MEAL_LABELS } from '../../types';
import type { DiaryEntry, DiaryDayStats, FamilyMember, MealType } from '../../types';

const today = () => new Date().toISOString().split('T')[0];
const WATER_GOAL_ML = 2000;
const WATER_STEPS = [250, 500];

// DIARY_MULTIDAY: сдвиг ISO-даты на N дней (без таймзонных сюрпризов).
const addDays = (iso: string, n: number): string => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
};

// DIARY_MULTIDAY: относительная подпись секции дня.
type DayRel = 'today' | 'yesterday' | 'tomorrow' | 'other';
const dayLabel = (iso: string): { label: string; rel: DayRel } => {
  const t = today();
  if (iso === t) return { label: 'Сегодня', rel: 'today' };
  if (iso === addDays(t, -1)) return { label: 'Вчера', rel: 'yesterday' };
  if (iso === addDays(t, 1)) return { label: 'Завтра', rel: 'tomorrow' };
  const d = new Date(`${iso}T00:00:00`);
  const s = d.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' });
  return { label: s.charAt(0).toUpperCase() + s.slice(1), rel: 'other' };
};

const emptyBucket = { calories: 0, proteins: 0, fats: 0, carbs: 0 };

const StatBox: React.FC<{ label: string; planned: number; actual: number; unit: string }> =
({ label, planned, actual, unit }) => (
  <div className="rounded-xl bg-rice px-3 py-2">
    <div className="text-xs text-gray-500">{label}</div>
    <div className="text-sm font-semibold text-chocolate">
      {Math.round(actual)}<span className="text-xs font-normal text-gray-400"> / {Math.round(planned)} {unit}</span>
    </div>
  </div>
);

// DIARY_CHART: круговая диаграмма «факт/план» по калориям (SVG-кольцо, без зависимостей).
const CalorieDonut: React.FC<{ fact: number; plan: number }> = ({ fact, plan }) => {
  const r = 34;
  const c = 2 * Math.PI * r;
  const ratio = plan > 0 ? Math.min(1, Math.max(0, fact / plan)) : (fact > 0 ? 1 : 0);
  const pct = plan > 0 ? Math.round((fact / plan) * 100) : null;
  return (
    <div className="relative shrink-0" style={{ width: 88, height: 88 }}>
      <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
        <circle cx="44" cy="44" r={r} fill="none" stroke="#F26B5E33" strokeWidth="8" />
        <circle cx="44" cy="44" r={r} fill="none" stroke="#F26B5E" strokeWidth="8"
          strokeLinecap="round" strokeDasharray={`${ratio * c} ${c}`} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-tight">
        <span className="text-sm font-bold text-tomato">{Math.round(fact)}</span>
        <span className="text-[10px] text-gray-400">/ {plan > 0 ? Math.round(plan) : '—'} ккал</span>
        {pct !== null && <span className="text-[10px] text-gray-400">{pct}%</span>}
      </div>
    </div>
  );
};

export const DiaryPage: React.FC = () => {
  const [date, setDate] = useState(today());
  const [memberId, setMemberId] = useState<number | undefined>(undefined);
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [isHead, setIsHead] = useState(false);

  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [stats, setStats] = useState<DiaryDayStats | null>(null);
  const [waterMl, setWaterMl] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showCopy, setShowCopy] = useState(false); // DIARY_COPY_V3
  const [showPrint, setShowPrint] = useState(false); // DIARY_HIER_PRINT_V5
  // DIARY_HIER_PRINT_V5 / DIARY_MULTIDAY: per-(date|meal) open state, ключ "<дата>|<meal>".
  const [openMeals, setOpenMeals] = useState<Set<string>>(new Set());
  const [customWater, setCustomWater] = useState('');

  // Family (for member switcher; HEAD only).
  useEffect(() => {
    familyApi.get()
      .then(({ data }) => {
        setMembers(data.members ?? []);
        const me = data.members?.find((m) => m.role === 'head' || m.role === 'owner');
        setIsHead(!!me);
      })
      .catch(() => { /* non-fatal */ });
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      // DIARY_MULTIDAY: грузим записи диапазоном вокруг выбранной (anchor) даты.
      const [e, s, w] = await Promise.all([
        diaryApi.list({ from: addDays(date, -7), to: addDays(date, 30), page_size: 1000, member_id: memberId }),
        diaryApi.stats(date, date, memberId).catch(() => [] as DiaryDayStats[]),
        diaryApi.getWater(date).catch(() => ({ date, water_ml: 0 })),
      ]);
      setEntries(e);
      setStats(s[0] ?? { date, planned: emptyBucket, actual: emptyBucket, total: emptyBucket });
      setWaterMl(w.water_ml ?? 0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [date, memberId]);

  useEffect(() => { load(); }, [load]);

  const toggleEaten = async (e: DiaryEntry) => {
    const next = !e.is_eaten;
    // Optimistic: update just this entry so the open/closed sections don't reset.
    setEntries((prev) => prev.map((x) => (x.id === e.id ? { ...x, is_eaten: next } : x)));
    try {
      await diaryApi.patch(e.id, { is_eaten: next });
      // Refresh stats only (entries already reflect the change).
      const s = await diaryApi.stats(date, date, memberId).catch(() => [] as DiaryDayStats[]);
      setStats(s[0] ?? { date, planned: emptyBucket, actual: emptyBucket, total: emptyBucket });
    } catch (err) {
      // Revert on failure.
      setEntries((prev) => prev.map((x) => (x.id === e.id ? { ...x, is_eaten: !next } : x)));
      alert(getErrorMessage(err));
    }
  };

  const remove = async (e: DiaryEntry) => {
    if (!window.confirm('Удалить запись?')) return;
    try {
      await diaryApi.remove(e.id);
      load();
    } catch (err) { alert(getErrorMessage(err)); }
  };

  const addWater = async (ml: number) => {
    const next = Math.max(0, waterMl + ml);
    setWaterMl(next); // optimistic
    try { await diaryApi.setWater(date, next); }
    catch (err) { setWaterMl(waterMl); alert(getErrorMessage(err)); }
  };

  const setWaterExact = async () => {
    const v = parseInt(customWater, 10);
    if (!Number.isFinite(v) || v < 0) return;
    setCustomWater('');
    setWaterMl(v);
    try { await diaryApi.setWater(date, v); }
    catch (err) { setWaterMl(waterMl); alert(getErrorMessage(err)); }
  };

  // DIARY_COPY_V3: plan = is_planned OR legacy planned_menu_item.
  const isPlan = (e: DiaryEntry) => e.is_planned === true || e.planned_menu_item != null;

  // DIARY_HIER_PRINT_V5: group a day's entries by meal type for hierarchical view.
  const MEAL_ORDER: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack'];
  const mealGroupsFor = (items: DiaryEntry[]) =>
    MEAL_ORDER
      .map((mt) => ({ mt, items: items.filter((e) => e.meal_type === mt) }))
      .filter((g) => g.items.length > 0);

  // DIARY_MULTIDAY: записи сгруппированы по дате; anchor-дата видна всегда.
  const byDate = new Map<string, DiaryEntry[]>();
  for (const e of entries) {
    const arr = byDate.get(e.date);
    if (arr) arr.push(e); else byDate.set(e.date, [e]);
  }
  if (!byDate.has(date)) byDate.set(date, []);
  const sortedDates = Array.from(byDate.keys()).sort();
  // DIARY_HIER_PRINT_V5: read a nutrition field that may be flat (number) or {value,unit}.
  const nutriVal = (e: DiaryEntry, key: 'calories' | 'proteins' | 'fats' | 'carbs'): number => {
    const raw = (e.nutrition as Record<string, unknown> | undefined)?.[key];
    let n = 0;
    if (typeof raw === 'number') n = raw;
    else if (typeof raw === 'string') n = parseFloat(raw);
    else if (raw && typeof raw === 'object' && 'value' in (raw as object)) {
      n = parseFloat(String((raw as { value: unknown }).value));
    }
    return Number.isFinite(n) ? n * (e.quantity ?? 1) : 0;
  };
  const mealKcal = (items: DiaryEntry[]) =>
    Math.round(items.reduce((sum, e) => sum + nutriVal(e, 'calories'), 0));

  const Entry: React.FC<{ e: DiaryEntry; canCheck: boolean }> = ({ e, canCheck }) => (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {canCheck ? (
            <input type="checkbox" checked={e.is_eaten} onChange={() => toggleEaten(e)}
                   className="w-5 h-5 accent-tomato cursor-pointer" />
          ) : (
            <span className="text-green-500 text-lg">✓</span>
          )}
          <div className="min-w-0">
            <span className="text-xs text-gray-400 uppercase tracking-wide">
              {MEAL_LABELS[e.meal_type] ?? e.meal_type}
            </span>
            <p className="font-medium text-chocolate mt-0.5 truncate">
              {e.recipe_title ?? e.custom_name ?? 'Без названия'}
              {e.quantity !== 1 && <span className="text-gray-400"> ×{e.quantity}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {nutriVal(e, 'calories') > 0 && (
            <span className="text-sm text-gray-500 whitespace-nowrap">
              {Math.round(nutriVal(e, 'calories'))} ккал
            </span>
          )}
          <button onClick={() => remove(e)} className="text-gray-400 hover:text-red-600 text-sm" title="Удалить">🗑</button>
        </div>
      </div>
    </Card>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-chocolate">Дневник питания</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => setShowPrint(true)}>🖨 Печать</Button>
          <Button variant="ghost" onClick={() => setShowCopy(true)}>📋 Копировать</Button>
          <Button variant="ghost" onClick={() => setShowImport(true)}>📥 Заполнить из меню</Button>
          <Button onClick={() => setShowAdd(true)}>＋ Добавить</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input type="date" value={date} max={today()}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none" />
        {isHead && members.length > 1 && (
          <select value={memberId ?? ''} onChange={(e) => setMemberId(e.target.value ? Number(e.target.value) : undefined)}
            className="rounded-xl border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none">
            <option value="">Я</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Stats card (план / факт) — DIARY_CHART: кольцо калорий + макросы */}
      {stats && (
        <Card className="p-4">
          <div className="text-sm font-semibold text-chocolate mb-3">Итог за день (факт / план)</div>
          <div className="flex items-center gap-4">
            <CalorieDonut fact={stats.actual.calories} plan={stats.planned.calories} />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 flex-1">
              <StatBox label="Белки" planned={stats.planned.proteins} actual={stats.actual.proteins} unit="г" />
              <StatBox label="Жиры" planned={stats.planned.fats} actual={stats.actual.fats} unit="г" />
              <StatBox label="Углеводы" planned={stats.planned.carbs} actual={stats.actual.carbs} unit="г" />
            </div>
          </div>
        </Card>
      )}

      {/* Water tracker */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-chocolate">💧 Вода</div>
          <div className="text-sm text-gray-500">
            {waterMl} / {WATER_GOAL_ML} мл
          </div>
        </div>
        <div className="h-2 rounded-full bg-rice overflow-hidden mb-3">
          <div className="h-full bg-tomato transition-all"
               style={{ width: `${Math.min(100, (waterMl / WATER_GOAL_ML) * 100)}%` }} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {WATER_STEPS.map((ml) => (
            <Button key={ml} variant="ghost" onClick={() => addWater(ml)}>+{ml} мл</Button>
          ))}
          <Button variant="ghost" onClick={() => addWater(-250)} disabled={waterMl <= 0}>−250 мл</Button>
          <div className="flex items-center gap-2 ml-auto">
            <input type="number" value={customWater} min="0"
              onChange={(e) => setCustomWater(e.target.value)}
              placeholder="мл"
              className="w-24 rounded-xl border border-gray-300 px-3 py-1.5 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none" />
            <Button variant="ghost" onClick={setWaterExact} disabled={!customWater}>Задать</Button>
          </div>
        </div>
      </Card>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {/* DIARY_MULTIDAY: многодневная лента — секции по датам (Сегодня/Вчера/Завтра + дата). */}
      {loading ? <PageSpinner /> : (
        <div className="space-y-5">
          {sortedDates.map((d) => {
            const dayEntries = byDate.get(d) ?? [];
            const { label, rel } = dayLabel(d);
            const groups = mealGroupsFor(dayEntries);
            const dayKcal = dayEntries.reduce((sum, e) => sum + nutriVal(e, 'calories'), 0);
            const sub = new Date(`${d}T00:00:00`).toLocaleDateString('ru', { day: 'numeric', month: 'long' });
            const headerCls =
              rel === 'today' ? 'bg-tomato/10 ring-1 ring-tomato/30'
              : rel === 'yesterday' || rel === 'tomorrow' ? 'bg-tomato/5'
              : 'bg-rice';
            return (
              <div key={d} className="space-y-2">
                <div className={`flex items-center justify-between rounded-xl px-3 py-2 ${headerCls}`}>
                  <div className="flex items-baseline gap-2 min-w-0">
                    <span className={`font-semibold ${rel === 'today' ? 'text-tomato' : 'text-chocolate'}`}>{label}</span>
                    {rel !== 'other' && <span className="text-xs text-gray-500 truncate">{sub}</span>}
                  </div>
                  {dayKcal > 0 && <span className="text-sm text-gray-500 whitespace-nowrap">{Math.round(dayKcal)} ккал</span>}
                </div>

                {groups.length === 0 ? (
                  <p className="text-sm text-gray-400 px-3">Нет записей</p>
                ) : groups.map((g) => {
                  const key = `${d}|${g.mt}`;
                  return (
                    <details key={key} open={openMeals.has(key)}
                      onToggle={(ev) => {
                        const isOpen = (ev.target as HTMLDetailsElement).open;
                        setOpenMeals((prev) => {
                          const n = new Set(prev);
                          if (isOpen) n.add(key); else n.delete(key);
                          return n;
                        });
                      }}
                      className="rounded-2xl border border-border bg-surface overflow-hidden">
                      <summary className="cursor-pointer select-none px-4 py-3 flex items-center justify-between">
                        <span className="font-semibold text-chocolate">
                          {MEAL_LABELS[g.mt] ?? g.mt}
                          <span className="text-gray-400 font-normal"> · {g.items.length}</span>
                        </span>
                        <span className="text-sm text-gray-500">{mealKcal(g.items)} ккал</span>
                      </summary>
                      <div className="px-3 pb-3 space-y-2">
                        {g.items.map((e) => <Entry key={e.id} e={e} canCheck={isPlan(e)} />)}
                      </div>
                    </details>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {showAdd && (
        <AddDiaryEntryModal date={date} memberId={memberId}
          onClose={() => setShowAdd(false)} onAdded={load} />
      )}
      {showImport && (
        <ImportMenuModal date={date} memberId={memberId}
          onClose={() => setShowImport(false)}
          onImported={(startDate) => {
            // DIARY_MULTIDAY: перецентрируем ленту на дату старта импорта.
            if (startDate && startDate !== date) setDate(startDate);
            else load();
          }} />
      )}
      {showCopy && (
        <CopyFromDayModal targetDate={date} memberId={memberId}
          onClose={() => setShowCopy(false)} onCopied={load} />
      )}
      {showPrint && (
        <PrintDiaryModal date={date} memberId={memberId}
          onClose={() => setShowPrint(false)} />
      )}
    </div>
  );
};
