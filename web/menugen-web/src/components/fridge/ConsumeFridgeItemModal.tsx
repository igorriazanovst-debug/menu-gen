import React, { useState } from 'react';
import { fridgeApi } from '../../api/fridge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { fmtWriteOffQty } from '../../utils/writeOffQty';
import type { FridgeItem } from '../../types';

/**
 * MG_WRITEOFF: «Израсходовал» — ручное списание позиции холодильника.
 *
 * Съеденное убиралось из холодильника только удалением позиции целиком.
 * Початую пачку это не описывает никак: съели половину — либо удали всё, либо
 * правь количество руками.
 *
 * Количество здесь — в единице самой позиции и никуда не переводится: человек
 * смотрит на конкретную пачку и говорит, сколько ушло из неё.
 *
 * Ошибочное нажатие снимается сразу после него: списание — это запись, и её
 * номер возвращается, чтобы вернуть всё целиком.
 */
interface Props {
  item: FridgeItem;
  onClose: () => void;
  /** Списание прошло (или его отменили) — список надо перечитать. */
  onDone: () => void;
}

export const ConsumeFridgeItemModal: React.FC<Props> = ({ item, onClose, onDone }) => {
  const [qty, setQty] = useState(fmtWriteOffQty(item.quantity));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [writeOffId, setWriteOffId] = useState<number | null>(null);

  const send = async (all: boolean) => {
    if (busy) return;
    const parsed = Number(qty.replace(',', '.'));
    if (!all && (!qty.trim() || !Number.isFinite(parsed) || parsed <= 0)) {
      setErr('Укажите количество больше нуля');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const { data } = await fridgeApi.consume(item.id, all ? undefined : parsed);
      setWriteOffId(data.write_off_id);
      onDone();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Не удалось списать');
      setBusy(false);
    }
  };

  const undo = async () => {
    if (writeOffId == null) return;
    setBusy(true);
    try {
      await fridgeApi.undoWriteOff(writeOffId);
      onDone();
      onClose();
    } catch {
      setBusy(false);
      setErr('Не удалось отменить списание');
    }
  };

  // Списали — показываем итог с возможностью вернуть.
  if (writeOffId != null) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <Card className="max-w-sm w-full p-6" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
          <h2 className="text-lg font-bold text-chocolate">🧊 {item.name}</h2>
          <p className="mt-2 text-sm text-gray-600">Списано из холодильника.</p>
          {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
          <div className="mt-5 flex flex-col gap-2">
            <Button onClick={onClose} disabled={busy}>Готово</Button>
            <button
              type="button"
              onClick={undo}
              disabled={busy}
              className="text-sm text-gray-500 hover:text-chocolate disabled:opacity-60"
            >
              ↩ Отменить списание
            </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <Card className="max-w-sm w-full p-6" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-chocolate">{item.name}</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              В холодильнике: {fmtWriteOffQty(item.quantity)} {item.unit ?? ''}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        <label className="block mt-4 text-sm text-gray-600">
          Израсходовано
          <div className="flex items-center gap-2 mt-1">
            <input
              autoFocus
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputMode="decimal"
              className="flex-1 border border-border rounded-xl px-3 py-2 text-sm"
            />
            <span className="text-sm text-gray-500">{item.unit ?? ''}</span>
          </div>
        </label>

        {err && <p className="mt-2 text-sm text-red-600">{err}</p>}

        <div className="mt-5 flex gap-2">
          <Button variant="ghost" className="flex-1" onClick={() => send(true)} disabled={busy}>
            Списать всё
          </Button>
          <Button className="flex-1" onClick={() => send(false)} disabled={busy}>
            {busy ? '…' : 'Списать'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
