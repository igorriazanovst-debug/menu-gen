import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { login, clearError } from '../../store/slices/authSlice';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

const schema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
});
type FormData = z.infer<typeof schema>;

export const LoginPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { loading, error, user } = useAppSelector((s) => s.auth);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  useEffect(() => { if (user) navigate('/dashboard'); }, [user, navigate]);
  useEffect(() => { return () => { dispatch(clearError()); }; }, [dispatch]);

  const onSubmit = (data: FormData) => dispatch(login(data));

  return (
    <div className="min-h-screen bg-rice flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">🍅</div>
          <h1 className="text-3xl font-bold text-chocolate">MenuGen</h1>
          <p className="text-gray-500 mt-1 text-sm">Бесконечный вкусный мир</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-xl font-semibold text-chocolate mb-6">Вход в аккаунт</h2>
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
            <Input label="Пароль" type="password" {...register('password')} error={errors.password?.message} />
            <Button type="submit" loading={loading} className="w-full mt-2">
              Войти
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};
