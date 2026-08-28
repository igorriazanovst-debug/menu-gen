// MG_ACCDEL: публичная страница удаления аккаунта — /delete-account
//
// Google Play требует адрес, по которому удаление можно запросить, не открывая
// приложение, не входя и ничего не устанавливая. Поэтому страница лежит среди
// юридических (публичных) маршрутов, а не за PrivateRoute, и не просит войти.
//
// Подтверждение письмом обязательно: форма без входа, исполняющая удаление
// сразу, позволяла бы стереть чужой аккаунт, зная только e-mail.
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useLegal, LegalShell } from './legalShared';

export const DeleteAccountPage: React.FC = () => {
  const { data } = useLegal();
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'form' | 'sending' | 'sent'>('form');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setState('sending');
    try {
      await authApi.requestAccountDeletion(email.trim());
    } catch {
      // Намеренно не показываем ошибку: ответ должен быть одинаков и для
      // существующего адреса, и для любого другого. Сетевой сбой человек
      // заметит по тому, что письмо не пришло, и повторит.
    }
    setState('sent');
  };

  return (
    <LegalShell title="Удаление аккаунта" logoUrl={data?.logo_url}>
      {state === 'sent' ? (
        <div className="bg-white rounded-2xl p-6 shadow-sm">
          <p className="mb-3">
            Если аккаунт с адресом <span className="font-semibold">{email}</span> существует, мы
            отправили на него письмо со ссылкой для подтверждения. Ссылка действует сутки.
          </p>
          <p className="text-sm text-gray-500">
            Письма нет? Проверьте папку «Спам» — и убедитесь, что адрес введён тот же, с которым
            вы регистрировались.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="bg-white rounded-2xl p-6 shadow-sm">
          <p className="mb-4">
            Укажите адрес, на который зарегистрирован аккаунт. Мы пришлём письмо со ссылкой —
            удаление начнётся только после перехода по ней.
          </p>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full border border-border rounded-xl px-4 py-3 mb-4"
            aria-label="E-mail аккаунта"
          />
          <button
            type="submit"
            disabled={state === 'sending'}
            className="w-full bg-tomato text-white rounded-xl py-3 font-semibold disabled:opacity-60"
          >
            {state === 'sending' ? 'Отправляем…' : 'Прислать ссылку для удаления'}
          </button>
        </form>
      )}

      <div className="bg-white rounded-2xl p-6 shadow-sm mt-6 text-sm leading-relaxed">
        <h2 className="font-semibold text-base mb-3">Что произойдёт</h2>
        <ul className="list-disc pl-5 space-y-2">
          <li>Сразу после подтверждения аккаунт блокируется — войти в него будет нельзя.</li>
          <li>
            Через 30 дней данные удаляются безвозвратно: профиль, меню, холодильник, списки
            покупок, дневники питания и веса, избранные рецепты и загруженные фотографии.
          </li>
          <li>
            <span className="font-semibold">Передумали?</span> В течение этих 30 дней просто
            войдите в приложение обычным способом — удаление отменится, данные останутся на месте.
          </li>
          <li>
            Если в вашей семье есть другие участники, семья и её данные сохранятся и перейдут к
            одному из них. Если вы в семье один — она удаляется вместе с аккаунтом.
          </li>
          <li>
            Рецепты, которые вы опубликовали для всех, остаются в общем каталоге, но перестают
            быть связаны с вами.
          </li>
          <li>
            Сведения о совершённых платежах сохраняются без привязки к вам: этого требует
            бухгалтерский учёт.
          </li>
        </ul>
      </div>

      <p className="text-sm text-gray-500 mt-6 text-center">
        Удалить аккаунт можно и в приложении: «Профиль» → «Удалить аккаунт».{' '}
        <Link to="/privacy" className="text-tomato hover:underline">
          Политика обработки персональных данных
        </Link>
      </p>
    </LegalShell>
  );
};
