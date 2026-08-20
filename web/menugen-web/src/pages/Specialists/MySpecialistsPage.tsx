// MG_SPECINVITE: «Мои специалисты» — кто имеет доступ к данным семьи.
//
// Раньше этого экрана не было: клиент не видел, кто читает его дневник и правит
// меню, и не мог это прекратить — завершить доступ умел только сам специалист.
// Для доступа к чужим данным это неправильно: право прекратить должно быть у
// того, чьи данные читают.
//
// Здесь же оба способа подключить специалиста: по его e-mail (нужен премиум) и
// по коду, который специалист выдаёт сам — код заодно даёт месяц премиума.
import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/client';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import { apiErrorMessage } from '../../utils/apiError';
import {
  LEVEL_LABELS,
  SECTION_LABELS,
  specialistTypeLabel,
  type AccessSection,
  type SpecialistPermissions,
} from '../../constants/specialist';
import { MyRecommendations } from './MyRecommendations'; // MG_TRAINER

interface MySpecialist {
  id: number;
  specialist_name: string;
  specialist_email: string;
  role: string;
  permissions: SpecialistPermissions;
  status: 'pending' | 'active' | 'ended';
  assigned_at: string;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'ожидает подтверждения специалистом',
  active: 'доступ открыт',
};

export const MySpecialistsPage: React.FC = () => {
  const [rows, setRows] = useState<MySpecialist[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    const { data } = await api.get<MySpecialist[]>('/specialists/my/');
    setRows(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const invite = async () => {
    setError('');
    setSuccess('');
    if (!email.trim()) {
      setError('Укажите e-mail специалиста.');
      return;
    }
    setBusy(true);
    try {
      await api.post('/specialists/invite/', { email: email.trim() });
      setEmail('');
      setSuccess('Приглашение отправлено. Доступ откроется, когда специалист его примет.');
      await load();
    } catch (e) {
      setError(apiErrorMessage(e, ['email']) ?? 'Не удалось пригласить специалиста.');
    } finally {
      setBusy(false);
    }
  };

  const redeem = async () => {
    setError('');
    setSuccess('');
    if (!code.trim()) {
      setError('Введите код.');
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post('/subscriptions/promo/redeem/', { code: code.trim() });
      setCode('');
      setSuccess(data?.detail ?? 'Код активирован.');
      await load();
    } catch (e) {
      setError(apiErrorMessage(e) ?? 'Не удалось активировать код.');
    } finally {
      setBusy(false);
    }
  };

  const end = async (row: MySpecialist) => {
    if (!window.confirm(`Прекратить доступ: ${row.specialist_name}?\n\nСпециалист сразу перестанет видеть ваши данные.`)) {
      return;
    }
    await api.post(`/specialists/assignments/${row.id}/end/`);
    await load();
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-chocolate">Мои специалисты</h1>
        <p className="text-sm text-gray-500">
          Кто имеет доступ к данным вашей семьи и в каком объёме.
        </p>
      </div>

      {/* MG_TRAINER: что назначили специалисты — и отметка «сделал» */}
      <MyRecommendations />

      <Card>
        {rows.length === 0 ? (
          <p className="text-sm text-gray-400">
            Доступ никому не выдан. Ваши данные видите только вы и ваша семья.
          </p>
        ) : (
          <ul className="space-y-4">
            {rows.map((row) => (
              <li key={row.id} className="border-b border-gray-100 last:border-0 pb-4 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-chocolate">{row.specialist_name}</p>
                    <p className="text-xs text-gray-400">
                      {row.specialist_email} · {specialistTypeLabel(row.role)}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">{STATUS_LABELS[row.status] ?? row.status}</p>
                  </div>
                  <button
                    onClick={() => end(row)}
                    className="text-sm text-tomato border border-tomato px-3 py-1 rounded-lg hover:bg-tomato hover:text-white transition shrink-0"
                  >
                    Прекратить доступ
                  </button>
                </div>

                {/* Объём доступа — теми же словами, что видит специалист */}
                <ul className="mt-2 text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1">
                  {(Object.keys(SECTION_LABELS) as AccessSection[])
                    .filter((s) => row.permissions?.[s] !== 'none')
                    .map((s) => (
                      <li key={s}>
                        {SECTION_LABELS[s]}: <span className="text-chocolate">{LEVEL_LABELS[row.permissions[s]]}</span>
                      </li>
                    ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {error && <p className="text-tomato text-sm">{error}</p>}
      {success && <p className="text-avocado text-sm">{success}</p>}

      <Card>
        <h2 className="font-semibold text-chocolate mb-1">Код специалиста</h2>
        <p className="text-sm text-gray-500 mb-3">
          Если специалист дал вам код — введите его. Вы получите месяц премиума, а специалист
          сразу получит доступ к вашим данным.
        </p>
        <div className="flex gap-2">
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="SP-XXXX-XXXX-XXXX" />
          <Button onClick={redeem} disabled={busy}>Активировать</Button>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold text-chocolate mb-1">Пригласить по e-mail</h2>
        <p className="text-sm text-gray-500 mb-3">
          Специалист должен быть зарегистрирован в MenuGen и подтверждён. Приглашение доступно
          на премиум-тарифе.
        </p>
        <div className="flex gap-2">
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e-mail специалиста"
            type="email"
          />
          <Button onClick={invite} disabled={busy}>Пригласить</Button>
        </div>
      </Card>
    </div>
  );
};
