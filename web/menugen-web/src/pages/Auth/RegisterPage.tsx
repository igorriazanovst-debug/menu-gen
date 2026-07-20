// MG_REG: страница регистрации. Создаёт пользователя (по умолчанию бесплатный
// тариф — семью и Free-подписку заводит бэкенд), сразу логинит.
import React, { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { register as registerThunk, clearError } from '../../store/slices/authSlice';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

const schema = z.object({
  name: z.string().min(1, 'Введите имя'),
  email: z.string().email('Введите корректный email'),
  password: z.string().min(5, 'Минимум 5 символов'),
  password2: z.string().min(5, 'Минимум 5 символов'),
}).refine((d) => d.password === d.password2, {
  message: 'Пароли не совпадают',
  path: ['password2'],
});
type FormData = z.infer<typeof schema>;

export const RegisterPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { loading, error, user } = useAppSelector((s) => s.auth);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);
  useEffect(() => { return () => { dispatch(clearError()); }; }, [dispatch]);

  const onSubmit = (data: FormData) => dispatch(registerThunk(data));

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-text">MenuGen</h1>
          <p className="text-muted mt-1 text-sm">Бесконечный вкусный мир</p>
        </div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          <h2 className="text-xl font-semibold text-text mb-6">Регистрация</h2>
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input label="Имя" type="text" {...register('name')} error={errors.name?.message} />
            <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
            <Input label="Пароль" type="password" {...register('password')} error={errors.password?.message} />
            <Input label="Повторите пароль" type="password" {...register('password2')} error={errors.password2?.message} />
            <Button type="submit" loading={loading} className="w-full mt-2">
              Зарегистрироваться
            </Button>
          </form>
          <p className="text-sm text-muted text-center mt-5">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="text-tomato font-medium hover:underline">Войти</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
