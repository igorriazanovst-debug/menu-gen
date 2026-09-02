import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { AndroidDownload } from '../../components/app/AndroidDownload'; // MG_APKSITE
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { login, loginPhone, clearError } from '../../store/slices/authSlice';
import { authApi } from '../../api/auth';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { PhoneInput, DEFAULT_PHONE_CODE } from '../../components/ui/PhoneInput'; // MG_PHONECODE

const schema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(5, 'Минимум 5 символов'), // MG_208_V_web_login
});
type FormData = z.infer<typeof schema>;

// MG_PHONEVERIFY: вход по телефону — отдельная простая форма (телефон+пароль).
type LoginMode = 'email' | 'phone';

export const LoginPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { loading, error, user } = useAppSelector((s) => s.auth);

  const [mode, setMode] = useState<LoginMode>('email');
  // MG_PHONECODE: поле не пустое, а с уже подставленным кодом страны.
  const [phone, setPhone] = useState(DEFAULT_PHONE_CODE);
  const [phonePassword, setPhonePassword] = useState('');

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  // MG_EMAILVERIFY: если e-mail не подтверждён — предлагаем отправить письмо снова.
  const [needVerify, setNeedVerify] = useState<string | null>(null);
  const [resendMsg, setResendMsg] = useState<string | null>(null);

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);
  useEffect(() => { return () => { dispatch(clearError()); }; }, [dispatch]);

  const switchMode = (m: LoginMode) => {
    if (m === mode) return;
    dispatch(clearError());
    setNeedVerify(null); setResendMsg(null);
    setMode(m);
  };

  const onSubmit = async (data: FormData) => {
    setNeedVerify(null); setResendMsg(null);
    try {
      await dispatch(login(data)).unwrap();
    } catch (payload: any) {
      if (payload?.code === 'email_not_verified') setNeedVerify(payload.email || data.email);
    }
  };

  const onSubmitPhone = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await dispatch(loginPhone({ phone, password: phonePassword })).unwrap();
    } catch { /* ошибка в state.error */ }
  };

  const resend = async () => {
    if (!needVerify) return;
    setResendMsg(null);
    try {
      await authApi.resendVerification(needVerify);
      setResendMsg('Письмо отправлено. Проверьте почту.');
    } catch {
      setResendMsg('Не удалось отправить письмо. Попробуйте позже.');
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          {/* MG_SKIN: слот логотипа (заменить на <Logo/> ~h-14 цветной на светлом фоне) */}
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-text">MenuGen</h1>
          <p className="text-muted mt-1 text-sm">Бесконечный вкусный мир</p>
        </div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          <h2 className="text-xl font-semibold text-text mb-6">Вход в аккаунт</h2>

          {/* MG_PHONEVERIFY: переключатель способа входа */}
          <div className="grid grid-cols-2 gap-2 mb-6">
            <button
              type="button"
              onClick={() => switchMode('email')}
              className={[
                'rounded-xl border px-3 py-2 text-sm font-medium transition',
                mode === 'email'
                  ? 'border-tomato bg-tomato/10 text-tomato'
                  : 'border-gray-300 text-muted hover:border-tomato/50',
              ].join(' ')}
            >
              E-mail
            </button>
            <button
              type="button"
              onClick={() => switchMode('phone')}
              className={[
                'rounded-xl border px-3 py-2 text-sm font-medium transition',
                mode === 'phone'
                  ? 'border-tomato bg-tomato/10 text-tomato'
                  : 'border-gray-300 text-muted hover:border-tomato/50',
              ].join(' ')}
            >
              Телефон
            </button>
          </div>

          {error && !needVerify && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}
          {needVerify && (
            <div className="mb-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
              E-mail <span className="font-medium">{needVerify}</span> не подтверждён.
              <button type="button" onClick={resend} className="ml-1 font-medium text-tomato hover:underline">
                Отправить письмо снова
              </button>
              {resendMsg && <div className="mt-1 text-tomato">{resendMsg}</div>}
            </div>
          )}
          {mode === 'email' ? (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
              <Input label="Пароль" type="password" {...register('password')} error={errors.password?.message} />
              <Button type="submit" loading={loading} className="w-full mt-2">
                Войти
              </Button>
              {/* MG_PWDRESET: восстановление только по e-mail — письмо слать
                  больше некуда. У входа по телефону этой ссылки нет намеренно. */}
              <p className="text-sm text-center">
                <Link to="/forgot-password" className="text-muted hover:text-tomato hover:underline">
                  Забыли пароль?
                </Link>
              </p>
            </form>
          ) : (
            <form onSubmit={onSubmitPhone} className="space-y-4">
              {/* MG_PHONECODE: код страны выбирается, а не набирается вручную */}
              <PhoneInput value={phone} onChange={setPhone} />
              <Input
                label="Пароль"
                type="password"
                value={phonePassword}
                onChange={(e) => setPhonePassword(e.target.value)}
              />
              <Button type="submit" loading={loading} className="w-full mt-2">
                Войти
              </Button>
            </form>
          )}
          <p className="text-sm text-muted text-center mt-5">
            Нет аккаунта?{' '}
            <Link to="/register" className="text-tomato font-medium hover:underline">По e-mail</Link>
            {' · '}
            <Link to="/register/phone" className="text-tomato font-medium hover:underline">По телефону</Link>
          </p>

          {/* MG_APKSITE: приложение можно поставить, не дожидаясь магазина. */}
          <AndroidDownload />
        </div>
      </div>
    </div>
  );
};
