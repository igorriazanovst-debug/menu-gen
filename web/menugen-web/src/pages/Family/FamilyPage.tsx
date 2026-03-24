import React, { useEffect, useState } from 'react';
import { familyApi } from '../../api/family';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { Family } from '../../types';

export const FamilyPage: React.FC = () => {
  const [family, setFamily] = useState<Family | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await familyApi.get();
      setFamily(data);
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true); setInviteError(''); setInviteSuccess('');
    try {
      await familyApi.invite(inviteEmail.trim());
      setInviteSuccess(`${inviteEmail} успешно приглашён!`);
      setInviteEmail('');
      load();
    } catch (e) { setInviteError(getErrorMessage(e)); }
    finally { setInviting(false); }
  };

  const handleRemove = async (memberId: number, name: string) => {
    if (!window.confirm(`Удалить ${name} из семьи?`)) return;
    try {
      await familyApi.removeMember(memberId);
      load();
    } catch (e) { alert(getErrorMessage(e)); }
  };

  if (loading) return <PageSpinner />;
  if (error) return (
    <div className="text-center py-16">
      <p className="text-red-600">{error}</p>
      <Button variant="ghost" className="mt-4" onClick={load}>Повторить</Button>
    </div>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-chocolate">Семья</h1>

      {family && (
        <>
          <Card className="p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-tomato/10 flex items-center justify-center text-2xl">👨‍👩‍👧</div>
              <div>
                <h2 className="font-semibold text-chocolate text-lg">{family.name}</h2>
                <p className="text-sm text-gray-500">Глава: {family.owner_name}</p>
              </div>
            </div>

            <h3 className="font-medium text-chocolate mb-3">
              Участники ({family.members.length})
            </h3>
            <div className="space-y-2">
              {family.members.map((m) => (
                <div key={m.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-rice">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-avocado/10 flex items-center justify-center font-semibold text-avocado text-sm">
                      {m.name[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-chocolate">{m.name}</p>
                      {m.email && <p className="text-xs text-gray-400">{m.email}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge color={m.role === 'head' ? 'red' : 'gray'}>
                      {m.role === 'head' ? 'Глава' : 'Участник'}
                    </Badge>
                    {m.role !== 'head' && (
                      <button onClick={() => handleRemove(m.id, m.name)}
                        className="text-xs text-red-400 hover:text-red-600 transition">
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Invite */}
          <Card className="p-5">
            <h2 className="font-semibold text-chocolate mb-4">Пригласить участника</h2>
            {inviteSuccess && (
              <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
                {inviteSuccess}
              </div>
            )}
            <form onSubmit={handleInvite} className="flex gap-3">
              <Input
                className="flex-1"
                placeholder="Email участника"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                error={inviteError}
              />
              <Button type="submit" loading={inviting}>Пригласить</Button>
            </form>
          </Card>
        </>
      )}
    </div>
  );
};
