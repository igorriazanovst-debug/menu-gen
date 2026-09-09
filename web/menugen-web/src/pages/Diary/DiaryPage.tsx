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
import { EditDiaryEntryModal } from '../../components/diary/EditDiaryEntryModal';
import { AddedByMark } from '../../components/diary/AddedByMark'; // MG_HEADKEEPS
import { MeasurementsCard } from './MeasurementsCard'; // MG_BODYSIZE
import { PrintDiaryModal } from '../../components/diary/PrintDiaryModal'; // DIARY_HIER_PRINT_V5
import { getErrorMessage } from '../../utils/api';
import {
  MEAL_SLOT_LABELS, MEAL_SLOT_ORDER, MEAL_SLOTS_BY_PLAN, MEAL_SLOT_COLORS,
} from '../../types';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { WeightCard } from './WeightCard'; // MG_TRAINER
import { todayIso } from '../../utils/isoDate'; // ISO_DATE_V1
import { dayTotalsHint } from '../../utils/dayTotalsHint'; // DIARY_TOTALS_V1
import { allEaten, toMark } from '../../utils/markEaten'; // DIARY_EATALL_V1
import type { DiaryEntry, DiaryDayStats, DiaryWaterLog, FamilyMember, MealSlot } from '../../types';

const today = todayIso; // ISO_DATE_V1: локальный календарь, а не UTC
const WATER_GOAL_ML = 2000;
const WATER_STEPS = [250, 500];


const emptyBucket = { calories: 0, proteins: 0, fats: 0, carbs: 0 };

const StatBox: React.FC<{ label: string; planned: number; actual: number; unit: string }> =
({ label, planned, actual, unit }) => (
  <div className="rounded-xl bg-rice px-3 py-2">
    <div className="text-xs text-gray-500">{label}</div>
    <div className="text-sm font-semibold text-chocolate">
      {Math.round(actual)}<span className="text-xs font-normal text-gray-500"> / {Math.round(planned)} {unit} по плану</span>
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
        <span className="text-[10px] text-gray-500">/ {plan > 0 ? Math.round(plan) : '—'} ккал</span>
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
  // MG_HEADKEEPS: кто поставил текущее значение воды. Пусто — сам человек.
  const [waterBy, setWaterBy] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false); // DIARY_EATALL_V1
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showCopy, setShowCopy] = useState(false); // DIARY_COPY_V3
  const [showPrint, setShowPrint] = useState(false); // DIARY_HIER_PRINT_V5
  const [editing, setEditing] = useState<DiaryEntry | null>(null); // MG_DIARYEDIT
  // DIARY_HIER_PRINT_V5 / DIARY_MULTIDAY: per-(date|meal) open state, ключ "<дата>|<meal>".
  const [openMeals, setOpenMeals] = useState<Set<string>>(new Set());
  const [customWater, setCustomWater] = useState('');
  const authUserId = useAppSelector((s) => s.auth.user?.id);

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
      // DIARY: грузим записи только за выбранный день.
      const [e, s, w] = await Promise.all([
        diaryApi.list({ date, page_size: 1000, member_id: memberId }),
        diaryApi.stats(date, date, memberId).catch(() => [] as DiaryDayStats[]),
        // MG_HEADKEEPS: вода тоже принадлежит человеку, которого смотрим.
        diaryApi.getWater(date, memberId).catch(() => ({ date, water_ml: 0 } as DiaryWaterLog)),
      ]);
      setEntries(e);
      setStats(s[0] ?? { date, planned: emptyBucket, actual: emptyBucket, total: emptyBucket });
      setWaterMl(w.water_ml ?? 0);
      setWaterBy(w.added_by_name ?? null);
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

  // DIARY_EATALL_V1: отметить съеденным всё сразу — приём или весь день.
  // Отмечать по одному семь раз подряд человек не станет, и факт останется
  // пустым при съеденном плане.
  const markAll = async (items: DiaryEntry[]) => {
    const { ids, eaten } = toMark(items);
    if (!ids.length) return;
    const before = entries;
    setEntries((prev) => prev.map((x) => (ids.includes(x.id) ? { ...x, is_eaten: eaten } : x)));
    setBulkBusy(true);
    try {
      // Пачкой, а не по одному: иначе на семи приёмах экран будет дёргаться.
      await Promise.all(ids.map((id) => diaryApi.patch(id, { is_eaten: eaten })));
      const s = await diaryApi.stats(date, date, memberId).catch(() => [] as DiaryDayStats[]);
      setStats(s[0] ?? { date, planned: emptyBucket, actual: emptyBucket, total: emptyBucket });
    } catch (err) {
      setEntries(before);
      alert(getErrorMessage(err));
    } finally {
      setBulkBusy(false);
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
    try { const { data } = await diaryApi.setWater(date, next, memberId); setWaterBy(data.added_by_name ?? null); }
    catch (err) { setWaterMl(waterMl); alert(getErrorMessage(err)); }
  };

  const setWaterExact = async () => {
    const v = parseInt(customWater, 10);
    if (!Number.isFinite(v) || v < 0) return;
    setCustomWater('');
    setWaterMl(v);
    try { const { data } = await diaryApi.setWater(date, v, memberId); setWaterBy(data.added_by_name ?? null); }
    catch (err) { setWaterMl(waterMl); alert(getErrorMessage(err)); }
  };

  // DIARY_COPY_V3: plan = is_planned OR legacy planned_menu_item.
  const isPlan = (e: DiaryEntry) => e.is_planned === true || e.planned_menu_item != null;

  // MG_MEALSLOT: день раскладывается по слотам, а не по роду еды — иначе оба
  // перекуса слипаются в один и читать их невозможно.
  //
  // Слот у записи есть всегда: сервер проставляет его сам, а старым записям его
  // проставила миграция. Запасной путь по meal_type оставлен на случай ответа
  // из офлайн-кэша, снятого до обновления.
  const slotOf = (e: DiaryEntry): MealSlot =>
    (e.meal_slot ?? (e.meal_type === 'snack' ? 'snack1' : e.meal_type)) as MealSlot;

  // Сколько приёмов у человека — столько разделов и показываем, даже пустыми:
  // в пустой раздел видно, что туда ещё ничего не записано, и понятно, куда
  // класть. Плюс любой слот, где записи есть, — на случай смены раскладки.
  const viewedMember = members.find((m) =>
    memberId ? m.id === memberId : m.user_id === authUserId);
  const mealPlan = viewedMember?.profile?.meal_plan_type === '5' ? '5' : '3';
  const slotsWithEntries = new Set(entries.map(slotOf));
  const visibleSlots = MEAL_SLOT_ORDER.filter(
    (slot) => MEAL_SLOTS_BY_PLAN[mealPlan].includes(slot) || slotsWithEntries.has(slot));
  const mealGroups = visibleSlots.map((slot) => ({
    slot,
    items: entries.filter((e) => slotOf(e) === slot),
  }));
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
  // Итог приёма считаем из тех же записей, что показаны на экране: добавили
  // запись — список перезагрузился, и сумма пересчиталась сама. Отдельный
  // запрос за суммой означал бы, что она может разойтись с тем, что видно.
  const mealMacros = (items: DiaryEntry[]) => ({
    proteins: Math.round(items.reduce((s, e) => s + nutriVal(e, 'proteins'), 0)),
    fats: Math.round(items.reduce((s, e) => s + nutriVal(e, 'fats'), 0)),
    carbs: Math.round(items.reduce((s, e) => s + nutriVal(e, 'carbs'), 0)),
  });

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
            <span className="text-xs uppercase tracking-wide"
                  style={{ color: MEAL_SLOT_COLORS[slotOf(e)] }}>
              {MEAL_SLOT_LABELS[slotOf(e)] ?? e.meal_type}
            </span>
            <p className="font-medium text-chocolate mt-0.5 truncate">
              {e.recipe_title ?? e.custom_name ?? 'Без названия'}
              {e.quantity !== 1 && <span className="text-gray-400"> ×{e.quantity}</span>}
              {/* MG_HEADKEEPS: запись внёс не сам человек — видно сразу. */}
              <AddedByMark name={e.added_by_name} className="ml-1 align-middle" />
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {nutriVal(e, 'calories') > 0 && (
            <span className="text-sm text-gray-500 whitespace-nowrap">
              {Math.round(nutriVal(e, 'calories'))} ккал
            </span>
          )}
          {/* MG_DIARYEDIT: правка записи — приём, название, вес, порции, КБЖУ. */}
          <button onClick={() => setEditing(e)}
                  className="text-gray-400 hover:text-tomato text-sm" title="Изменить">✎</button>
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
          {/* DIARY_EATALL_V1: весь день одной кнопкой */}
          {toMark(entries).ids.length > 0 && (
            <Button variant="ghost" disabled={bulkBusy} onClick={() => markAll(entries)}>
              {allEaten(entries) ? '↩️ Снять отметки' : '✅ Съедено всё'}
            </Button>
          )}
          <Button onClick={() => setShowAdd(true)}>＋ Добавить</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* DIARY_FUTURE_V1: без ограничения сверху — меню импортируют вперёд,
            и на завтрашний план надо уметь зайти (и удалить лишнее). */}
        <input type="date" value={date}
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

      {/* MG_HEADKEEPS: глава смотрит чужой дневник — стоит сказать, что теперь
          он может в него и писать, и что запись не выдаст себя за чужую. */}
      {memberId && (
        <p className="text-xs text-gray-500 -mt-3">
          Вы смотрите дневник участника. Всё, что вы здесь добавите — еду, воду,
          вес, обхваты, — будет помечено короной: видно, что запись внесли вы.
        </p>
      )}

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
          {/* DIARY_TOTALS_V1: нули в факте — норма для нетронутого плана,
              но без объяснения это выглядит как сломанный подсчёт. */}
          {dayTotalsHint(stats.planned, stats.actual) && (
            <p className="text-xs text-gray-500 mt-3">{dayTotalsHint(stats.planned, stats.actual)}</p>
          )}
        </Card>
      )}

      {/* Water tracker */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-chocolate">
            💧 Вода
            {/* MG_HEADKEEPS: у воды на день одно значение — корона показывает,
                кто поставил текущее. */}
            <AddedByMark name={waterBy} withName className="ml-2" />
          </div>
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

      {/* MG_TRAINER: вес по датам — без него у тренера пустой график */}
      <WeightCard date={date} memberId={memberId} />

      {/* MG_BODYSIZE: обхваты — там же, где вес: их меряют в один заход. */}
      <MeasurementsCard date={date} memberId={memberId} />

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {/* DIARY: только выбранный день — приёмы пищи списком. */}
      {loading ? <PageSpinner /> : (entries.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📔</div>
          <p>Нет записей за этот день</p>
        </div>
      ) : (
        <div className="space-y-3">
          {mealGroups.map((g) => (
            <details key={g.slot} open={openMeals.has(g.slot)}
              // Цвет приёма — полосой слева, как в приложении.
              style={{ borderLeft: `4px solid ${MEAL_SLOT_COLORS[g.slot]}` }}
              onToggle={(ev) => {
                const isOpen = (ev.target as HTMLDetailsElement).open;
                setOpenMeals((prev) => {
                  const n = new Set(prev);
                  if (isOpen) n.add(g.slot); else n.delete(g.slot);
                  return n;
                });
              }}
              className="rounded-2xl border border-border bg-surface overflow-hidden">
              <summary
                className="cursor-pointer select-none px-4 py-3 flex items-center justify-between"
                style={{ backgroundColor: `${MEAL_SLOT_COLORS[g.slot]}14` }}
              >
                <span className="font-semibold" style={{ color: MEAL_SLOT_COLORS[g.slot] }}>
                  {MEAL_SLOT_LABELS[g.slot]}
                  <span className="text-gray-400 font-normal">
                    {g.items.length > 0 ? ` · ${g.items.length}` : ' · пусто'}
                  </span>
                </span>
                <span className="flex items-center gap-3">
                  {/* DIARY_EATALL_V1: отметить весь приём. Внутри summary, поэтому
                      гасим всплытие — иначе клик схлопывает раскрытый список. */}
                  {toMark(g.items).ids.length > 0 && (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(ev) => { ev.preventDefault(); ev.stopPropagation(); markAll(g.items); }}
                      onKeyDown={(ev) => {
                        if (ev.key === 'Enter' || ev.key === ' ') {
                          ev.preventDefault(); ev.stopPropagation(); markAll(g.items);
                        }
                      }}
                      className="text-xs text-avocado hover:underline cursor-pointer"
                    >
                      {allEaten(g.items) ? 'снять' : 'съедено всё'}
                    </span>
                  )}
                  {/* MG_MEALSLOT: итог приёма — калории и Б/Ж/У. Считается из
                      показанных записей, поэтому после добавления пересчитывается
                      вместе со списком. */}
                  <span className="text-right leading-tight">
                    <span className="block text-sm text-gray-600">{mealKcal(g.items)} ккал</span>
                    {g.items.length > 0 && (
                      <span className="block text-[11px] text-gray-500">
                        Белки {mealMacros(g.items).proteins} г
                        {' '}· Жиры {mealMacros(g.items).fats} г
                        {' '}· Углеводы {mealMacros(g.items).carbs} г
                      </span>
                    )}
                  </span>
                </span>
              </summary>
              <div className="px-3 pb-3 space-y-2">
                {g.items.length === 0 ? (
                  <p className="text-sm text-gray-400 px-1 py-2">Пока ничего не записано.</p>
                ) : (
                  g.items.map((e) => <Entry key={e.id} e={e} canCheck={isPlan(e)} />)
                )}
              </div>
            </details>
          ))}
        </div>
      ))}

      {editing && (
        <EditDiaryEntryModal entry={editing}
          onClose={() => setEditing(null)} onSaved={load} />
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
