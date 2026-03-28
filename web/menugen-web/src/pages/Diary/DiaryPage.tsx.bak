import React, { useState, useEffect } from 'react';
import client from '../../api/client';
import { Card } from '../../components/ui/Card';
import { PageSpinner } from '../../components/ui/Spinner';
import type { PaginatedResponse } from '../../types';

interface DiaryEntry {
  id: number; date: string; meal_type: string;
  recipe_title?: string; custom_name?: string;
  nutrition: Record<string, { value: string; unit: string }>;
  quantity: number;
}

const MEAL_LABELS: Record<string, string> = {
  breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус',
};

export const DiaryPage: React.FC = () => {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    client.get<PaginatedResponse<DiaryEntry>>('/diary/', { params: { date } })
      .then((r) => setEntries(r.data.results))
      .finally(() => setLoading(false));
  }, [date]);

  const totalCal = entries.reduce((sum, e) => {
    const cal = parseFloat(e.nutrition?.calories?.value ?? '0') * e.quantity;
    return sum + (isNaN(cal) ? 0 : cal);
  }, 0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-chocolate">Дневник питания</h1>

      <div className="flex items-center gap-4">
        <input type="date" value={date}
          max={new Date().toISOString().split('T')[0]}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none" />
        {totalCal > 0 && (
          <div className="px-3 py-1.5 rounded-xl bg-rice text-sm text-chocolate">
            🔥 {Math.round(totalCal)} ккал за день
          </div>
        )}
      </div>

      {loading ? <PageSpinner /> : entries.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📓</div>
          <p>Нет записей за этот день</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <Card key={e.id} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs text-gray-400 uppercase tracking-wide">
                    {MEAL_LABELS[e.meal_type] ?? e.meal_type}
                  </span>
                  <p className="font-medium text-chocolate mt-0.5">
                    {e.recipe_title ?? e.custom_name ?? 'Без названия'}
                  </p>
                </div>
                {e.nutrition?.calories && (
                  <span className="text-sm text-gray-500">
                    {e.nutrition.calories.value} {e.nutrition.calories.unit}
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
