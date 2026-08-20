// DIARY_COPY_V3
import React, { useCallback, useEffect, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { diaryApi } from '../../api/diary';
import { getErrorMessage } from '../../utils/api';
import { MEAL_LABELS } from '../../types';
import type { DiaryEntry } from '../../types';
import { todayIso } from '../../utils/isoDate'; // ISO_DATE_V1

interface Props {
  targetDate: string;   // day the copies will land on (the page's current date)
  memberId?: number;
  onClose: () => void;
  onCopied: () => void;
}

const today = todayIso; // ISO_DATE_V1

export const CopyFromDayModal: React.FC<Props> = ({ targetDate, memberId, onClose, onCopied }) => {
  const [sourceDate, setSourceDate] = useState(today());
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(''); setSelected(new Set());
    try {
      const e = await diaryApi.list({ date: sourceDate, member_id: memberId });
      setEntries(e);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [sourceDate, memberId]);

  useEffect(() => { load(); }, [load]);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const allChecked = entries.length > 0 && selected.size === entries.length;
  const toggleAll = () => {
    setSelected(allChecked ? new Set() : new Set(entries.map((e) => e.id)));
  };

  const run = async () => {
    if (selected.size === 0) { setError('Выберите хотя бы одну запись'); return; }
    setBusy(true); setError('');
    try {
      await diaryApi.copy(Array.from(selected), targetDate, memberId);
      onCopied();
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <Card className="w-full max-w-md p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-chocolate mb-1">Копировать из дня</h2>
        <p className="text-xs text-gray-500 mb-4">Записи добавятся в план на {targetDate}</p>

        <label className="block text-xs text-gray-500 mb-1">Дата-источник</label>
        <input type="date" value={sourceDate} max={today()}
          onChange={(e) => setSourceDate(e.target.value)}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none" />

        {loading ? (
          <div className="py-8 flex justify-center"><Spinner size="md" /></div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-gray-400 py-6 text-center">Нет записей за этот день</p>
        ) : (
          <div className="space-y-2 mb-4">
            <label className="flex items-center gap-2 text-sm text-chocolate cursor-pointer select-none">
              <input type="checkbox" checked={allChecked} onChange={toggleAll}
                     className="w-4 h-4 accent-tomato" />
              Выбрать все ({entries.length})
            </label>
            <div className="h-px bg-gray-100" />
            {entries.map((e) => (
              <label key={e.id}
                     className="flex items-center gap-2 rounded-xl bg-rice px-3 py-2 cursor-pointer select-none">
                <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggle(e.id)}
                       className="w-4 h-4 accent-tomato" />
                <span className="text-xs text-gray-400 uppercase w-16 shrink-0">
                  {MEAL_LABELS[e.meal_type] ?? e.meal_type}
                </span>
                <span className="text-sm text-chocolate truncate flex-1">
                  {e.recipe_title ?? e.custom_name ?? 'Без названия'}
                  {e.quantity !== 1 && <span className="text-gray-400"> ×{e.quantity}</span>}
                </span>
                {e.nutrition?.calories && (
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {e.nutrition.calories.value} {e.nutrition.calories.unit}
                  </span>
                )}
              </label>
            ))}
          </div>
        )}

        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Отмена</Button>
          <Button onClick={run} disabled={busy || selected.size === 0}>
            {busy ? 'Копирование…' : `Копировать (${selected.size})`}
          </Button>
        </div>
      </Card>
    </div>
  );
};
