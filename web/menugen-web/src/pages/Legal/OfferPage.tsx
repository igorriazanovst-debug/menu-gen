// MG_LEGAL: страница публичной оферты.
import React from 'react';
import { LegalShell, useLegal } from './legalShared';

export const OfferPage: React.FC = () => {
  const { data, loading, error } = useLegal();
  return (
    <LegalShell title="Публичная оферта" logoUrl={data?.logo_url}>
      {loading ? (
        <p className="text-center text-gray-400">Загрузка…</p>
      ) : error || !data ? (
        <p className="text-center text-gray-400">Не удалось загрузить оферту.</p>
      ) : data.offer_text && data.offer_text.trim() ? (
        <div className="bg-surface rounded-2xl shadow p-5 whitespace-pre-wrap text-chocolate text-sm leading-relaxed">
          {data.offer_text}
        </div>
      ) : (
        <p className="text-center text-gray-400">Текст оферты пока не задан.</p>
      )}
    </LegalShell>
  );
};

export default OfferPage;
