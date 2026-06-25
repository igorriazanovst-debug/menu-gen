// MG_204_V_family = 1
import React, { useEffect, useState } from 'react';
import { familyApi } from '../../api/family';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { Family, FamilyMember } from '../../types';
import { FamilyMemberEditModal } from '../../components/family/FamilyMemberEditModal';

export const FamilyPage: React.FC = () => {
  const [family, setFamily] = useState<Family | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');
  const [editing, setEditing] = useState<FamilyMember | null>(null);
  // MG_MANAGEDMEMBER: create a member card without inviting anyone.
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

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

  const onMemberSaved = () => {
    // перезагружаем семью, чтобы получить обновлённый профиль
    load();
  };

  // MG_MANAGEDMEMBER: create a member card (no invitation). Open the edit modal
  // afterwards so the head can fill in the profile / nutrition targets.
  const handleCreateManaged = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setCreating(true); setCreateError('');
    try {
      const { data } = await familyApi.createManagedMember({ name });
      setNewName('');
      await load();
      setEditing(data); // let the head fill in the profile right away
    } catch (e) { setCreateError(getErrorMessage(e)); }
    finally { setCreating(false); }
  };

  // MG_MANAGEDMEMBER: give a managed member their own login.
  const handleAttachAccount = async (m: FamilyMember) => {
    const email = window.prompt(`E-mail для входа (${m.name}):`, '');
    if (email === null) return;
    const trimmed = email.trim();
    if (!trimmed) return;
    const password = window.prompt('Пароль (необязательно, можно задать позже через сброс):', '') ?? '';
    try {
      await familyApi.attachAccount(m.id, { email: trimmed, password: password.trim() || undefined });
      await load();
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
                      <div className="flex items-center gap-2">
                        {m.email && <p className="text-xs text-gray-400">{m.email}</p>}
                        {m.profile?.calorie_target && (
                          <span className="text-xs text-gray-400">
                            · {m.profile.calorie_target} ккал · {m.profile.meal_plan_type ?? '3'} прм
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* MG_MANAGEDMEMBER: card without its own login */}
                    {m.is_managed && <Badge color="gray">Без входа</Badge>}
                    <Badge color={(m.role === 'head' || m.role === 'owner') ? 'red' : 'gray'}>
                      {(m.role === 'head' || m.role === 'owner') ? 'Глава' : 'Участник'}
                    </Badge>
                    {m.is_managed && (
                      <button
                        onClick={() => handleAttachAccount(m)}
                        className="text-xs text-gray-500 hover:text-tomato transition px-2 py-1 rounded hover:bg-surface"
                        title="Добавить вход (email/пароль)"
                      >
                        🔑
                      </button>
                    )}
                    <button
                      onClick={() => setEditing(m)}
                      className="text-xs text-gray-500 hover:text-tomato transition px-2 py-1 rounded hover:bg-surface"
                      title="Редактировать"
                    >
                      ✎
                    </button>
                    {(m.role !== 'head' && m.role !== 'owner') && (
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

          {/* MG_MANAGEDMEMBER: add a member card without inviting anyone */}
          <Card className="p-5">
            <h2 className="font-semibold text-chocolate mb-1">Добавить члена семьи</h2>
            <p className="text-xs text-gray-500 mb-4">
              Без приглашения — например, ребёнок без телефона или член семьи, чьё
              питание ведёт специалист. Вход можно добавить позже.
            </p>
            <form onSubmit={handleCreateManaged} className="flex gap-3">
              <Input
                className="flex-1"
                placeholder="Имя"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                error={createError}
              />
              <Button type="submit" loading={creating}>Добавить</Button>
            </form>
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

      {editing && (
        <FamilyMemberEditModal
          member={editing}
          onClose={() => setEditing(null)}
          onSaved={onMemberSaved}
        />
      )}
    </div>
  );
};
