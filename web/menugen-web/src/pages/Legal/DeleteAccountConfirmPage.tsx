// MG_ACCDEL: переход по ссылке из письма — /delete-account/confirm?token=...
//
// Удаление здесь НЕ выполняется автоматически при открытии страницы: почтовые
// сервисы и антивирусы ходят по ссылкам из писем сами, и такое «подтверждение»
// сработало бы без участия человека. Поэтому нужен явный клик.
import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useLegal, LegalShell } from './legalShared';

export const DeleteAccountConfirmPage: React.FC = () => {
  const { data } = useLegal();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [state, setState] = useState<'ready' | 'sending' | 'done' | 'error'>(
    token ? 'ready' : 'error',
  );
  const [graceDays, setGraceDays] = useState(30);

  const confirm = async () => {
    setState('sending');
    try {
      const resp = await authApi.confirmAccountDeletion(token);
      setGraceDays(resp.data.grace_days ?? 30);
      setState('done');
    } catch {
      setState('error');
    }
  };

  return (
    <LegalShell title="Подтверждение удаления" logoUrl={data?.logo_url}>
      <div className="bg-white rounded-2xl p-6 shadow-sm">
        {state === 'error' && (
          <>
            <p className="mb-4">
              Ссылка недействительна или устарела — она действует сутки с момента отправки.
            </p>
            <Link
              to="/delete-account"
              className="inline-block bg-tomato text-white rounded-xl px-5 py-3 font-semibold"
            >
              Запросить новую ссылку
            </Link>
          </>
        )}

        {(state === 'ready' || state === 'sending') && (
          <>
            <p className="mb-2 font-semibold">Удалить аккаунт MenuGen?</p>
            <p className="mb-4 text-sm text-gray-600">
              Аккаунт будет заблокирован сразу, а данные удалены безвозвратно через 30 дней. Всё
              это время удаление можно отменить — достаточно войти в приложение.
            </p>
            <button
              onClick={confirm}
              disabled={state === 'sending'}
              className="bg-tomato text-white rounded-xl px-5 py-3 font-semibold disabled:opacity-60"
            >
              {state === 'sending' ? 'Отправляем…' : 'Да, удалить аккаунт'}
            </button>
          </>
        )}

        {state === 'done' && (
          <>
            <p className="mb-2 font-semibold">Аккаунт заблокирован.</p>
            <p className="text-sm text-gray-600">
              Данные будут удалены через {graceDays} дней. Если передумаете — войдите в приложение
              до этого срока, и удаление отменится.
            </p>
          </>
        )}
      </div>
    </LegalShell>
  );
};
