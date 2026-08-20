// MG_TRAINER: изменение веса между первым и последним замером.
//
// Отдельным модулем без зависимостей: считать динамику нужно и в дневнике, и в
// тестах, а тянуть ради этого api-клиент (и вместе с ним axios) незачем.

export interface WeightPointLike {
  date: string;
  weight_kg: string | number;
}

/** Разница «последний минус первый», кг. null — если точек меньше двух. */
export const weightDelta = (points: WeightPointLike[]): number | null => {
  if (points.length < 2) return null;
  const first = Number(points[0].weight_kg);
  const last = Number(points[points.length - 1].weight_kg);
  if (Number.isNaN(first) || Number.isNaN(last)) return null;
  return Math.round((last - first) * 10) / 10;
};
