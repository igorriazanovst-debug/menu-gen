// MG_204_V_family = 1
import React, { useEffect, useState } from 'react';
import { familyApi } from '../../api/family';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { Family, FamilyMember, FamilyChoice, FamilyInvite } from '../../types';
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
  // MG_ACTIVEFAMILY / MG_FAMINVITE
  const [choices, setChoices] = useState<FamilyChoice[]>([]);
  const [invites, setInvites] = useState<FamilyInvite[]>([]);
  const [busyFamilyId, setBusyFamilyId] = useState<number | null>(null);
  const [busyInviteId, setBusyInviteId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await familyApi.get();
      setFamily(data);
    } catch (e) { setError(getErrorMessage(e)); }
    finally { setLoading(false); }
    // Список столов и входящие приглашения — не критичны для экрана: если они
    // не пришли, семья всё равно показывается, поэтому ошибки тут глотаем.
    try { setChoices((await familyApi.choices()).data); } catch { /* не блокируем экран */ }
    try { setInvites((await familyApi.myInvites()).data); } catch { /* не блокируем экран */ }
  };

  // MG_ACTIVEFAMILY: переключение перезагружает страницу целиком.
  //
  // Холодильник, меню, покупки и дневник каждый держат своё состояние, и
  // обойти их по одному значило бы однажды забыть какой-нибудь список и
  // показать человеку данные прошлой семьи — то есть чужие. Перезагрузка
  // гарантирует, что после смены стола на экране нет ничего от прежнего.
  const handleSwitch = async (target: FamilyChoice) => {
    if (target.is_active) return;
    setBusyFamilyId(target.id);
    try {
      await familyApi.switchTo(target.id);
      window.location.reload();
    } catch (e) { alert(getErrorMessage(e)); setBusyFamilyId(null); }
  };

  // MG_FAMINVITE: согласие сажает за новый стол, поэтому тоже перезагружаем.
  const handleRespond = async (invite: FamilyInvite, accept: boolean) => {
    setBusyInviteId(invite.id);
    try {
      await familyApi.respondInvite(invite.id, accept);
      if (accept) { window.location.reload(); return; }
      setInvites((prev) => prev.filter((row) => row.id !== invite.id));
    } catch (e) { alert(getErrorMessage(e)); }
    finally { setBusyInviteId(null); }
  };

  const handleCancelInvite = async (inviteId: number, name: string) => {
    if (!window.confirm(`Отозвать приглашение для ${name}?`)) return;
    try {
      await familyApi.cancelInvite(inviteId);
      load();
    } catch (e) { alert(getErrorMessage(e)); }
  };

  useEffect(() => { load(); }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true); setInviteError(''); setInviteSuccess('');
    try {
      await familyApi.invite(inviteEmail.trim());
      // MG_FAMINVITE: приглашение отправлено, но человек ещё не в семье —
      // текст обязан это говорить, иначе глава решит, что дело сделано.
      setInviteSuccess(`Приглашение отправлено на ${inviteEmail}. Участник появится в семье, когда примет его.`);
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

      {/* MG_FAMINVITE: входящие приглашения — первым делом, это требует ответа */}
      {invites.length > 0 && (
        <Card className="p-5 border-2 border-avocado/40">
          <h2 className="font-semibold text-chocolate mb-1">Вас приглашают в семью</h2>
          <p className="text-xs text-gray-500 mb-4">
            Если примете — общими станут холодильник, список покупок и меню, а глава
            семьи сможет видеть и менять ваши нормы КБЖУ. Дневник питания, вода и вес
            останутся вашими. Пока не ответите, ничего не меняется.
          </p>
          <div className="space-y-2">
            {invites.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between p-3 rounded-xl bg-rice">
                <div>
                  <p className="text-sm font-medium text-chocolate">{inv.family_name}</p>
                  <p className="text-xs text-gray-500">
                    {inv.invited_by_name || 'Глава семьи'} · участников: {inv.members_count}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => handleRespond(inv, true)}
                    loading={busyInviteId === inv.id}
                  >
                    Принять
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => handleRespond(inv, false)}
                    loading={busyInviteId === inv.id}
                  >
                    Отклонить
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* MG_ACTIVEFAMILY: переключатель показываем, только когда есть из чего выбирать */}
      {choices.length > 1 && (
        <Card className="p-5">
          <h2 className="font-semibold text-chocolate mb-1">В какой семье вы сейчас</h2>
          <p className="text-xs text-gray-500 mb-4">
            Холодильник, меню, список покупок и подписка — общие для той семьи, в
            которой вы сейчас. Дневник, вода и вес остаются вашими в любой из них.
          </p>
          <div className="space-y-2">
            {choices.map((c) => (
              <div
                key={c.id}
                className={`flex items-center justify-between p-3 rounded-xl ${c.is_active ? 'bg-avocado/10' : 'bg-rice'}`}
              >
                <div>
                  <p className="text-sm font-medium text-chocolate">
                    {c.name}
                    {c.is_own && <span className="text-xs text-gray-400"> · своя</span>}
                  </p>
                  <p className="text-xs text-gray-500">
                    {c.role === 'head' ? 'Глава' : 'Участник'} · участников: {c.members_count}
                    {c.has_premium ? ' · премиум' : ' · без премиума'}
                  </p>
                </div>
                {c.is_active ? (
                  <Badge color="red">Сейчас здесь</Badge>
                ) : (
                  <Button
                    variant="ghost"
                    loading={busyFamilyId === c.id}
                    onClick={() => handleSwitch(c)}
                  >
                    Перейти
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

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

            {/* MG_FAMINVITE: позвали, но ещё не ответили */}
            {(family.pending_invites?.length ?? 0) > 0 && (
              <>
                <h3 className="font-medium text-chocolate mt-5 mb-3">
                  Приглашены ({family.pending_invites!.length})
                </h3>
                <div className="space-y-2">
                  {family.pending_invites!.map((inv) => (
                    <div key={inv.id}
                      className="flex items-center justify-between p-3 rounded-xl bg-rice/60">
                      <div>
                        <p className="text-sm font-medium text-chocolate">{inv.name}</p>
                        <p className="text-xs text-gray-400">{inv.email || inv.phone}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge color="gray">Ждём ответа</Badge>
                        <button onClick={() => handleCancelInvite(inv.id, inv.name)}
                          className="text-xs text-red-400 hover:text-red-600 transition"
                          title="Отозвать приглашение">
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
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
