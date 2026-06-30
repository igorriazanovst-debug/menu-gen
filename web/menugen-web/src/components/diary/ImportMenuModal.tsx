// FILL_FROM_MENU_V4
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { diaryApi } from '../../api/diary';
import { menuApi } from '../../api/menu';
import { getErrorMessage } from '../../utils/api';
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

  // Group items by day_offset → slot.
  const grouped = useMemo(() => {
    const items = detail?.items ?? [];
    const byDay = new Map<number, Map<string, MenuItem[]>>();
    for (const it of items) {
      const day = it.day_offset ?? 0;
      const slot = slotKey(it);
      if (!byDay.has(day)) byDay.set(day, new Map());
      const slots = byDay.get(day)!;
      if (!slots.has(slot)) slots.set(slot, []);
      slots.get(slot)!.push(it);
    }
    return byDay;
  }, [detail]);

  // DIARY_MULTIDAY: день меню ляжет на baseDate + offset (не на собственные даты меню).
  const dayDate = (offset: number): string => {
    const iso = addDaysIso(baseDate, offset);
    return new Date(`${iso}T00:00:00`).toLocaleDateString('ru', { weekday: 'short', day: 'numeric', month: 'short' });
  };

  const toggle = (id: number) =>
    setSelected((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const toggleMany = (ids: number[], on: boolean) =>
    setSelected((prev) => {
      const n = new Set(prev);
      ids.forEach((i) => (on ? n.add(i) : n.delete(i)));
      return n;
    });

  const allIds = useMemo(() => (detail?.items ?? []).map((i) => i.id), [detail]);
  const allChecked = allIds.length > 0 && selected.size === allIds.length;

  const run = async () => {
    if (menuId == null) return;
    if (selected.size === 0) { setError('Выберите хотя бы один приём'); return; }
    setBusy(true); setError('');
    try {
      await diaryApi.importFromMenu(menuId, baseDate, memberId, Array.from(selected));
      onImported(baseDate);
      onClose();
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
                  Выбрать всё ({allIds.length})
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
                            const its = slots.get(sk)!;
                            const ids = its.map((i) => i.id);
                            const on = ids.every((i) => selected.has(i));
                            return (
                              <div key={sk}>
                                <label className="flex items-center gap-2 text-xs font-medium text-gray-500 mb-1 cursor-pointer select-none">
                                  <input type="checkbox" checked={on}
                                         onChange={() => toggleMany(ids, !on)}
                                         className="w-3.5 h-3.5 accent-tomato" />
                                  {MEAL_SLOT_LABEL[sk] ?? MEAL_LABELS[sk as MealType] ?? sk}
                                </label>
                                <div className="pl-5 space-y-1">
                                  {its.map((it) => (
                                    <label key={it.id}
                                           className="flex items-center gap-2 text-sm text-chocolate cursor-pointer select-none">
                                      <input type="checkbox" checked={selected.has(it.id)}
                                             onChange={() => toggle(it.id)}
                                             className="w-4 h-4 accent-tomato" />
                                      <span className="truncate">
                                        {it.recipe?.title ?? 'Без названия'}
                                        {it.quantity !== 1 && <span className="text-gray-400"> ×{it.quantity}</span>}
                                      </span>
                                    </label>
                                  ))}
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

        <div className="flex gap-2 justify-end mt-4">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Отмена</Button>
          <Button onClick={run} disabled={busy || selected.size === 0}>
            {busy ? 'Добавление…' : `Добавить (${selected.size})`}
          </Button>
        </div>
      </Card>
    </div>
  );
};
