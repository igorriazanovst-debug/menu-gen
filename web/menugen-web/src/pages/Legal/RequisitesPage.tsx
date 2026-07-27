// MG_LEGAL: страница реквизитов ИП.
import React from 'react';
import { LegalShell, useLegal } from './legalShared';

const Row: React.FC<{ label: string; value?: string }> = ({ label, value }) =>
  value ? (
    <div className="flex flex-col sm:flex-row sm:gap-3 py-2 border-b border-border/60 last:border-0">
      <span className="text-gray-400 text-sm sm:w-48 shrink-0">{label}</span>
      <span className="text-chocolate break-words">{value}</span>
    </div>
  ) : null;

export const RequisitesPage: React.FC = () => {
  const { data, loading, error } = useLegal();
  return (
    <LegalShell title={data?.company_name || 'Реквизиты'} logoUrl={data?.logo_url}>
      {loading ? (
        <p className="text-center text-gray-400">Загрузка…</p>
      ) : error || !data ? (
        <p className="text-center text-gray-400">Не удалось загрузить реквизиты.</p>
      ) : (
        <div className="bg-surface rounded-2xl shadow p-5">
          <Row label="Наименование" value={data.company_name} />
          <Row label="ИНН" value={data.inn} />
          <Row label="ОГРНИП" value={data.ogrnip} />
          <Row label="Адрес" value={data.legal_address} />
          <Row label="E-mail" value={data.email} />
          <Row label="Телефон" value={data.phone} />
          <Row label="Банк" value={data.bank_name} />
          <Row label="БИК" value={data.bank_bik} />
          <Row label="Расчётный счёт" value={data.bank_account} />
          <Row label="Корр. счёт" value={data.corr_account} />
          {data.requisites_extra && (
            <div className="pt-3 whitespace-pre-wrap text-chocolate text-sm">{data.requisites_extra}</div>
          )}
          {!data.company_name && !data.inn && (
            <p className="text-center text-gray-400">Реквизиты пока не заполнены.</p>
          )}
        </div>
      )}
    </LegalShell>
  );
};

export default RequisitesPage;
