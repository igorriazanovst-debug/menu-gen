// MG_BODYCHART: график веса по точкам замеров.
//
// Рисуется своим SVG, без библиотеки графиков: линия одна, точек десятки, а
// любая библиотека — это сотни килобайт в бандл ради того, что укладывается в
// сотню строк.
//
// MG_CHARTAXES: у первой версии не было ни осей, ни чисел — только линия. По
// такой картинке видно «вниз или вверх», но не видно ни насколько, ни когда, и
// пользы от неё чуть. Теперь есть три вещи, без которых график не график:
//
//   * шкала слева — три подписи в килограммах (низ, середина, верх);
//   * шкала снизу — даты первого, среднего и последнего замера;
//   * значения — у первой и последней точки прямо на графике, у остальных во
//     всплывающей подсказке; плюс легенда сверху с разницей за период.
//
// Ось Y не начинается с нуля: вес меняется на проценты, и на шкале от нуля
// линия была бы прямой при любой динамике. Поэтому берём диапазон замеров и
// добавляем поля — а чтобы это не вводило в заблуждение, подписи на шкале
// показывают реальные килограммы.
//
// По оси X точки расставлены равномерно, по номеру, а не по календарю: замеры
// делают неравномерно, и перерыв в две недели не должен съедать половину
// картинки. Подписи дат под шкалой честно показывают, какому дню какая точка.
import React from 'react';
import type { DiaryWeightPoint } from '../../api/diary';

const W = 360;
const H = 150;
const PAD_L = 36; // место под подписи килограммов
const PAD_R = 10;
const PAD_T = 14;
const PAD_B = 24; // место под даты

const fmtDate = (iso: string) => {
  const [, m, d] = iso.split('-');
  return `${d}.${m}`;
};

const fmtKg = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

export const WeightChart: React.FC<{ points: DiaryWeightPoint[] }> = ({ points }) => {
  const values = points
    .map((p) => ({ date: p.date, kg: parseFloat(p.weight_kg) }))
    .filter((p) => Number.isFinite(p.kg));

  if (values.length < 2) {
    return (
      <p className="text-xs text-gray-400 py-3">
        Для графика нужно хотя бы два замера — сделайте ещё один в другой день.
      </p>
    );
  }

  const min = Math.min(...values.map((v) => v.kg));
  const max = Math.max(...values.map((v) => v.kg));
  // Плоский участок (все замеры равны) развалил бы деление на ноль; поле в 15%
  // держит линию посередине, а не по краю.
  const span = max - min || 1;
  const lo = min - span * 0.15;
  const hi = max + span * 0.15;
  const mid = (lo + hi) / 2;

  const x = (i: number) => PAD_L + (i * (W - PAD_L - PAD_R)) / (values.length - 1);
  const y = (kg: number) => PAD_T + ((hi - kg) * (H - PAD_T - PAD_B)) / (hi - lo);

  const line = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v.kg).toFixed(1)}`).join(' ');
  const area = `${line} L${x(values.length - 1).toFixed(1)},${H - PAD_B} L${x(0).toFixed(1)},${H - PAD_B} Z`;

  const first = values[0];
  const last = values[values.length - 1];
  const delta = Math.round((last.kg - first.kg) * 10) / 10;

  // Даты под шкалой: первая, последняя и середина — больше на такой ширине не
  // помещается, а частокол подписей читается хуже, чем их отсутствие.
  const tickIdx = values.length >= 4 ? [0, Math.floor((values.length - 1) / 2), values.length - 1] : [0, values.length - 1];

  return (
    <div className="pt-2">
      {/* Легенда: что за линия, за какой период и куда сдвинулся вес. */}
      <div className="flex items-center gap-2 text-[11px] text-gray-500 mb-1">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: '#E5484D' }} />
          Вес, кг
        </span>
        <span className="text-gray-400">
          {fmtDate(first.date)} — {fmtDate(last.date)}
        </span>
        {delta !== 0 && (
          <span className={delta < 0 ? 'text-avocado' : 'text-gray-500'}>
            {delta > 0 ? '+' : '−'}{Math.abs(delta)} кг за период
          </span>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 190 }} role="img"
           aria-label={`График веса с ${first.date} (${first.kg} кг) по ${last.date} (${last.kg} кг)`}>
        {/* Сетка и подписи шкалы: низ, середина, верх диапазона. */}
        {[hi, mid, lo].map((kg) => (
          <g key={kg}>
            <line x1={PAD_L} y1={y(kg)} x2={W - PAD_R} y2={y(kg)}
                  stroke="#E7DDD3" strokeWidth="1" strokeDasharray="2 3" />
            <text x={PAD_L - 6} y={y(kg) + 3} fontSize="9" textAnchor="end" fill="#8A7568">
              {fmtKg(kg)}
            </text>
          </g>
        ))}

        {/* Сами оси — сплошными, чтобы отделить поле графика от подписей. */}
        <line x1={PAD_L} y1={PAD_T - 4} x2={PAD_L} y2={H - PAD_B} stroke="#D9C3B0" strokeWidth="1" />
        <line x1={PAD_L} y1={H - PAD_B} x2={W - PAD_R} y2={H - PAD_B} stroke="#D9C3B0" strokeWidth="1" />

        <path d={area} fill="#E5484D" opacity="0.08" />
        <path d={line} fill="none" stroke="#E5484D" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />

        {values.map((v, i) => (
          <circle key={v.date} cx={x(i)} cy={y(v.kg)} r={i === values.length - 1 ? 3.5 : 2.5}
                  fill="#E5484D">
            {/* Значение каждой точки — в подсказке: подписать все числа на
                графике нельзя, они сольются, а узнать их нужно. */}
            <title>{`${fmtDate(v.date)}: ${fmtKg(v.kg)} кг`}</title>
          </circle>
        ))}

        {/* Числа у крайних точек: с них начинают читать график, и ради них не
            нужно ни во что наводить курсор. */}
        <text x={x(0) + 4} y={y(first.kg) - 6} fontSize="9" fill="#5B4636">{fmtKg(first.kg)}</text>
        <text x={x(values.length - 1) - 4} y={y(last.kg) - 6} fontSize="9" textAnchor="end"
              fill="#5B4636" fontWeight="600">
          {fmtKg(last.kg)}
        </text>

        {/* Даты под осью. */}
        {tickIdx.map((i, n) => (
          <text key={values[i].date} x={x(i)} y={H - PAD_B + 13} fontSize="9" fill="#8A7568"
                textAnchor={n === 0 ? 'start' : n === tickIdx.length - 1 ? 'end' : 'middle'}>
            {fmtDate(values[i].date)}
          </text>
        ))}
      </svg>
    </div>
  );
};
