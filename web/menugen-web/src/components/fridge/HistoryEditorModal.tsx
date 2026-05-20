import React, { useEffect, useState } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Button } from '../ui/Button';
import type { FridgeHistoryItem } from '../../types';

interface Props {
  onClose: () => void;
  onChanged: () => void | Promise<void>;
}

export const HistoryEditorModal: React.FC<Props> = ({ onClose, onChanged }) => {
  const [history, setHistory] = useState<FridgeHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy]       = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await fridgeApi.history(100);
      setHistory((data as any) ?? []);
    } catch {
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const doDelete = async (h: FridgeHistoryItem, dropFridge: boolean) => {
    const label = dropFridge
      ? `Удалить «${h.name}» из холодильника И из истории?`
      : `Удалить «${h.name}» из истории добавления?\n(Активные позиции в холодильнике останутся.)`;
    if (!window.confirm(label)) return;
    setBusy(h.name);
    try {
      await fridgeApi.deleteHistoryEntry(h.name, dropFridge);
      await load();
      await onChanged();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-chocolate">История добавления</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {loading ? (
            <p className="text-sm text-gray-500 py-8 text-center">Загрузка…</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-gray-500 py-8 text-center">История пуста.</p>
          ) : (
            <div className="space-y-2">
              {history.map((h, i) => (
                <div
                  key={`${h.name}-${i}`}
                  className="flex items-center gap-2 p-2 rounded-xl border border-gray-200"
                >
                  <span className="text-lg">{h.category_icon || '📦'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-chocolate truncate">{h.name}</div>
                    <div className="text-xs text-gray-500">
                      {h.category_name || 'Без категории'} · добавлений: {h.times_used}
                    </div>
                  </div>
                  <button
                    onClick={() => doDelete(h, false)}
                    disabled={busy === h.name}
                    className="text-xs px-2 py-1 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                    title="Удалить из истории (активные останутся)"
                  >🕘✕</button>
                  <button
                    onClick={() => doDelete(h, true)}
                    disabled={busy === h.name}
                    className="text-xs px-2 py-1 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-50"
                    title="Удалить из холодильника и истории"
                  >🗑 всё</button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 text-[11px] text-gray-400 leading-snug">
            🕘✕ — удалить только из истории (записи, которых нет в холодильнике).<br />
            🗑 всё — удалить из холодильника и из истории.
          </div>
        </div>
      </div>
    </div>
  );
};
