// MG_ALLERGEN14_V_web = 1
// Редактор аллергенов профиля: фиксированный список 14 (ТР ТС 022/2011)
// чекбоксами + возможность добавить свой (внесписочный) аллерген текстом.
import React, { useMemo, useState } from 'react';
import { ALLERGENS, ALLERGEN_KEYS, allergenLabel } from '../../constants/allergens';
// Примечание: намеренно без Set/Map-итераций (CRA target ES5).

interface Props {
  /** Текущий список: ключи из 14 + произвольные строки (кастомные). */
  value: string[];
  /** Вызывается с новым списком; родитель сохраняет на бэкенд. */
  onChange: (next: string[]) => void;
}

export const AllergenEditor: React.FC<Props> = ({ value, onChange }) => {
  const [custom, setCustom] = useState('');

  // Кастомные (внесписочные) значения — всё, что не входит в 14 ключей.
  const customValues = useMemo(
    () => value.filter((v) => !ALLERGEN_KEYS.includes(v)),
    [value],
  );

  const toggle = (key: string) => {
    if (value.includes(key)) {
      onChange(value.filter((v) => v !== key));
    } else {
      onChange([...value, key]);
    }
  };

  const addCustom = () => {
    const t = custom.trim();
    if (!t) return;
    // не дублируем и не пересекаем со стандартным списком по названию
    const exists = value.some((v) => v.toLowerCase() === t.toLowerCase());
    const isStd = ALLERGENS.some((a) => a.label.toLowerCase() === t.toLowerCase());
    if (!exists && !isStd) onChange([...value, t]);
    setCustom('');
  };

  const removeCustom = (v: string) => onChange(value.filter((x) => x !== v));

  // Группируем 14 по group для аккуратных секций.
  const groups = useMemo(() => {
    const byGroup: Record<string, typeof ALLERGENS> = {};
    const order: string[] = [];
    ALLERGENS.forEach((a) => {
      if (!byGroup[a.group]) {
        byGroup[a.group] = [];
        order.push(a.group);
      }
      byGroup[a.group].push(a);
    });
    return order.map((g) => ({ group: g, items: byGroup[g] }));
  }, []);

  return (
    <div>
      {/* Фиксированный список 14 — чекбоксами по группам */}
      <div className="space-y-3">
        {groups.map((g) => (
          <div key={g.group}>
            <div className="text-xs font-semibold text-gray-500 mb-1">{g.group}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {g.items.map((a) => {
                const checked = value.includes(a.key);
                return (
                  <button
                    key={a.key}
                    type="button"
                    onClick={() => toggle(a.key)}
                    title={a.full}
                    className={
                      'flex items-center gap-2 px-3 py-2 rounded-xl border text-left text-sm transition ' +
                      (checked
                        ? 'border-tomato bg-tomato/10 text-chocolate'
                        : 'border-border bg-surface hover:border-tomato/40 text-gray-700')
                    }
                  >
                    <span
                      className={
                        'flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border text-xs ' +
                        (checked ? 'bg-tomato border-tomato text-white' : 'border-gray-300 text-transparent')
                      }
                    >
                      ✓
                    </span>
                    <span className="flex-1">{a.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Кастомные (внесписочные) аллергены */}
      <div className="mt-4 pt-4 border-t border-border">
        <div className="text-xs font-semibold text-gray-500 mb-2">Свой аллерген (вне списка)</div>
        {customValues.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {customValues.map((v) => (
              <span
                key={v}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-avocado/10 text-avocado text-sm border border-avocado/20"
              >
                {allergenLabel(v)}
                <button
                  type="button"
                  onClick={() => removeCustom(v)}
                  aria-label={`Убрать ${v}`}
                  className="text-avocado/70 hover:text-avocado font-bold leading-none"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addCustom();
              }
            }}
            placeholder="Напр. кориандр"
            className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-avocado/40 focus:border-avocado"
          />
          <button
            type="button"
            onClick={addCustom}
            disabled={!custom.trim()}
            className="px-4 py-2 rounded-xl bg-avocado text-white text-sm font-semibold disabled:opacity-40"
          >
            Добавить
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Внесписочные аллергены исключаются по совпадению в названиях ингредиентов.
        </p>
      </div>
    </div>
  );
};
