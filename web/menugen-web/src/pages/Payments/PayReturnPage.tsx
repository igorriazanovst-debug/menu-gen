// MG_PAYRELIABLE: страница возврата с оплаты для мобильного приложения.
//
// ЮKassa принимает только http(s) в return_url, поэтому вернуть человека прямо
// в приложение она не может. Приложение уводит сюда, а отсюда — обратно в него.
//
// Страница ПУБЛИЧНАЯ и намеренно ничего не знает о платеже. Оплата началась в
// приложении, а открылся системный браузер: там может не быть ни сессии, ни
// вообще этого аккаунта. Спрашивать статус здесь — значит показать «войдите»
// вместо результата. Исход выясняет само приложение, у которого есть и
// идентификатор платежа, и авторизация.
import React from 'react';
import { Link } from 'react-router-dom';
import { canOpenApp } from '../../utils/appLink';

export const APP_PAYMENT_LINK = 'menugen://payment';

export const PayReturnPage: React.FC = () => {
  const offerApp = React.useRef(canOpenApp()).current;

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm text-center">
        <div className="text-6xl mb-3">🍅</div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          <div className="text-5xl mb-3">✅</div>
          <h2 className="text-xl font-semibold text-text mb-1">Оплата завершена</h2>
          <p className="text-muted text-sm mb-5">
            Вернитесь в приложение — подписка обновится сама.
          </p>

          {offerApp && (
            <a
              href={APP_PAYMENT_LINK}
              className="block w-full bg-tomato text-white font-medium rounded-xl py-3 hover:opacity-90 transition"
            >
              Вернуться в приложение
            </a>
          )}

          <p className="text-sm text-muted mt-4">
            Платили в браузере?{' '}
            <Link to="/subscriptions" className="text-tomato font-medium hover:underline">
              Открыть подписку
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
