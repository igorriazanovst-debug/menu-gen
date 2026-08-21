// MG_SHELFLIFE: перенос покупок в холодильник со сроками годности.
//
// Раньше это было окно подтверждения: «перенести N товаров?» — и товары
// ложились без сроков, из-за чего напоминание «скоро испортится» молчало для
// всего купленного.
//
// Даты подставлены по справочнику (сколько продукт живёт после покупки), но
// показаны и правятся здесь же. Молча проставленный неверный срок рождает
// ложные «испортится», а от них перестают читать и настоящие — поэтому
// предположение видно до сохранения, а не после.
import React, { useMemo, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import type { ShoppingV2Item } from '../../types';

interface Props {
  items: ShoppingV2Item[];
  autoExpiry: boolean;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (expiry: Record<number, string | null>) => void;
}

/** Стартовые даты: подсказка сервера, если семья её хочет. */
export const initialExpiry = (
  items: ShoppingV2Item[],
  autoExpiry: boolean,
): Record<number, string> => {
  const out: Record<number, string> = {};
  if (!autoExpiry) return out;
  for (const it of items) {
    if (it.suggested_expiry) out[it.id] = it.suggested_expiry;
  }
  return out;
};

/** Пустая строка — это «без срока», а не «подставь сам»: шлём null. */
export const toPayload = (dates: Record<number, string>): Record<number, string | null> => {
  const out: Record<number, string | null> = {};
  for (const [id, value] of Object.entries(dates)) {
    out[Number(id)] = value ? value : null;
  }
  return out;
};

export const TransferToFridgeModal: React.FC<Props> = ({
  items,
  autoExpiry,
  busy,
  onCancel,
  onConfirm,
}) => {
  const [dates, setDates] = useState<Record<number, string>>(() => initialExpiry(items, autoExpiry));

  const known = useMemo(() => items.filter((i) => i.suggested_expiry).length, [items]);

  const set = (id: number, value: string) => setDates((prev) => ({ ...prev, [id]: value }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onCancel}>
      <Card
        className="w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-chocolate mb-1">В холодильник</h2>
        <p className="text-xs text-gray-500 mb-4">
          Переносятся купленные товары. Сроки годности подставлены примерно —
          {known > 0 ? ' поправьте, где знаете точнее.' : ' справочных сроков нет, укажите вручную.'}
        </p>

        <div className="space-y-2">
          {items.map((it) => (
            <div key={it.id} className="flex items-center justify-between gap-3">
              <span className="text-sm text-chocolate min-w-0 truncate">{it.name}</span>
              <input
                type="date"
                value={dates[it.id] ?? ''}
                onChange={(e) => set(it.id, e.target.value)}
                className="rounded-xl border border-gray-300 px-2 py-1.5 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none"
              />
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-400 mt-3">
          Пустая дата — товар ляжет без срока, напоминания по нему не будет.
        </p>

        <div className="flex items-center gap-3 mt-5">
          <Button onClick={() => onConfirm(toPayload(dates))} disabled={busy}>
            {busy ? 'Переносим…' : `Перенести (${items.length})`}
          </Button>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Отмена
          </Button>
        </div>
      </Card>
    </div>
  );
};
