// MG_PAYPERIOD: выбор периода подписки.
//
// Раньше «Подключить» вело на оплату месяца без вариантов. Теперь период
// выбирает человек, а выгоду длинного периода считает бэкенд — чтобы она была
// одинаковой в вебе и в мобильном, а не пересчитывалась в каждом клиенте.
import React from 'react';
import type { PlanOffer } from '../../types';

interface Props {
  offers: PlanOffer[];
  value: string;
  onChange: (code: string) => void;
}

export const PeriodPicker: React.FC<Props> = ({ offers, value, onChange }) => {
  if (offers.length < 2) return null;

  return (
    <div className="flex gap-2 mb-3" role="radiogroup" aria-label="Период подписки">
      {offers.map((offer) => {
        const active = offer.code === value;
        return (
          <button
            key={offer.code}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(offer.code)}
            className={[
              'relative flex-1 rounded-xl border px-3 py-2 text-sm transition',
              active
                ? 'border-tomato bg-tomato/5 text-chocolate font-semibold'
                : 'border-gray-200 text-gray-500 hover:border-gray-300',
            ].join(' ')}
          >
            {offer.title}
            {offer.discount_percent > 0 && (
              <span className="absolute -top-2 -right-1 rounded-full bg-avocado px-1.5 py-0.5 text-[10px] font-semibold text-white">
                −{offer.discount_percent}%
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

/** Подпись под ценой: за месяц при длинном периоде — чтобы сравнивать было с чем. */
export function offerPriceNote(offer: PlanOffer): string | null {
  if (offer.months <= 1) return null;
  return `${Math.round(Number(offer.price_per_month))} ₽ в месяц`;
}
