// MG_205UI_V_target_field = 1
import React, { useState, useEffect, useCallback } from 'react';
import type { TargetField as TF, TargetMeta, TargetAuditEntry } from '../../types';

interface Props {
  label: string;          // "Ккал", "Белок"…
  unit: string;           // "ккал", "г"
  value: string | number | null | undefined;
  field: TF;              // 'calorie_target' и т.д.
  meta?: TargetMeta;      // последняя запись аудита
  bgClass: string;        // напр. 'bg-tomato/10 text-tomato'
  /**
   * Источник истории: либо текущий пользователь (`{kind:'me'}`),
   * либо член семьи (`{kind:'member', memberId, getHistory, onReset}`).
   * Это позволяет переиспользовать компонент в Profile и в Family.
   */
  loader: TargetLoader;
  /** Колбэк после успешного reset — родитель должен перезагрузить data. */
  onResetDone?: () => void;
  /** true если у пользователя нет прав на reset (read-only режим). */
  readOnly?: boolean;
}

export type TargetLoader = {
  getHistory: (field: TF) => Promise<TargetAuditEntry[]>;
  reset: (field: TF) => Promise<void>;
};

const formatNum = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isNaN(n) ? '—' : n.toFixed(0);
};

const sourceBadge: Record<string, { label: string; cls: string }> = {
  auto:       { label: 'auto',     cls: 'bg-gray-100  text-gray-600  border-gray-200' },
  user:       { label: 'вручную',  cls: 'bg-blue-100  text-blue-700  border-blue-200' },
  specialist: { label: 'специалист', cls: 'bg-purple-100 text-purple-700 border-purple-200' },
};

const formatDate = (iso?: string | null) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return iso; }
};

export const TargetField: React.FC<Props> = ({
  label, unit, value, field, meta, bgClass, loader, onResetDone, readOnly,
}) => {
  const [open, setOpen] = useState(false);
  const [hist, setHist] = useState<TargetAuditEntry[] | null>(null);
  const [loadErr, setLoadErr] = useState<string>('');
  const [resetting, setResetting] = useState(false);

  const src = meta?.source ?? 'auto';
  const badge = sourceBadge[src] ?? sourceBadge.auto;

  const loadHistory = useCallback(async () => {
    setLoadErr(''); setHist(null);
    try {
      const arr = await loader.getHistory(field);
      setHist(arr);
    } catch (e: any) {
      setLoadErr(e?.message ?? 'Не удалось загрузить историю');
    }
  }, [loader, field]);

  useEffect(() => {
    if (open && hist === null) loadHistory();
  }, [open, hist, loadHistory]);

  const handleReset = async () => {
    setResetting(true);
    try {
      await loader.reset(field);
      onResetDone?.();
      setHist(null);  // история обновится при следующем открытии
    } catch (e) { /* ignore */ }
    finally { setResetting(false); }
  };

  return (
    <div className={`relative px-3 py-2 rounded-xl ${bgClass} border border-transparent`}>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] uppercase tracking-wide opacity-70">{label}</span>
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className={`text-[9px] uppercase font-medium px-1.5 py-0.5 rounded border ${badge.cls} hover:opacity-80 transition`}
          title="Источник правки. Нажмите для истории"
        >
          {badge.label}
        </button>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-lg font-bold leading-none">{formatNum(value)}</span>
        <span className="text-[10px] opacity-60">{unit}</span>
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 bg-white rounded-xl border border-gray-200 shadow-lg p-3 text-xs text-chocolate min-w-[220px]">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold">{label} — история</span>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-700">✕</button>
          </div>

          {loadErr && <div className="text-red-600 mb-2">{loadErr}</div>}
          {hist === null && !loadErr && <div className="text-gray-400">Загрузка…</div>}
          {hist && hist.length === 0 && <div className="text-gray-400">Записей нет</div>}

          {hist && hist.length > 0 && (
            <ul className="space-y-1.5 max-h-56 overflow-y-auto">
              {hist.map(e => (
                <li key={e.id} className="flex items-start gap-2">
                  <span className={`mt-0.5 px-1.5 py-0.5 rounded border text-[9px] uppercase ${(sourceBadge[e.source] ?? sourceBadge.auto).cls}`}>
                    {(sourceBadge[e.source] ?? sourceBadge.auto).label}
                  </span>
                  <div className="flex-1">
                    <div className="text-gray-900">
                      {e.old_value ?? '—'} → <strong>{e.new_value ?? '—'}</strong>
                    </div>
                    <div className="text-gray-400">
                      {formatDate(e.at)}
                      {e.by_user && <> · {e.by_user.name}</>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {!readOnly && src !== 'auto' && (
            <button
              type="button"
              onClick={handleReset}
              disabled={resetting}
              className="mt-3 w-full text-xs px-3 py-2 rounded-lg bg-tomato text-white hover:bg-tomato/90 disabled:opacity-50"
            >
              {resetting ? 'Сброс…' : 'Сбросить к авто'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
