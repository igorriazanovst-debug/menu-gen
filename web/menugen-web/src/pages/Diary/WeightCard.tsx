// MG_TRAINER: вес за день и недавние замеры.
//
// Раньше вес жил одним числом в профиле и перезаписывался — динамики не было
// ни у пользователя, ни у тренера. Здесь запись за выбранную дату: повторная
// запись за тот же день правит замер, а не добавляет вторую точку.
import React, { useCallback, useEffect, useState } from 'react';
import { diaryApi, type DiaryWeightPoint } from '../../api/diary';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { apiErrorMessage } from '../../utils/apiError';
import { weightDelta } from '../../utils/weightDelta';

export const WeightCard: React.FC<{ date: string; memberId?: number }> = ({ date, memberId }) => {
  const [points, setPoints] = useState<DiaryWeightPoint[]>([]);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await diaryApi.getWeight(90, memberId);
      setPoints(rows);
      const today = rows.find((p) => p.date === date);
      setValue(today ? today.weight_kg : '');
    } catch {
      // Отсутствие замеров — не ошибка: карточка просто пустая.
      setPoints([]);
    }
  }, [date, memberId]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    if (!value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await diaryApi.setWeight(date, value.trim(), '', memberId);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось сохранить вес.');
    } finally {
      setBusy(false);
    }
  };

  const delta = weightDelta(points);
  const recent = points.slice(-5).reverse();

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-chocolate">⚖️ Вес</div>
        {delta !== null && (
          <div className="text-sm text-gray-500">
            {delta > 0 ? '+' : delta < 0 ? '−' : ''}
            {Math.abs(delta).toFixed(1)} кг за период
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          step="0.1"
          min="0"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="кг"
          className="w-28 rounded-xl border border-gray-300 px-3 py-1.5 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none"
        />
        <Button variant="ghost" onClick={save} disabled={busy || !value.trim()}>
          Записать
        </Button>
        <span className="text-xs text-gray-400">за {date}</span>
      </div>
      {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
      {recent.length > 0 && (
        <div className="mt-3 pt-3 border-t space-y-1">
          {recent.map((p) => (
            <div key={p.date} className="flex justify-between text-sm text-chocolate">
              <span className="text-gray-400">{p.date}</span>
              <span>{p.weight_kg} кг</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
