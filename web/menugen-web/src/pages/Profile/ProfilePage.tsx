import React, { useState } from 'react';
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { setUser } from '../../store/slices/authSlice';
import { authApi } from '../../api/auth';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { getErrorMessage } from '../../utils/api';

export const ProfilePage: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const [name, setName] = useState(user?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setSuccess(''); setError('');
    try {
      const { data } = await authApi.updateMe({ name });
      dispatch(setUser(data));
      setSuccess('Профиль обновлён!');
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold text-chocolate">Профиль</h1>
      <Card className="p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-tomato/10 flex items-center justify-center text-3xl font-bold text-tomato">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div>
            <p className="font-semibold text-chocolate text-lg">{user?.name}</p>
            <p className="text-sm text-gray-500">{user?.email ?? user?.phone}</p>
          </div>
        </div>
        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {success}
          </div>
        )}
        <form onSubmit={handleSave} className="space-y-4">
          <Input label="Имя" value={name} onChange={(e) => setName(e.target.value)} error={error} />
          <Input label="Email" value={user?.email ?? ''} disabled />
          <Button type="submit" loading={saving}>Сохранить</Button>
        </form>
      </Card>
    </div>
  );
};
