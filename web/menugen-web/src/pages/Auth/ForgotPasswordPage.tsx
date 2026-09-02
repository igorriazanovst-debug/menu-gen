// MG_PWDRESET: «забыли пароль» — /forgot-password
//
// Страница публичная и лежит вне PrivateRoute: человек, забывший пароль, войти
// не может по определению.
//
// Два способа, потому что аккаунты бывают двух видов. У зарегистрированного по
// e-mail ссылка уходит письмом. У зарегистрированного по телефону e-mail может
// не быть вовсе — ему ссылка уходит в тот мессенджер, где он подтверждал номер
// при регистрации. Отдельного доказательства владения для этого не понадобилось:
// диалог с ботом, в котором человек делился контактом, и есть доказательство.
//
// Ответ одинаков для существующего и несуществующего адреса (номера) — иначе
// форма превратилась бы в проверку «зарегистрирован ли такой», доступную кому
// угодно. По той же причине здесь не показывается сетевая ошибка: два разных
// исхода на экране выдали бы ровно то, что мы прячем.
import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { PhoneInput, DEFAULT_PHONE_CODE } from '../../components/ui/PhoneInput'; // MG_PHONECODE

type Mode = 'email' | 'phone';

export const ForgotPasswordPage: React.FC = () => {
  // Со страницы входа приходим уже в нужной вкладке: человек, который вводил
  // телефон, ищет восстановление по телефону, а не по адресу.
  const [params] = useSearchParams();
  const [mode, setMode] = useState<Mode>(params.get('mode') === 'phone' ? 'phone' : 'email');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState(DEFAULT_PHONE_CODE);
  const [state, setState] = useState<'form' | 'sending' | 'sent'>('form');

  const byPhone = mode === 'phone';
  const filled = byPhone ? phone.replace(/\D/g, '').length >= 10 : email.trim().length > 0;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!filled) return;
    setState('sending');
    try {
      await authApi.requestPasswordReset(byPhone ? { phone } : { email: email.trim() });
    } catch {
      // Молча: см. комментарий в шапке файла.
    }
    setState('sent');
  };

  const tab = (m: Mode, label: string) => (
    <button
      type="button"
      onClick={() => setMode(m)}
      className={[
        'rounded-xl border px-3 py-2 text-sm font-medium transition',
        mode === m
          ? 'border-tomato bg-tomato/10 text-tomato'
          : 'border-gray-300 text-muted hover:border-tomato/50',
      ].join(' ')}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-text">MenuGen</h1>
        </div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          {state === 'sent' ? (
            <>
              <h2 className="text-xl font-semibold text-text mb-3">
                {byPhone ? 'Ссылка отправлена' : 'Письмо отправлено'}
              </h2>
              {byPhone ? (
                <>
                  <p className="text-sm text-muted mb-3">
                    Если аккаунт с номером <span className="font-medium text-text">{phone}</span>{' '}
                    существует, мы отправили ссылку для смены пароля в мессенджер, где вы
                    подтверждали номер. Ссылка действует 2 часа.
                  </p>
                  <p className="text-sm text-muted">
                    Сообщения нет? Проверьте, что бот не заблокирован, и что номер введён тот же,
                    с которым вы регистрировались.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-muted mb-3">
                    Если аккаунт с адресом <span className="font-medium text-text">{email}</span>{' '}
                    существует, мы отправили на него ссылку для смены пароля. Ссылка действует
                    2 часа.
                  </p>
                  <p className="text-sm text-muted">
                    Письма нет? Проверьте папку «Спам» и убедитесь, что адрес тот же, с которым вы
                    регистрировались.
                  </p>
                </>
              )}
              <p className="text-sm text-muted text-center mt-6">
                <Link to="/login" className="text-tomato font-medium hover:underline">
                  Вернуться ко входу
                </Link>
              </p>
            </>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-text mb-2">Восстановление пароля</h2>
              <p className="text-sm text-muted mb-6">
                {byPhone
                  ? 'Укажите номер, на который зарегистрирован аккаунт. Пришлём ссылку в мессенджер, где вы подтверждали номер.'
                  : 'Укажите адрес, на который зарегистрирован аккаунт. Пришлём письмо со ссылкой — по ней можно будет задать новый пароль.'}
              </p>
              <div className="grid grid-cols-2 gap-2 mb-6">
                {tab('email', 'E-mail')}
                {tab('phone', 'Телефон')}
              </div>
              <form onSubmit={submit} className="space-y-4">
                {byPhone ? (
                  <PhoneInput value={phone} onChange={setPhone} />
                ) : (
                  <Input
                    label="Email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                )}
                <Button type="submit" loading={state === 'sending'} className="w-full mt-2">
                  Прислать ссылку
                </Button>
              </form>
              <p className="text-sm text-muted text-center mt-5">
                Вспомнили пароль?{' '}
                <Link to="/login" className="text-tomato font-medium hover:underline">
                  Войти
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
