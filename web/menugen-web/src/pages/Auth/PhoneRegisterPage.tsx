// MG_PHONEVERIFY: регистрация по телефону с подтверждением в мессенджере.
// Шаги: (1) номер + мессенджер → создаём заявку; (2) подтверждение в боте
// (пользователь делится контактом) с авто-опросом статуса; (3) имя + пароль →
// аккаунт создан и выполнен вход. Подтверждение номера — разовое; дальше вход
// по телефону+паролю (страница /login).
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { phoneRegister, clearError } from '../../store/slices/authSlice';
import { authApi, type MessengerProvider, type PhoneStartResult, type PhoneStatus } from '../../api/auth';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

type Step = 'phone' | 'confirm' | 'finish';

const POLL_MS = 2500;

export const PhoneRegisterPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { loading, error, user } = useAppSelector((s) => s.auth);

  const [step, setStep] = useState<Step>('phone');
  const [phone, setPhone] = useState('');
  const [provider, setProvider] = useState<MessengerProvider>('telegram');
  const [session, setSession] = useState<PhoneStartResult | null>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [status, setStatus] = useState<PhoneStatus>('pending');
  const [mismatchPhone, setMismatchPhone] = useState<string | undefined>();

  // финальная форма
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');

  const [starting, setStarting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);
  useEffect(() => () => { dispatch(clearError()); }, [dispatch]);

  // ── шаг 1: старт заявки ──────────────────────────────────────────────────
  const onStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalErr(null);
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 10) { setLocalErr('Введите корректный номер телефона.'); return; }
    setStarting(true);
    try {
      const { data } = await authApi.phoneStart(phone, provider);
      setSession(data);
      setStatus('pending');
      setStep('confirm');
    } catch (err: any) {
      const d = err.response?.data;
      if (d?.code === 'phone_taken') {
        setLocalErr('Аккаунт с таким телефоном уже есть. Войдите по паролю.');
      } else if (d?.code === 'provider_unavailable') {
        setLocalErr('Подтверждение через этот мессенджер пока недоступно.');
      } else {
        setLocalErr(d?.detail || 'Не удалось начать подтверждение. Попробуйте позже.');
      }
    } finally {
      setStarting(false);
    }
  };

  // ── шаг 2: опрос статуса ─────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'confirm' || !session) return;
    const tick = async () => {
      try {
        const { data } = await authApi.phoneStatus(session.token);
        setStatus(data.status);
        setMismatchPhone(data.messenger_phone);
        if (data.status === 'verified') {
          stopPolling();
          setStep('finish');
        } else if (data.status === 'expired') {
          stopPolling();
        }
      } catch { /* сеть моргнула — попробуем на следующем тике */ }
    };
    pollRef.current = setInterval(tick, POLL_MS);
    tick();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, session]);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const restart = () => {
    stopPolling();
    setSession(null);
    setStatus('pending');
    setMismatchPhone(undefined);
    setLocalErr(null);
    setStep('phone');
  };

  // ── шаг 3: завершение регистрации ────────────────────────────────────────
  const onFinish = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalErr(null);
    if (!name.trim()) { setLocalErr('Введите имя.'); return; }
    if (password.length < 5) { setLocalErr('Пароль — минимум 5 символов.'); return; }
    if (password !== password2) { setLocalErr('Пароли не совпадают.'); return; }
    if (!session) return;
    try {
      await dispatch(phoneRegister({ token: session.token, name, password, password2 })).unwrap();
      // при успехе user проставится → редирект в useEffect
    } catch { /* ошибка в state.error */ }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-text">MenuGen</h1>
          <p className="text-muted mt-1 text-sm">Бесконечный вкусный мир</p>
        </div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          {/* ─────────── Шаг 1: номер + мессенджер ─────────── */}
          {step === 'phone' && (
            <>
              <h2 className="text-xl font-semibold text-text mb-6">Регистрация по телефону</h2>
              {localErr && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                  {localErr}
                </div>
              )}
              <form onSubmit={onStart} className="space-y-4">
                <Input
                  label="Телефон"
                  type="tel"
                  placeholder="+7 900 000-00-00"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  hint="Номер, привязанный к вашему мессенджеру"
                />
                <div>
                  <p className="text-sm font-medium text-chocolate mb-2">Подтверждение через</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setProvider('telegram')}
                      className={[
                        'rounded-xl border px-3 py-2 text-sm font-medium transition',
                        provider === 'telegram'
                          ? 'border-tomato bg-tomato/10 text-tomato'
                          : 'border-gray-300 text-muted hover:border-tomato/50',
                      ].join(' ')}
                    >
                      ✈️ Telegram
                    </button>
                    <button
                      type="button"
                      onClick={() => setProvider('max')}
                      className={[
                        'rounded-xl border px-3 py-2 text-sm font-medium transition',
                        provider === 'max'
                          ? 'border-tomato bg-tomato/10 text-tomato'
                          : 'border-gray-300 text-muted hover:border-tomato/50',
                      ].join(' ')}
                    >
                      💬 Max
                    </button>
                  </div>
                </div>
                <Button type="submit" loading={starting} className="w-full mt-2">
                  Продолжить
                </Button>
              </form>
              <p className="text-sm text-muted text-center mt-5">
                Уже есть аккаунт?{' '}
                <Link to="/login" className="text-tomato font-medium hover:underline">Войти</Link>
              </p>
              <p className="text-sm text-muted text-center mt-2">
                <Link to="/register" className="text-tomato font-medium hover:underline">
                  Регистрация по e-mail
                </Link>
              </p>
            </>
          )}

          {/* ─────────── Шаг 2: подтверждение в боте ─────────── */}
          {step === 'confirm' && session && (
            <div className="text-center">
              <div className="text-5xl mb-3">📱</div>
              <h2 className="text-xl font-semibold text-text mb-2">Подтвердите номер</h2>
              <p className="text-sm text-muted mb-5">
                Откройте бота <span className="font-medium text-text">@{session.bot_username}</span>,
                нажмите «Старт» и поделитесь своим контактом.
              </p>

              <a href={session.deep_link} target="_blank" rel="noopener noreferrer">
                <Button className="w-full mb-4">
                  Открыть бота в {session.provider === 'max' ? 'Max' : 'Telegram'}
                </Button>
              </a>

              {status === 'pending' && (
                <div className="flex items-center justify-center gap-2 text-sm text-muted">
                  <svg className="animate-spin h-4 w-4 text-tomato" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Ожидаем подтверждения…
                </div>
              )}

              {status === 'mismatch' && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                  Номер в мессенджере{mismatchPhone ? ` (${mismatchPhone})` : ''} не совпал с введённым.
                  Проверьте номер и начните заново.
                </div>
              )}

              {status === 'expired' && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                  Время подтверждения истекло. Начните заново.
                </div>
              )}

              <button
                onClick={restart}
                className="mt-5 text-sm text-tomato font-medium hover:underline"
              >
                ← Изменить номер
              </button>
            </div>
          )}

          {/* ─────────── Шаг 3: имя + пароль ─────────── */}
          {step === 'finish' && (
            <>
              <div className="mb-4 p-3 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm text-center">
                Номер подтверждён ✅ Придумайте пароль для входа.
              </div>
              {error && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                  {error}
                </div>
              )}
              {localErr && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                  {localErr}
                </div>
              )}
              <form onSubmit={onFinish} className="space-y-4">
                <Input label="Имя" type="text" value={name} onChange={(e) => setName(e.target.value)} />
                <Input
                  label="Пароль"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  hint="Минимум 5 символов"
                />
                <Input
                  label="Повторите пароль"
                  type="password"
                  value={password2}
                  onChange={(e) => setPassword2(e.target.value)}
                />
                <Button type="submit" loading={loading} className="w-full mt-2">
                  Завершить регистрацию
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
