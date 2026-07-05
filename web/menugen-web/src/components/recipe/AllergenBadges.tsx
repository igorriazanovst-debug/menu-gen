// MG_ALLERGEN14: бейджи аллергенов рецепта (ключи → метки ТР ТС 022).
import React from 'react';
import { allergenLabel } from '../../constants/allergens';

interface Props {
  allergens?: string[] | null;
  className?: string;
}

export const AllergenBadges: React.FC<Props> = ({ allergens, className }) => {
  if (!allergens || allergens.length === 0) return null;
  return (
    <div className={'flex flex-wrap items-center gap-1.5 ' + (className ?? '')}>
      <span className="text-xs text-gray-500">⚠️ Аллергены:</span>
      {allergens.map((k) => (
        <span
          key={k}
          className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-xs"
        >
          {allergenLabel(k)}
        </span>
      ))}
    </div>
  );
};
