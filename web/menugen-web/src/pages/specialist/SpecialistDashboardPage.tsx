import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../../hooks/useAppDispatch";
import {
  acceptAssignment,
  fetchClients,
  fetchInviteCode,
  fetchPendingAssignments,
  fetchSpecialistProfile,
} from "../../store/specialistSlice";
import {
  LEVEL_LABELS,
  SECTION_LABELS,
  specialistTypeLabel,
  type AccessSection,
} from "../../constants/specialist"; // MG_SPECACCESS

export const SpecialistDashboardPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { profile, clients, pendingAssignments, inviteCode, loading, error } =
    useAppSelector((s) => s.specialist);

  useEffect(() => {
    dispatch(fetchSpecialistProfile());
    dispatch(fetchClients());
    dispatch(fetchPendingAssignments());
    dispatch(fetchInviteCode()); // MG_SPECINVITE
  }, [dispatch]);

  const handleAccept = (assignmentId: number) => {
    dispatch(acceptAssignment(assignmentId)).then(() => {
      dispatch(fetchClients());
      dispatch(fetchPendingAssignments());
    });
  };

  if (loading && !profile) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-tomato" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <p className="text-chocolate text-lg mb-4">
          Профиль специалиста не найден.
        </p>
        <Link
          to="/specialist/register"
          className="bg-tomato text-white px-6 py-2 rounded-lg hover:bg-red-700"
        >
          Зарегистрироваться как специалист
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
      {/* Профиль */}
      <div className="bg-surface rounded-2xl shadow p-6 flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-avocado flex items-center justify-center text-white text-2xl font-bold">
          {profile.name.charAt(0).toUpperCase()}
        </div>
        <div>
          <h1 className="text-xl font-bold text-chocolate">{profile.name}</h1>
          <p className="text-sm text-gray-500">{profile.email}</p>
          <span
            className={`inline-block mt-1 text-xs px-2 py-0.5 rounded-full font-medium ${
              profile.is_verified
                ? "bg-avocado/20 text-avocado"
                : "bg-lemon/30 text-yellow-700"
            }`}
          >
            {profile.is_verified
              ? `✓ Верифицирован · ${specialistTypeLabel(profile.specialist_type)}`
              : `Ожидает верификации · ${specialistTypeLabel(profile.specialist_type)}`}
          </span>
        </div>
      </div>

      {/* MG_SPECACCESS: что даёт роль. Специалист должен понимать границы
          своего доступа до того, как упрётся в отказ на чужом экране. */}
      {profile.permissions && (
        <section className="bg-surface rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold text-chocolate mb-1">Доступ к данным клиента</h2>
          <p className="text-sm text-gray-400 mb-4">
            Зависит от роли и действует, пока клиент не завершил доступ.
          </p>
          <ul className="text-sm divide-y divide-gray-100">
            {(Object.keys(SECTION_LABELS) as AccessSection[]).map((section) => {
              const level = profile.permissions![section];
              return (
                <li key={section} className="flex items-center justify-between py-2">
                  <span className={level === "none" ? "text-gray-400" : "text-chocolate"}>
                    {SECTION_LABELS[section]}
                  </span>
                  <span
                    className={
                      level === "write"
                        ? "text-avocado font-medium"
                        : level === "read"
                          ? "text-gray-500"
                          : "text-gray-300"
                    }
                  >
                    {LEVEL_LABELS[level]}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* MG_SPECINVITE: личный код — приглашение со стороны специалиста.
          Клиент вводит его у себя и получает месяц премиума, а доступ
          открывается сразу: ввод кода и есть его согласие. */}
      {inviteCode && (
        <section className="bg-surface rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold text-chocolate mb-1">Код приглашения</h2>
          <p className="text-sm text-gray-400 mb-4">
            Дайте код клиенту: он получит {inviteCode.days} дней премиума, а вы — доступ к его
            данным. Клиент может прекратить доступ в любой момент.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <code className="text-lg font-mono bg-lemon/20 border border-lemon rounded-lg px-4 py-2 text-chocolate">
              {inviteCode.code}
            </code>
            <button
              onClick={() => navigator.clipboard?.writeText(inviteCode.code)}
              className="text-sm border border-avocado text-avocado px-3 py-2 rounded-lg hover:bg-avocado hover:text-white transition"
            >
              Скопировать
            </button>
            <span className="text-sm text-gray-400">
              активаций: {inviteCode.redeemed_count} из {inviteCode.max_redemptions}
            </span>
          </div>
        </section>
      )}

      {/* Ожидающие приглашения */}
      {pendingAssignments.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-chocolate mb-3">
            Ожидают подтверждения ({pendingAssignments.length})
          </h2>
          <div className="space-y-2">
            {pendingAssignments.map((a) => (
              <div
                key={a.assignment_id}
                className="bg-lemon/20 border border-lemon rounded-xl px-4 py-3 flex items-center justify-between"
              >
                <span className="text-chocolate font-medium">{a.family_name}</span>
                <button
                  onClick={() => handleAccept(a.assignment_id)}
                  className="bg-avocado text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700"
                >
                  Принять
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Клиенты */}
      <section>
        <h2 className="text-lg font-semibold text-chocolate mb-3">
          Мои клиенты ({clients.length})
        </h2>
        {clients.length === 0 ? (
          <p className="text-gray-400 text-sm">Нет активных клиентов.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {clients.map((c) => (
              <Link
                key={c.id}
                to={`/specialist/clients/${c.id}`}
                className="bg-surface rounded-xl shadow p-4 hover:shadow-md transition"
              >
                <p className="font-semibold text-chocolate">{c.name}</p>
                <p className="text-sm text-gray-500 mt-1">
                  {c.members.length} участн.
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {c.members.slice(0, 3).map((m) => (
                    <span
                      key={m.id}
                      className="text-xs bg-rice text-chocolate px-2 py-0.5 rounded-full"
                    >
                      {m.name}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {error && (
        <p className="text-tomato text-sm text-center">{error}</p>
      )}
    </div>
  );
};
