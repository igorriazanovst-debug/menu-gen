// MG_PWDRESET: страница перехода по ссылке из письма — /reset-password?token=…
//
// Токен одноразовый: он подписан отпечатком текущего пароля, поэтому после
// успешной смены та же ссылка перестаёт работать. Отсюда и текст ошибки —
// «устарела или уже использована», а не просто «неверная».
//
// После успеха НЕ логиним и не перекидываем в аккаунт: вход остаётся отдельным
// действием, потому что вход отменяет запланированное удаление аккаунта
// (MG_ACCDEL), и это решение человек должен принять сам.
import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

export const ResetPasswordPage: React.FC = () => {
  const [params] = useSearchParams();
  const token = params.get('token') || '';

  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<'form' | 'saving' | 'done'>('form');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 5) { setError('Пароль — минимум 5 символов.'); return; }
    if (password !== password2) { setError('Пароли не совпадают.'); return; }
    setState('saving');
    try {
      await authApi.confirmPasswordReset(token, password, password2);
      setState('done');
    } catch (err: any) {
      const data = err?.response?.data;
      setError(
        data?.code === 'invalid_token'
          ? 'Ссылка устарела или уже использована. Запросите новую.'
          : data?.detail || 'Не удалось сменить пароль. Попробуйте ещё раз.',
      );
      setState('form');
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-text">MenuGen</h1>
        </div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          {state === 'done' ? (
            <div className="text-center">
              <div className="text-5xl mb-3">✅</div>
              <h2 className="text-xl font-semibold text-text mb-1">Пароль изменён</h2>
              <p className="text-muted text-sm mb-6">Войдите с новым паролем.</p>
              <Link
                to="/login"
                className="block w-full bg-tomato text-white font-medium rounded-xl py-3 hover:opacity-90 transition"
              >
                Перейти ко входу
              </Link>
            </div>
          ) : !token ? (
            <div className="text-center">
              <div className="text-5xl mb-3">⚠️</div>
              <h2 className="text-xl font-semibold text-text mb-1">Ссылка неполная</h2>
              <p className="text-muted text-sm mb-6">
                Откройте её из письма целиком — вместе с частью после знака вопроса.
              </p>
              <Link to="/forgot-password" className="text-tomato font-medium hover:underline text-sm">
                Запросить письмо заново
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-text mb-2">Новый пароль</h2>
              <p className="text-sm text-muted mb-6">Минимум 5 символов.</p>
              {error && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                  {error}
                </div>
              )}
              <form onSubmit={submit} className="space-y-4">
                <Input
                  label="Новый пароль"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <Input
                  label="Повторите пароль"
                  type="password"
                  autoComplete="new-password"
                  value={password2}
                  onChange={(e) => setPassword2(e.target.value)}
                />
                <Button type="submit" loading={state === 'saving'} className="w-full mt-2">
                  Сохранить пароль
                </Button>
              </form>
              <p className="text-sm text-muted text-center mt-5">
                <Link to="/forgot-password" className="text-tomato font-medium hover:underline">
                  Запросить письмо заново
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
