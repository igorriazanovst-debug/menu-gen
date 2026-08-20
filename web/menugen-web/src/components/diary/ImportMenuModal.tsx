// FILL_FROM_MENU_V4
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { diaryApi } from '../../api/diary';
import { menuApi } from '../../api/menu';
import { getErrorMessage } from '../../utils/api';
import { importOutcome } from '../../utils/importOutcome'; // FILL_FROM_MENU_V5
import { MEAL_LABELS } from '../../types';
import type { Menu, MenuItem, MealType } from '../../types';

interface Props {
  date: string;
  memberId?: number;
  onClose: () => void;
  // DIARY_MULTIDAY: startDate — куда лёг день 0 плана (страница перецентрируется на него).
  onImported: (startDate?: string) => void;
}

// DIARY_MULTIDAY: сдвиг ISO-даты на N дней.
const addDaysIso = (iso: string, n: number): string => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
};

const MEAL_SLOT_LABEL: Record<string, string> = {
  breakfast: 'Завтрак', snack1: 'Перекус 1', lunch: 'Обед',
  snack2: 'Перекус 2', dinner: 'Ужин', snack: 'Перекус',
};
const SLOT_ORDER = ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner', 'snack'];

const slotKey = (it: MenuItem): string =>
  (it.meal_slot && String(it.meal_slot)) || it.meal_type;

// FILL_FROM_MENU: одно блюдо в списке импорта; ids — все копии (по членам семьи).
interface Dish { title: string; ids: number[]; }

const fmtRange = (m: Menu) => {
  const f = (d: string) => new Date(d).toLocaleDateString('ru', { day: 'numeric', month: 'short' });
  return `${f(m.start_date)} – ${f(m.end_date)}`;
};

export const ImportMenuModal: React.FC<Props> = ({ date, memberId, onClose, onImported }) => {
  const [menus, setMenus] = useState<Menu[]>([]);
  const [menuId, setMenuId] = useState<number | null>(null);
  const [baseDate, setBaseDate] = useState(date); // DIARY_MULTIDAY: дата старта плана
  const [detail, setDetail] = useState<Menu | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(''); // FILL_FROM_MENU_V5: результат импорта

  // Load menu list; default to the first (active) menu.
  useEffect(() => {
    (async () => {
      setLoadingList(true); setError('');
      try {
        const { data } = await menuApi.list();
        const d = data as unknown as { results?: Menu[] } | Menu[];
        const list = Array.isArray(d) ? d : (d.results ?? []);
        setMenus(list);
        if (list.length) setMenuId(list[0].id);
        else setError('Нет доступных меню. Сначала сгенерируйте меню.');
      } catch (e) {
        setError(getErrorMessage(e));
      } finally {
        setLoadingList(false);
      }
    })();
  }, []);

  // Load detail of selected menu.
  const loadDetail = useCallback(async (id: number) => {
    setLoadingDetail(true); setError(''); setSelected(new Set());
    try {
      const { data } = await menuApi.get(id);
      setDetail(data);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => { if (menuId != null) loadDetail(menuId); }, [menuId, loadDetail]);

  // FILL_FROM_MENU: схлопываем копии блюда (в family-меню одно блюдо продублировано
  // под каждого члена семьи). Блюдо = (recipe.id + component_role); храним все id-копии,
  // отправляем их — бэкенд импортирует копию нужного члена.
  const grouped = useMemo(() => {
    const items = detail?.items ?? [];
    const byDay = new Map<number, Map<string, Map<string, Dish>>>();
    for (const it of items) {
      const day = it.day_offset ?? 0;
      const slot = slotKey(it);
      const key = `${it.recipe?.id ?? it.recipe?.title ?? ''}|${it.component_role ?? ''}`;
      if (!byDay.has(day)) byDay.set(day, new Map());
      const slots = byDay.get(day)!;
      if (!slots.has(slot)) slots.set(slot, new Map());
      const dishes = slots.get(slot)!;
      if (!dishes.has(key)) dishes.set(key, { title: it.recipe?.title ?? 'Без названия', ids: [] });
      dishes.get(key)!.ids.push(it.id);
    }
    // внутренние map блюд → массивы (сохраняя порядок)
    const out = new Map<number, Map<string, Dish[]>>();
    byDay.forEach((slots, day) => {
      const s = new Map<string, Dish[]>();
      slots.forEach((dishes, slot) => s.set(slot, Array.from(dishes.values())));
      out.set(day, s);
    });
    return out;
  }, [detail]);

  const dishList = useMemo(() => {
    const arr: Dish[] = [];
    grouped.forEach((slots) => slots.forEach((dishes) => arr.push(...dishes)));
    return arr;
  }, [grouped]);

  // DIARY_MULTIDAY: день меню ляжет на baseDate + offset (не на собственные даты меню).
  const dayDate = (offset: number): string => {
    const iso = addDaysIso(baseDate, offset);
    return new Date(`${iso}T00:00:00`).toLocaleDateString('ru', { weekday: 'short', day: 'numeric', month: 'short' });
  };

  const toggleMany = (ids: number[], on: boolean) =>
    setSelected((prev) => {
      const n = new Set(prev);
      ids.forEach((i) => (on ? n.add(i) : n.delete(i)));
      return n;
    });

  const allIds = useMemo(() => (detail?.items ?? []).map((i) => i.id), [detail]);
  const allChecked = allIds.length > 0 && selected.size === allIds.length;
  // Счётчики по УНИКАЛЬНЫМ блюдам (а не по id-копиям).
  const totalDishes = dishList.length;
  const selectedDishes = dishList.filter((d) => d.ids.every((id) => selected.has(id))).length;

  const run = async () => {
    if (menuId == null) return;
    if (selected.size === 0) { setError('Выберите хотя бы один приём'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      const { data } = await diaryApi.importFromMenu(menuId, baseDate, memberId, Array.from(selected));
      // FILL_FROM_MENU_V5: переходим туда, где записи оказались, а не на дату
      // начала плана: блюда третьего дня меню ложатся на «начало + 2».
      const outcome = importOutcome(data);
      onImported(outcome.jumpDate ?? baseDate);
      if (outcome.keepOpen) {
        setNotice(outcome.message);
      } else {
        onClose();
      }
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const sortedDays = useMemo(() => Array.from(grouped.keys()).sort((a, b) => a - b), [grouped]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <Card className="w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-1">Заполнить из меню</h2>
        <p className="text-xs text-gray-500 mb-3">
          Дни меню разнесутся по датам, начиная с выбранной даты старта.
        </p>

        {/* DIARY_MULTIDAY: дата старта плана (день 0 меню). */}
        <label className="block text-xs text-gray-500 mb-1">Дата начала плана</label>
        <input type="date" value={baseDate}
               onChange={(e) => setBaseDate(e.target.value || date)}
               className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none" />

        {loadingList ? (
          <div className="py-8 flex justify-center"><Spinner size="md" /></div>
        ) : (
          <>
            <label className="block text-xs text-gray-500 mb-1">Меню</label>
            <select
              value={menuId ?? ''}
              onChange={(e) => setMenuId(e.target.value ? Number(e.target.value) : null)}
              className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none">
              {menus.map((m) => (
                <option key={m.id} value={m.id}>
                  #{m.id} · {fmtRange(m)}{m.status ? ` · ${m.status}` : ''}
                </option>
              ))}
            </select>

            {loadingDetail ? (
              <div className="py-8 flex justify-center"><Spinner size="md" /></div>
            ) : detail && allIds.length > 0 ? (
              <>
                <label className="flex items-center gap-2 text-sm text-chocolate mb-2 cursor-pointer select-none">
                  <input type="checkbox" checked={allChecked}
                         onChange={() => toggleMany(allIds, !allChecked)}
                         className="w-4 h-4 accent-tomato" />
                  Выбрать всё ({totalDishes})
                </label>

                <div className="space-y-4">
                  {sortedDays.map((day) => {
                    const slots = grouped.get(day)!;
                    const slotKeys = Array.from(slots.keys())
                      .sort((a, b) => SLOT_ORDER.indexOf(a) - SLOT_ORDER.indexOf(b));
                    return (
                      <div key={day} className="rounded-xl border border-border">
                        <div className="px-3 py-2 text-xs font-semibold text-chocolate bg-rice rounded-t-xl">
                          День {day + 1} · {dayDate(day)}
                        </div>
                        <div className="p-2 space-y-2">
                          {slotKeys.map((sk) => {
                            const dishes = slots.get(sk)!;
                            const ids = dishes.flatMap((d) => d.ids);
                            const on = ids.length > 0 && ids.every((i) => selected.has(i));
                            return (
                              <div key={sk}>
                                <label className="flex items-center gap-2 text-xs font-medium text-gray-500 mb-1 cursor-pointer select-none">
                                  <input type="checkbox" checked={on}
                                         onChange={() => toggleMany(ids, !on)}
                                         className="w-3.5 h-3.5 accent-tomato" />
                                  {MEAL_SLOT_LABEL[sk] ?? MEAL_LABELS[sk as MealType] ?? sk}
                                </label>
                                <div className="pl-5 space-y-1">
                                  {dishes.map((dish, di) => {
                                    const checked = dish.ids.every((id) => selected.has(id));
                                    return (
                                      <label key={di}
                                             className="flex items-center gap-2 text-sm text-chocolate cursor-pointer select-none">
                                        <input type="checkbox" checked={checked}
                                               onChange={() => toggleMany(dish.ids, !checked)}
                                               className="w-4 h-4 accent-tomato" />
                                        <span className="truncate">{dish.title}</span>
                                      </label>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              !error && <p className="text-sm text-gray-400 py-6 text-center">В меню нет позиций</p>
            )}
          </>
        )}

        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}
        {/* FILL_FROM_MENU_V5: молчание после импорта неотличимо от поломки */}
        {notice && <p className="text-sm text-chocolate mt-3">{notice}</p>}

        <div className="flex gap-2 justify-end mt-4">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Отмена</Button>
          <Button onClick={run} disabled={busy || selected.size === 0}>
            {busy ? 'Добавление…' : `Добавить (${selectedDishes})`}
          </Button>
        </div>
      </Card>
    </div>
  );
};
