// MG_BODYSIZE: обхваты тела — ввод, история и контур.
//
// Рядом с весом, а не в профиле, и по той же причине, по которой вес когда-то
// уехал из профиля в дневник: профиль хранит текущее состояние, а вопрос
// «что происходит» требует прошлых точек. С обхватами это заметнее, чем с
// весом: вес на диете неделями стоит, а талия в это время уходит — и человек,
// глядя на одно число, решает, что старается зря.
//
// Пустые поля не отправляются: кто-то меряет только талию, и заставлять его
// выдумывать шею неправильно. Отправленное пустым (стёрли значение) уходит как
// null — это способ убрать один ошибочный обхват; кнопка «убрать» стирает
// строку за день целиком.
//
// MG_DAYFIX: дата — та, что выбрана вверху страницы, одна на весь дневник.
// Прошлые замеры в списке кликабельны: клик переключает день всей страницы, и
// дальше замер правится или удаляется как сегодняшний. Пустые поля за день
// значат «не мерили» — впишите, и замер появится.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { AddedByMark } from '../../components/diary/AddedByMark';
import { BodyOutline } from './BodyOutline';
import { useShowChart } from '../../utils/showChart';
import { diaryApi, MEASUREMENT_FIELDS, type DiaryMeasurement, type MeasurementField } from '../../api/diary';
import { apiErrorMessage } from '../../utils/apiError';
import { useAppSelector } from '../../hooks/useAppDispatch';

type Draft = Record<MeasurementField, string>;

const emptyDraft = (): Draft =>
  MEASUREMENT_FIELDS.reduce((acc, f) => ({ ...acc, [f.key]: '' }), {} as Draft);

const draftFrom = (row: DiaryMeasurement | null): Draft => {
  const d = emptyDraft();
  if (!row) return d;
  for (const { key } of MEASUREMENT_FIELDS) d[key] = row[key] ?? '';
  return d;
};

interface Props {
  date: string;
  memberId?: number;
  /** Переключить день всей страницы — по клику на прошлый замер. */
  onPickDate?: (date: string) => void;
}

export const MeasurementsCard: React.FC<Props> = ({ date, memberId, onPickDate }) => {
  const [rows, setRows] = useState<DiaryMeasurement[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [showChart, setShowChart] = useShowChart('body');
  // Силуэт берётся из своего профиля; у чужого дневника пол нам недоступен, и
  // тогда рисуется нейтральный контур — это лучше, чем угадывать.
  const gender = useAppSelector((s) => s.auth.user?.profile?.gender);

  const load = useCallback(async () => {
    try {
      const list = await diaryApi.getMeasurements(365, memberId);
      setRows(list);
      // Поля заполняем замером за выбранный день, если он есть: тогда правка
      // сегодняшнего замера — это правка, а не ввод заново.
      setDraft(draftFrom(list.find((r) => r.date === date) ?? null));
    } catch {
      // Пустая история — не ошибка: карточка просто без данных.
      setRows([]);
    }
  }, [date, memberId]);

  useEffect(() => {
    load();
  }, [load]);

  const latest = rows.length ? rows[rows.length - 1] : null;
  const previous = rows.length > 1 ? rows[rows.length - 2] : null;
  // Замер за выбранный день: от него зависит, «Записать» это или «Изменить».
  const forDate = rows.find((r) => r.date === date) ?? null;
  const recent = rows.slice(-5).reverse();

  const filled = useMemo(
    () => MEASUREMENT_FIELDS.some(({ key }) => draft[key].trim() !== ''),
    [draft],
  );

  const remove = async () => {
    if (!window.confirm(`Убрать замер обхватов за ${date}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await diaryApi.deleteMeasurement(date, memberId);
      setDraft(emptyDraft());
      await load();
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось убрать замер.');
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, string | null> = { date };
      for (const { key } of MEASUREMENT_FIELDS) {
        const raw = draft[key].trim().replace(',', '.');
        payload[key] = raw === '' ? null : raw;
      }
      await diaryApi.setMeasurement(payload as never, memberId);
      await load();
      setOpen(false);
    } catch (err) {
      setError(apiErrorMessage(err) ?? 'Не удалось сохранить замеры.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-chocolate">
          📏 Обхваты
          <AddedByMark name={latest?.added_by_name} withName className="ml-2" />
        </div>
        <div className="flex items-center gap-3">
          {/* Всегда, а не только при готовых замерах: иначе о диаграмме не
              узнать, пока не запишешь первый обхват, — а записывать незачем,
              пока не знаешь, что она есть. Пустая диаграмма это объясняет. */}
          <button type="button" onClick={() => setShowChart(!showChart)}
                  className="text-xs text-avocado hover:underline">
            {showChart ? 'скрыть диаграмму' : 'показать диаграмму'}
          </button>
          {/* Подпись зависит от того, есть ли замер за выбранный день: «записать»
              на пустом дне и «изменить» на занятом — иначе человек не поймёт,
              заведёт он новый замер или перепишет прежний. */}
          <button type="button" onClick={() => setOpen((v) => !v)}
                  className="text-xs text-avocado hover:underline">
            {open ? 'свернуть' : forDate ? 'изменить' : 'записать'}
          </button>
        </div>
      </div>

      {latest && !open && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-chocolate">
          {MEASUREMENT_FIELDS.map(({ key, label }) =>
            latest[key] ? (
              <span key={key}>
                <span className="text-gray-400">{label}</span> {latest[key]} см
              </span>
            ) : null,
          )}
          <span className="text-xs text-gray-400 self-center">за {latest.date}</span>
        </div>
      )}

      {open && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {MEASUREMENT_FIELDS.map(({ key, label }) => (
              <label key={key} className="block">
                <span className="block text-xs text-gray-500 mb-1">{label}, см</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={draft[key]}
                  onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                  className="w-full rounded-xl border border-gray-300 px-3 py-1.5 text-sm focus:ring-2 focus:ring-tomato/40 focus:border-tomato outline-none"
                />
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={save} disabled={busy || !filled}>
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
            <p className="text-xs text-gray-400">
              За этот день замера нет — впишите хотя бы один обхват.
            </p>
          )}
          {recent.length > 0 && (
            <div className="pt-2 border-t space-y-1">
              <p className="text-xs text-gray-400">Прошлые замеры — нажмите, чтобы открыть день:</p>
              {recent.map((r) => (
                <button key={r.date} type="button"
                        onClick={() => onPickDate?.(r.date)}
                        className={`w-full flex justify-between text-sm text-chocolate rounded-lg px-1 -mx-1 ${
                          onPickDate ? 'hover:bg-rice cursor-pointer' : 'cursor-default'
                        } ${r.date === date ? 'bg-rice' : ''}`}>
                  <span className="text-gray-400">
                    {r.date}
                    <AddedByMark name={r.added_by_name} className="ml-1" />
                  </span>
                  <span className="truncate ml-2">
                    {MEASUREMENT_FIELDS.filter(({ key }) => r[key]).map(({ key, label }) =>
                      `${label} ${r[key]}`).join(' · ') || '—'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <p className="text-red-600 text-sm mt-2">{error}</p>}

      {showChart && <BodyOutline latest={latest} previous={previous} gender={gender} />}
    </Card>
  );
};
