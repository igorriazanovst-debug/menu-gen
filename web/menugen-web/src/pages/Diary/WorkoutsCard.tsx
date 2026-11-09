// MG_WORKOUT: физнагрузки за день — список, запись и удаление.
//
// Живёт на вкладке «Тело», рядом с весом и обхватами: это всё про тело, а не
// про еду. Заведено ради тренерской оптики: тренер видел в дневнике одну еду, а
// вопрос «что человек делал на этом калораже» ответа не имел.
//
// Чего карточка НЕ делает: не трогает дневную норму. Норма уже содержит
// коэффициент активности («умеренные нагрузки 3–5 раз в неделю» — множитель
// 1,55), и прибавка за каждую тренировку посчитала бы его дважды. Человеку на
// похудении приложение разрешило бы съесть лишние полтысячи калорий — это
// работа против его цели, а не мелкая неточность. Расход показывается
// отдельным числом и нигде не вычитается.
//
// Отличие от веса: записей на день МНОГО. Пробежка утром и зал вечером — два
// занятия, а не перезапись одного.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { diaryApi, type DiaryActivityType, type DiaryWorkout } from '../../api/diary';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { apiErrorMessage } from '../../utils/apiError';
import { AddedByMark } from '../../components/diary/AddedByMark'; // MG_HEADKEEPS

interface Props {
  date: string;
  memberId?: number;
  /** Расход попал в сводку дня — «Итогам» надо перечитать её. */
  onChanged?: () => void;
}

/** «40 мин» или «1 ч 20 мин»: в минутах длинное занятие читается плохо. */
const duration = (min: number): string => {
  if (min < 60) return `${min} мин`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h} ч` : `${h} ч ${m} мин`;
};

export const WorkoutsCard: React.FC<Props> = ({ date, memberId, onChanged }) => {
  const [rows, setRows] = useState<DiaryWorkout[]>([]);
  const [catalog, setCatalog] = useState<DiaryActivityType[]>([]);
  const [activityId, setActivityId] = useState('');
  const [customName, setCustomName] = useState('');
  const [minutes, setMinutes] = useState('30');
  const [kcal, setKcal] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await diaryApi.getWorkouts(date, memberId));
    } catch {
      // Занятий может не быть вовсе — это не ошибка, список просто пуст.
      setRows([]);
    }
  }, [date, memberId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    // Справочник один на всё время работы страницы: он меняется только
    // миграцией, и перечитывать его на каждую смену дня незачем.
    diaryApi.getActivities().then(setCatalog).catch(() => setCatalog([]));
  }, []);

  // Занятия без калорий в сумму не входят: пустое — это «не из чего считать»,
  // а не ноль.
  const burned = useMemo(
    () => rows.reduce((sum, r) => sum + (r.calories ?? 0), 0),
    [rows],
  );

  // Справочник сгруппирован так же, как его отдал сервер: порядок внутри групп
  // задан там (sort_order), и переупорядочивать его здесь нельзя.
  const groups = useMemo(() => {
    const out: { label: string; items: DiaryActivityType[] }[] = [];
    for (const a of catalog) {
      const label = a.group_label || a.group;
      const last = out[out.length - 1];
      if (last && last.label === label) last.items.push(a);
      else out.push({ label, items: [a] });
    }
    return out;
  }, [catalog]);

  const own = activityId === 'own';
  const canSave = (() => {
    const m = Number(minutes);
    if (!Number.isFinite(m) || m <= 0 || m > 1440) return false;
    return own ? customName.trim().length > 0 : activityId !== '';
  })();

  const save = async () => {
    if (!canSave) return;
    setBusy(true);
    setError(null);
    try {
      const payload = {
        date,
        duration_min: Number(minutes),
        ...(own ? { custom_name: customName.trim() } : { activity: Number(activityId) }),
        ...(kcal.trim() ? { calories: Number(kcal) } : {}),
      };
      await diaryApi.addWorkout(payload, memberId);
      setCustomName('');
      setKcal('');
      await load();
      onChanged?.();
    } catch (err) {
      // Причину отказа говорим словами сервера: он отвечает по делу, и общее
      // «не удалось» заставляет человека гадать, что именно не так.
      setError(apiErrorMessage(err) ?? 'Не удалось записать занятие.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (row: DiaryWorkout) => {
    if (!window.confirm(`Убрать «${row.title}» за ${date}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await diaryApi.deleteWorkout(row.id);
      await load();
      onChanged?.();
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось убрать занятие.');
    } finally {
      setBusy(false);
    }
  };

  const field =
    'rounded-xl border border-gray-300 px-3 py-1.5 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none';

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-chocolate">🏃 Занятия</div>
        {burned > 0 && <div className="text-sm text-gray-500">{burned} ккал</div>}
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-gray-400 mb-3">За этот день занятий не записано.</p>
      ) : (
        <div className="space-y-2 mb-3">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm text-chocolate truncate">
                  {r.title}
                  {/* MG_HEADKEEPS: занятие записал не сам человек — глава семьи
                      или тренер. */}
                  <AddedByMark name={r.added_by_name} withName className="ml-1 align-middle" />
                </div>
                <div className="text-xs text-gray-500">
                  {duration(r.duration_min)}
                  {r.calories !== null && (
                    <>
                      {' · '}
                      {/* «≈» говорит, что это наша оценка по справочному MET и
                          весу, а не показание прибора. */}
                      {r.calories_estimated ? '≈' : ''}{r.calories} ккал
                    </>
                  )}
                </div>
              </div>
              <button type="button" disabled={busy} onClick={() => remove(r)}
                      className="text-gray-400 hover:text-red-600 text-sm shrink-0" title="Убрать">
                🗑
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select value={activityId} onChange={(e) => setActivityId(e.target.value)} className={field}>
          <option value="">Выберите занятие…</option>
          {groups.map((g) => (
            <optgroup key={g.label} label={g.label}>
              {g.items.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </optgroup>
          ))}
          {/* Чего нет в справочнике, человек впишет своим названием: полный
              компендиум — восемьсот позиций вроде «игра на тубе стоя», и в
              списке выбора они утопили бы ходьбу и бег. */}
          <option value="own">Своё название…</option>
        </select>
        {own && (
          <input value={customName} onChange={(e) => setCustomName(e.target.value)}
                 placeholder="Сенокос" className={`${field} w-40`} />
        )}
        <input type="number" min="1" max="1440" value={minutes}
               onChange={(e) => setMinutes(e.target.value)}
               placeholder="мин" className={`${field} w-24`} />
        {/* Пустые калории — не пропуск, а нормальный путь: посчитаем по
            справочному MET и последнему весу. Введённое руками не перебиваем:
            человек мог смотреть на пульсометр. */}
        <input type="number" min="0" value={kcal} onChange={(e) => setKcal(e.target.value)}
               placeholder="ккал — посчитаем сами" className={`${field} w-48`} />
        <Button variant="ghost" disabled={busy || !canSave} onClick={save}>Записать</Button>
      </div>

      {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
    </Card>
  );
};
