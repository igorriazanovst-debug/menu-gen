// MG_PWDRESET: «забыли пароль» — /forgot-password
//
// Страница публичная и лежит вне PrivateRoute: человек, забывший пароль, войти
// не может по определению.
//
// Ответ одинаков для существующего и несуществующего адреса — иначе форма
// превратилась бы в проверку «зарегистрирован ли такой e-mail», доступную кому
// угодно. По той же причине здесь не показывается сетевая ошибка: два разных
// исхода на экране выдали бы ровно то, что мы прячем.
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'form' | 'sending' | 'sent'>('form');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setState('sending');
    try {
      await authApi.requestPasswordReset(email.trim());
    } catch {
      // Молча: см. комментарий в шапке файла.
    }
    setState('sent');
  };

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
              <h2 className="text-xl font-semibold text-text mb-3">Письмо отправлено</h2>
              <p className="text-sm text-muted mb-3">
                Если аккаунт с адресом <span className="font-medium text-text">{email}</span>{' '}
                существует, мы отправили на него ссылку для смены пароля. Ссылка действует 2 часа.
              </p>
              <p className="text-sm text-muted">
                Письма нет? Проверьте папку «Спам» и убедитесь, что адрес тот же, с которым вы
                регистрировались.
              </p>
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
                Укажите адрес, на который зарегистрирован аккаунт. Пришлём письмо со ссылкой —
                по ней можно будет задать новый пароль.
              </p>
              <form onSubmit={submit} className="space-y-4">
                <Input
                  label="Email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
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
