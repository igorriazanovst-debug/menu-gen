// MG_BODYSIZE: контур тела с обхватами.
//
// Зачем картинка, а не пять строк с числами. Числа отвечают на вопрос «сколько»,
// но не на вопрос «где»: «под грудью 78» человек читает секунду, а на контуре
// сразу видно, какая линия куда идёт, и не путается грудь с подгрудной. Второе:
// рядом с каждой линией стоит изменение с прошлого замера, и вся картина —
// «талия ушла, бёдра стоят» — читается одним взглядом.
//
// Контур мужской или женский — по полу из профиля. Разница только в силуэте:
// линии замеров и подписи одни и те же. Пол не указан — рисуем нейтральный.
//
// Рисуется вручную, без библиотеки: это одна статичная фигура, а не график.
import React from 'react';
import { MEASUREMENT_FIELDS, type DiaryMeasurement, type MeasurementField } from '../../api/diary';

type Silhouette = 'male' | 'female' | 'neutral';

// Высота каждой линии замера на картинке. Значения подобраны по силуэту: шея
// под головой, грудь по подмышкам, талия в самом узком месте, бёдра ниже.
const LINE_Y: Record<MeasurementField, number> = {
  neck_cm: 40,
  chest_cm: 66,
  under_bust_cm: 84,
  waist_cm: 104,
  hips_cm: 128,
};

// Половина ширины линии на каждом уровне — чтобы линия ложилась по контуру, а
// не торчала за него. Женский силуэт шире в бёдрах и уже в талии; мужской
// наоборот. Это рисунок, а не антропометрия: он подписан числами, и точность
// пропорций ничего не добавляет.
const HALF: Record<Silhouette, Record<MeasurementField, number>> = {
  male: { neck_cm: 9, chest_cm: 30, under_bust_cm: 27, waist_cm: 24, hips_cm: 26 },
  female: { neck_cm: 8, chest_cm: 27, under_bust_cm: 22, waist_cm: 19, hips_cm: 29 },
  neutral: { neck_cm: 8.5, chest_cm: 28, under_bust_cm: 24, waist_cm: 21, hips_cm: 27 },
};

const BODY: Record<Silhouette, string> = {
  // Плечи — талия — бёдра — ноги. Одна замкнутая фигура на каждый силуэт.
  male:
    'M100 22c-7 0-12 5-12 11 0 4 2 7 4 9-12 3-25 8-28 14-3 7-4 20-4 28 0 6 1 10 2 13'
    + ' 2 5 4 9 5 20 1 10 2 22 3 30 1 9 2 22 3 30h11c0-10 1-22 2-31 1-8 2-16 2-22'
    + ' 0-6 1-10 2-13 1 3 2 7 2 13 0 6 1 14 2 22 1 9 2 21 2 31h11c1-8 2-21 3-30'
    + ' 1-8 2-20 3-30 1-11 3-15 5-20 1-3 2-7 2-13 0-8-1-21-4-28-3-6-16-11-28-14'
    + ' 2-2 4-5 4-9 0-6-5-11-12-11z',
  female:
    'M100 22c-6 0-11 5-11 11 0 4 2 7 4 9-11 3-22 8-25 14-3 7-4 19-4 27 0 6 1 10 2 13'
    + ' 1 4 2 7 2 11-1 5-2 10-2 15 0 7 3 12 6 15 1 9 2 20 3 28 1 9 2 20 2 29h10'
    + ' c0-10 1-21 2-30 1-8 2-15 2-21 0-5 1-9 2-12 1 3 2 7 2 12 0 6 1 13 2 21'
    + ' 1 9 2 20 2 30h10c0-9 1-20 2-29 1-8 2-19 3-28 3-3 6-8 6-15 0-5-1-10-2-15'
    + ' 0-4 1-7 2-11 1-3 2-7 2-13 0-8-1-20-4-27-3-6-14-11-25-14 2-2 4-5 4-9 0-6-5-11-11-11z',
  neutral:
    'M100 22c-7 0-12 5-12 11 0 4 2 7 4 9-11 3-23 8-26 14-3 7-4 20-4 28 0 6 1 10 2 13'
    + ' 2 5 4 9 5 20 1 10 2 21 3 29 1 9 2 21 3 30h10c0-10 1-22 2-31 1-8 2-16 2-22'
    + ' 0-6 1-10 2-13 1 3 2 7 2 13 0 6 1 14 2 22 1 9 2 21 2 31h10c1-9 2-21 3-30'
    + ' 1-8 2-19 3-29 1-11 3-15 5-20 1-3 2-7 2-13 0-8-1-21-4-28-3-6-15-11-26-14'
    + ' 2-2 4-5 4-9 0-6-5-11-12-11z',
};

const num = (v: string | null | undefined): number | null => {
  if (v == null) return null;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
};

interface Props {
  latest: DiaryMeasurement | null;
  /** Предыдущий замер — для стрелок «было/стало». */
  previous?: DiaryMeasurement | null;
  gender?: string | null;
}

export const BodyOutline: React.FC<Props> = ({ latest, previous, gender }) => {
  const silhouette: Silhouette = gender === 'male' ? 'male' : gender === 'female' ? 'female' : 'neutral';
  const half = HALF[silhouette];

  if (!latest) {
    return (
      <p className="text-xs text-gray-400 py-3">
        Замеров пока нет — впишите хотя бы один обхват, и здесь появится контур.
      </p>
    );
  }

  const fmt = (iso: string) => {
    const [, m, d] = iso.split('-');
    return `${d}.${m}`;
  };

  return (
    <div className="pt-2">
      {/* MG_CHARTAXES: без подписи картинка молчит о главном — за какое число
          показаны обхваты и с чем сравнены числа слева. */}
      <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-gray-500 mb-1">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 border-t border-dashed" style={{ borderColor: '#E5484D' }} />
          Обхваты, см · замер {fmt(latest.date)}
        </span>
        {previous && (
          <span className="text-gray-400">слева — изменение с {fmt(previous.date)}</span>
        )}
      </div>
      <div className="flex justify-center">
      <svg viewBox="0 0 200 190" className="w-full max-w-[280px]" role="img"
           aria-label="Контур тела с обхватами">
        <path d={BODY[silhouette]} fill="#F5E7DC" stroke="#D9C3B0" strokeWidth="1.5" />
        {MEASUREMENT_FIELDS.map(({ key, label }) => {
          const value = num(latest[key]);
          if (value == null) return null;
          const y = LINE_Y[key];
          const dx = half[key];
          const was = previous ? num(previous[key]) : null;
          const delta = was == null ? null : Math.round((value - was) * 10) / 10;
          return (
            <g key={key}>
              <line x1={100 - dx} y1={y} x2={100 + dx} y2={y}
                    stroke="#E5484D" strokeWidth="1.5" strokeDasharray="3 2" />
              <text x={100 + dx + 6} y={y + 3.5} fontSize="9" fill="#5B4636">
                {label} {value}
                <tspan fill="#8A7568"> см</tspan>
              </text>
              {delta !== null && delta !== 0 && (
                // Знак важнее цвета: «−2 см» на талии хорошо, а на груди у
                // набирающего массу — плохо, и решать это не диаграмме.
                <text x={100 - dx - 6} y={y + 3.5} fontSize="9" textAnchor="end" fill="#8A7568">
                  {delta > 0 ? '+' : '−'}{Math.abs(delta)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      </div>
    </div>
  );
};
