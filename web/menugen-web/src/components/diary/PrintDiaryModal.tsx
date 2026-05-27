// DIARY_HIER_PRINT_V5
import React, { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { diaryApi } from '../../api/diary';
import { getErrorMessage } from '../../utils/api';
import { MEAL_LABELS } from '../../types';
import type { DiaryEntry, MealType } from '../../types';

interface Props {
  date: string;
  memberId?: number;
  onClose: () => void;
}

const MEAL_ORDER: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack'];
const today = () => new Date().toISOString().split('T')[0];

const num = (e: DiaryEntry, key: 'calories' | 'proteins' | 'fats' | 'carbs'): number => {
  const raw = (e.nutrition as Record<string, unknown> | undefined)?.[key];
  let n = 0;
  if (typeof raw === 'number') n = raw;
  else if (typeof raw === 'string') n = parseFloat(raw);
  else if (raw && typeof raw === 'object' && 'value' in (raw as object)) {
    n = parseFloat(String((raw as { value: unknown }).value));
  }
  const q = e.quantity ?? 1;
  return Number.isFinite(n) ? n * q : 0;
};

const daysBetween = (from: string, to: string): string[] => {
  const out: string[] = [];
  const d = new Date(from);
  const end = new Date(to);
  while (d <= end) {
    out.push(d.toISOString().split('T')[0]);
    d.setDate(d.getDate() + 1);
  }
  return out;
};

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const isPlan = (e: DiaryEntry) => e.is_planned === true || e.planned_menu_item != null;

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

export const PrintDiaryModal: React.FC<Props> = ({ date, memberId, onClose }) => {
  const [mode, setMode] = useState<'day' | 'period'>('day');
  const [from, setFrom] = useState(date);
  const [to, setTo] = useState(date);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const buildHtml = (days: { date: string; entries: DiaryEntry[] }[]): string => {
    const blocks = days.map((day) => {
      const ordered = MEAL_ORDER.flatMap((mt) => day.entries.filter((e) => e.meal_type === mt));
      const rest = day.entries.filter((e) => !MEAL_ORDER.includes(e.meal_type));
      const rows = [...ordered, ...rest];
      const tot = rows.reduce(
        (a, e) => ({
          cal: a.cal + num(e, 'calories'),
          p: a.p + num(e, 'proteins'),
          f: a.f + num(e, 'fats'),
          c: a.c + num(e, 'carbs'),
        }),
        { cal: 0, p: 0, f: 0, c: 0 },
      );
      const body = rows.length === 0
        ? '<p class="empty">Нет записей</p>'
        : `<table>
            <thead><tr>
              <th>Приём</th><th>Блюдо</th><th class="num">Кол-во</th>
              <th class="num">Ккал</th><th class="num">Б</th>
              <th class="num">Ж</th><th class="num">У</th><th>✓</th>
            </tr></thead>
            <tbody>
              ${rows.map((e) => `<tr>
                <td>${esc(MEAL_LABELS[e.meal_type] ?? e.meal_type)}</td>
                <td>${esc(e.recipe_title ?? e.custom_name ?? '—')}</td>
                <td class="num">${e.quantity}</td>
                <td class="num">${Math.round(num(e, 'calories'))}</td>
                <td class="num">${Math.round(num(e, 'proteins'))}</td>
                <td class="num">${Math.round(num(e, 'fats'))}</td>
                <td class="num">${Math.round(num(e, 'carbs'))}</td>
                <td>${isPlan(e) ? (e.is_eaten ? '✓' : '—') : '✓'}</td>
              </tr>`).join('')}
              <tr class="total">
                <td colspan="3">Итого за день</td>
                <td class="num">${Math.round(tot.cal)}</td>
                <td class="num">${Math.round(tot.p)}</td>
                <td class="num">${Math.round(tot.f)}</td>
                <td class="num">${Math.round(tot.c)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>`;
      return `<section><h2>${esc(fmtDate(day.date))}</h2>${body}</section>`;
    }).join('');

    return `<!doctype html><html lang="ru"><head><meta charset="utf-8">
      <title>Дневник питания</title>
      <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: #1a1a1a; margin: 16px; }
        h1 { font-size: 18px; margin: 0 0 12px; }
        h2 { font-size: 15px; margin: 14px 0 6px; }
        section { page-break-inside: avoid; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
        th, td { border: 1px solid #999; padding: 4px 6px; font-size: 12px; text-align: left; }
        th { background: #f0f0f0; }
        td.num, th.num { text-align: right; white-space: nowrap; }
        tr.total td { font-weight: bold; background: #fafafa; }
        .empty { font-size: 12px; color: #777; }
        @page { margin: 12mm; }
      </style></head>
      <body>
        <h1>Дневник питания</h1>
        ${blocks}
        <script>window.onload=function(){window.focus();window.print();};</script>
      </body></html>`;
  };

  const run = async () => {
    setError('');
    const f = mode === 'day' ? date : from;
    const t = mode === 'day' ? date : to;
    if (new Date(t) < new Date(f)) { setError('Конечная дата раньше начальной'); return; }
    const days = daysBetween(f, t);
    if (days.length > 31) { setError('Период не больше 31 дня'); return; }

    setBusy(true);
    try {
      const results: { date: string; entries: DiaryEntry[] }[] = [];
      for (const d of days) {
        const entries = await diaryApi.list({ date: d, member_id: memberId });
        results.push({ date: d, entries });
      }
      const html = buildHtml(results);
      const w = window.open('', '_blank', 'width=900,height=700');
      if (!w) {
        setError('Браузер заблокировал окно печати. Разрешите всплывающие окна и повторите.');
        return;
      }
      w.document.open();
      w.document.write(html);
      w.document.close();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <Card className="w-full max-w-md p-6" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-4">Печать дневника</h2>

        <div className="flex gap-2 mb-4">
          <button type="button" onClick={() => setMode('day')}
            className={`px-3 py-1.5 rounded-xl text-sm transition ${mode === 'day' ? 'bg-tomato text-white' : 'bg-rice text-chocolate'}`}>
            За день
          </button>
          <button type="button" onClick={() => setMode('period')}
            className={`px-3 py-1.5 rounded-xl text-sm transition ${mode === 'period' ? 'bg-tomato text-white' : 'bg-rice text-chocolate'}`}>
            За период
          </button>
        </div>

        {mode === 'day' ? (
          <p className="text-sm text-gray-600 mb-4">Дата: {date}</p>
        ) : (
          <div className="flex items-center gap-2 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">С</label>
              <input type="date" value={from} max={today()} onChange={(e) => setFrom(e.target.value)}
                className="rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">По</label>
              <input type="date" value={to} max={today()} onChange={(e) => setTo(e.target.value)}
                className="rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato" />
            </div>
          </div>
        )}

        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Закрыть</Button>
          <Button onClick={run} disabled={busy}>
            {busy ? <Spinner size="sm" /> : '🖨 Печать'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
