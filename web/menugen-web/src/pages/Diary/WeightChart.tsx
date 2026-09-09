// MG_BODYCHART: график веса по точкам замеров.
//
// Рисуется своим SVG, без библиотеки графиков: точек здесь десятки, линия одна,
// а любая библиотека — это сотни килобайт в бандл ради того, что укладывается в
// сорок строк.
//
// Что важно в самом графике. Ось Y не начинается с нуля: вес человека меняется
// на проценты, и на шкале от нуля линия выглядела бы прямой. Вместо этого берём
// диапазон замеров и добавляем поля сверху и снизу — тогда видно то, ради чего
// график и смотрят: идёт вниз или стоит.
//
// Даты по оси X расставлены по номеру точки, а не по календарю: замеры делают
// неравномерно, и пропуск в две недели не должен растягивать половину картинки.
// Для «вес за период» этого достаточно, а для календарной точности есть список
// замеров под графиком.
import React from 'react';
import type { DiaryWeightPoint } from '../../api/diary';

const W = 320;
const H = 96;
const PAD_X = 6;
const PAD_Y = 10;

const fmtDate = (iso: string) => {
  const [, m, d] = iso.split('-');
  return `${d}.${m}`;
};

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
  // Плоский участок (все замеры равны) развалил бы деление на ноль; полкило
  // поля — ровно столько, чтобы линия шла посередине, а не по краю.
  const span = max - min || 1;
  const lo = min - span * 0.15;
  const hi = max + span * 0.15;

  const x = (i: number) => PAD_X + (i * (W - PAD_X * 2)) / (values.length - 1);
  const y = (kg: number) => PAD_Y + ((hi - kg) * (H - PAD_Y * 2)) / (hi - lo);

  const line = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v.kg).toFixed(1)}`).join(' ');
  const area = `${line} L${x(values.length - 1).toFixed(1)},${H} L${x(0).toFixed(1)},${H} Z`;
  const last = values[values.length - 1];
  const first = values[0];

  return (
    <div className="pt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24" role="img"
           aria-label={`График веса: с ${first.kg} кг до ${last.kg} кг`}>
        <path d={area} fill="#E5484D" opacity="0.08" />
        <path d={line} fill="none" stroke="#E5484D" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
        {values.map((v, i) => (
          <circle key={v.date} cx={x(i)} cy={y(v.kg)} r={i === values.length - 1 ? 3.5 : 2}
                  fill="#E5484D" />
        ))}
      </svg>
      <div className="flex justify-between text-[11px] text-gray-400 px-1">
        <span>{fmtDate(first.date)} · {first.kg} кг</span>
        <span>{fmtDate(last.date)} · {last.kg} кг</span>
      </div>
    </div>
  );
};
