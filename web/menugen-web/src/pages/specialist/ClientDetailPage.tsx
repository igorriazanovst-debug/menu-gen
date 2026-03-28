import React, { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../../hooks/useAppDispatch";
import {
  endAssignment,
  fetchClientMenus,
  fetchClientRecommendations,
  fetchClients,
} from "../../store/specialistSlice";

const MEAL_LABELS: Record<string, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  dinner: "Ужин",
  snack: "Перекус",
};

const REC_TYPE_LABELS: Record<string, string> = {
  supplement: "БАД",
  food: "Питание",
  exercise: "Упражнение",
  other: "Другое",
};

export const ClientDetailPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();
  const fid = Number(familyId);
  const dispatch = useAppDispatch();
  const { clients, selectedClientMenus, selectedClientRecs, loading } =
    useAppSelector((s) => s.specialist);

  const client = clients.find((c) => c.id === fid);

  useEffect(() => {
    dispatch(fetchClientMenus(fid));
    dispatch(fetchClientRecommendations(fid));
  }, [dispatch, fid]);

  const handleEnd = () => {
    const assignment = client?.assignment_id;
    if (!assignment) return;
    if (!window.confirm("Завершить работу с клиентом?")) return;
    dispatch(endAssignment(assignment)).then(() => dispatch(fetchClients()));
  };

  if (loading && !client) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-tomato" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/specialist"
            className="text-sm text-avocado hover:underline mb-1 inline-block"
          >
            ← Назад к клиентам
          </Link>
          <h1 className="text-2xl font-bold text-chocolate">
            {client?.name ?? `Семья #${fid}`}
          </h1>
        </div>
        <button
          onClick={handleEnd}
          className="text-sm text-tomato border border-tomato px-3 py-1.5 rounded-lg hover:bg-tomato hover:text-white transition"
        >
          Завершить работу
        </button>
      </div>

      {/* Участники */}
      {client && (
        <section className="bg-white rounded-xl shadow p-4">
          <h2 className="font-semibold text-chocolate mb-3">Участники семьи</h2>
          <div className="divide-y">
            {client.members.map((m) => (
              <div key={m.id} className="py-2 flex items-center justify-between">
                <span className="text-chocolate">{m.name}</span>
                <span className="text-xs text-gray-400">{m.email}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Меню */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-chocolate">Меню</h2>
        </div>
        {selectedClientMenus.length === 0 ? (
          <p className="text-sm text-gray-400">Нет меню.</p>
        ) : (
          <div className="space-y-2">
            {selectedClientMenus.map((menu) => (
              <Link
                key={menu.id}
                to={`/specialist/clients/${fid}/menus/${menu.id}`}
                className="bg-white rounded-xl shadow px-4 py-3 flex items-center justify-between hover:shadow-md transition"
              >
                <div>
                  <p className="font-medium text-chocolate">
                    {menu.start_date} — {menu.end_date}
                  </p>
                  <p className="text-xs text-gray-400">{menu.period_days} дней</p>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    menu.status === "active"
                      ? "bg-avocado/20 text-avocado"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {menu.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Рекомендации */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-chocolate">Рекомендации</h2>
          <Link
            to={`/specialist/clients/${fid}/recommendations/new`}
            className="bg-tomato text-white text-sm px-4 py-1.5 rounded-lg hover:bg-red-700"
          >
            + Добавить
          </Link>
        </div>
        {selectedClientRecs.filter((r) => r.is_active).length === 0 ? (
          <p className="text-sm text-gray-400">Нет активных рекомендаций.</p>
        ) : (
          <div className="space-y-2">
            {selectedClientRecs
              .filter((r) => r.is_active)
              .map((r) => (
                <div
                  key={r.id}
                  className="bg-white rounded-xl shadow px-4 py-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-chocolate">{r.name}</span>
                    <span className="text-xs bg-lemon/30 text-yellow-700 px-2 py-0.5 rounded-full">
                      {REC_TYPE_LABELS[r.rec_type]}
                    </span>
                  </div>
                  {r.dosage && (
                    <p className="text-sm text-gray-500 mt-1">Доза: {r.dosage}</p>
                  )}
                  {r.frequency && (
                    <p className="text-sm text-gray-500">Частота: {r.frequency}</p>
                  )}
                  {r.member_name && (
                    <p className="text-xs text-gray-400 mt-1">
                      Для: {r.member_name}
                    </p>
                  )}
                </div>
              ))}
          </div>
        )}
      </section>
    </div>
  );
};
