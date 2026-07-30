// MG_PRIVACY: страница «Политика обработки персональных данных» (152-ФЗ).
// Текст приходит с бэкенда: свой из админки либо типовой с реквизитами.
import React from 'react';
import { LegalShell, useLegal } from './legalShared';

export const PrivacyPage: React.FC = () => {
  const { data, loading, error } = useLegal();
  return (
    <LegalShell title="Политика обработки персональных данных" logoUrl={data?.logo_url}>
      {loading ? (
        <p className="text-center text-gray-400">Загрузка…</p>
      ) : error || !data ? (
        <p className="text-center text-gray-400">Не удалось загрузить политику.</p>
      ) : data.privacy_text && data.privacy_text.trim() ? (
        <div className="bg-surface rounded-2xl shadow p-5 whitespace-pre-wrap text-chocolate text-sm leading-relaxed">
          {data.privacy_text}
        </div>
      ) : (
        <p className="text-center text-gray-400">Текст политики пока не задан.</p>
      )}
    </LegalShell>
  );
};

export default PrivacyPage;
