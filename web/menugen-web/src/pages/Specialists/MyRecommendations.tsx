// MG_TRAINER: рекомендации специалистов — на стороне клиента.
//
// До этого экрана не было: специалист выписывал рекомендации, а клиент их не
// видел нигде. Здесь же отметка «сделал» — по ней специалист понимает, делают
// ли назначенное, а не только открывали ли письмо.
import React, { useCallback, useEffect, useState } from 'react';
import api from '../../api/client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { apiErrorMessage } from '../../utils/apiError';
import { specialistTypeLabel } from '../../constants/specialist';

export interface Recommendation {
  id: number;
  rec_type: string;
  name: string;
  dosage: string;
  frequency: string;
  start_date: string | null;
  end_date: string | null;
  is_read: boolean;
  completed_at: string | null;
  specialist_name: string | null;
  specialist_type: string | null;
  member_name: string | null;
  created_at: string;
}

export const REC_TYPE_LABELS: Record<string, string> = {
  supplement: 'БАД',
  food: 'Питание',
  exercise: 'Упражнение',
  other: 'Другое',
};

/** Подпись срока: открытый интервал и «без срока» — разные вещи. */
export const periodLabel = (from: string | null, to: string | null): string => {
  if (from && to) return `${from} — ${to}`;
  if (from) return `с ${from}`;
  if (to) return `до ${to}`;
  return 'без срока';
};

export const MyRecommendations: React.FC = () => {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<Recommendation[]>('/specialists/recommendations/');
      setItems(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось загрузить рекомендации.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (rec: Recommendation) => {
    const done = !rec.completed_at;
    // Отмечаем сразу, не дожидаясь ответа: галочка должна отзываться мгновенно.
    setItems((prev) =>
      prev.map((r) => (r.id === rec.id ? { ...r, completed_at: done ? new Date().toISOString() : null } : r)),
    );
    try {
      await api.post(`/specialists/recommendations/${rec.id}/done/`, { done });
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось сохранить отметку.');
      load();
    }
  };

  if (loading) return null;
  if (!items.length && !error) return null;

  return (
    <Card className="p-4">
      <h2 className="font-semibold text-chocolate mb-3">Рекомендации специалистов</h2>
      {error && <p className="text-red-600 text-sm mb-2">{error}</p>}
      <div className="space-y-2">
        {items.map((r) => (
          <div key={r.id} className="border rounded-xl px-3 py-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium text-chocolate">{r.name}</p>
                <p className="text-xs text-gray-400">
                  {REC_TYPE_LABELS[r.rec_type] ?? r.rec_type}
                  {r.specialist_name && ` · ${r.specialist_name}`}
                  {r.specialist_type && ` (${specialistTypeLabel(r.specialist_type)})`}
                </p>
                {(r.dosage || r.frequency) && (
                  <p className="text-sm text-gray-500 mt-1">
                    {[r.dosage, r.frequency].filter(Boolean).join(' · ')}
                  </p>
                )}
                <p className="text-xs text-gray-400 mt-1">{periodLabel(r.start_date, r.end_date)}</p>
                {r.member_name && <p className="text-xs text-gray-400">Для: {r.member_name}</p>}
              </div>
              <Button variant="ghost" onClick={() => toggle(r)}>
                {r.completed_at ? '✓ Сделано' : 'Отметить'}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
