// MG_TRAINER: вес за день и недавние замеры.
//
// Раньше вес жил одним числом в профиле и перезаписывался — динамики не было
// ни у пользователя, ни у тренера. Здесь запись за выбранную дату: повторная
// запись за тот же день правит замер, а не добавляет вторую точку.
//
// MG_DAYFIX: дата у карточки не своя, а та, что выбрана вверху страницы, —
// одна на весь дневник. Три отдельных календаря на одной странице путали бы:
// человек правил бы вес за одно число, а еду видел за другое. Поэтому строка
// в списке замеров кликабельна: она переключает день всей страницы, и дальше
// замер правится или удаляется как сегодняшний. Пустое поле за выбранный день
// значит «замера не было» — впишите, и он появится.
import React, { useCallback, useEffect, useState } from 'react';
import { diaryApi, type DiaryWeightPoint } from '../../api/diary';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { apiErrorMessage } from '../../utils/apiError';
import { weightDelta } from '../../utils/weightDelta';
import { WeightChart } from './WeightChart'; // MG_BODYCHART
import { AddedByMark } from '../../components/diary/AddedByMark'; // MG_HEADKEEPS
import { useShowChart } from '../../utils/showChart'; // MG_BODYCHART

interface Props {
  date: string;
  memberId?: number;
  /** Переключить день всей страницы — по клику на прошлый замер. */
  onPickDate?: (date: string) => void;
}

export const WeightCard: React.FC<Props> = ({ date, memberId, onPickDate }) => {
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

  // MG_DAYFIX: замер за выбранный день, если он есть. От него зависит, что
  // показывать — «Записать» или «Изменить», и давать ли удаление.
  const forDate = points.find((p) => p.date === date) ?? null;

  const remove = async () => {
    if (!window.confirm(`Убрать замер веса за ${date}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await diaryApi.deleteWeight(date, memberId);
      setValue('');
      await load();
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось убрать замер.');
    } finally {
      setBusy(false);
    }
  };

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
  // MG_BODYCHART: график по желанию. Выбор запоминается: человек либо смотрит
  // динамику каждый день, либо она ему не нужна вовсе, и спрашивать заново
  // при каждом заходе незачем.
  const [showChart, setShowChart] = useShowChart('weight');

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-chocolate">⚖️ Вес</div>
        <div className="flex items-center gap-3">
          {delta !== null && (
            <div className="text-sm text-gray-500">
              {delta > 0 ? '+' : delta < 0 ? '−' : ''}
              {Math.abs(delta).toFixed(1)} кг за период
            </div>
          )}
          {/* Кнопку показываем всегда, даже когда замеров ещё нет: иначе про
              график не узнать — он появлялся бы сам собой на третьей неделе, а
              человек к тому времени уже решил, что графика в программе нет.
              Пустой график объясняет, чего ему не хватает. */}
          <button type="button" onClick={() => setShowChart(!showChart)}
                  className="text-xs text-avocado hover:underline">
            {showChart ? 'скрыть график' : 'показать график'}
          </button>
        </div>
      </div>
      {showChart && <WeightChart points={points} />}
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
          {forDate ? 'Изменить' : 'Записать'}
        </Button>
        {forDate && (
          <button type="button" onClick={remove} disabled={busy}
                  className="text-xs text-gray-400 hover:text-red-600">
            убрать
          </button>
        )}
        <span className="text-xs text-gray-400">за {date}</span>
      </div>
      {!forDate && (
        <p className="text-xs text-gray-400 mt-1">
          За этот день замера нет — впишите вес, и он появится.
        </p>
      )}
      {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
      {recent.length > 0 && (
        <div className="mt-3 pt-3 border-t space-y-1">
          {recent.map((p) => (
            <button key={p.date} type="button"
                    onClick={() => onPickDate?.(p.date)}
                    className={`w-full flex justify-between text-sm text-chocolate rounded-lg px-1 -mx-1 ${
                      onPickDate ? 'hover:bg-rice cursor-pointer' : 'cursor-default'
                    } ${p.date === date ? 'bg-rice' : ''}`}
                    title={onPickDate ? 'Открыть этот день — можно поправить или убрать' : undefined}>
              <span className="text-gray-400">
                {p.date}
                {/* MG_HEADKEEPS: замер внёс не сам человек. */}
                <AddedByMark name={p.added_by_name} className="ml-1" />
              </span>
              <span>{p.weight_kg} кг</span>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
};
