// MG_ALLERGEN_V_web = 4
// Редактор аллергенов профиля: выбор ИЗ СПИСКА продуктов, схлопнутого по
// базовому продукту («Сыр гауда», «Сыр тёртый» → «Сыр»), поиск по каталогу
// (серверный) и ввод произвольного аллергена.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { fridgeApi, type AllergenOption } from '../../api/fridge';

interface Props {
  /** Текущий список аллергенов. */
  value: string[];
  /** Вызывается с новым списком; родитель сохраняет на бэкенд. */
  onChange: (next: string[]) => void;
}

/** Есть ли уже такой аллерген (без учёта регистра/пробелов). */
function has(list: string[], name: string): boolean {
  const n = name.trim().toLowerCase();
  return list.some((a) => a.trim().toLowerCase() === n);
}

interface Group {
  cat: string;
  items: AllergenOption[];
}

/** Группировка по названию категории (для заголовков). */
function group(list: AllergenOption[]): Group[] {
  const byCat: Record<string, AllergenOption[]> = {};
  const order: string[] = [];
  list.forEach((p) => {
    const cat = p.category_name || 'Прочее';
    if (!byCat[cat]) {
      byCat[cat] = [];
      order.push(cat);
    }
    byCat[cat].push(p);
  });
  return order.map((cat) => ({ cat, items: byCat[cat] }));
}

export const AllergenEditor: React.FC<Props> = ({ value, onChange }) => {
  const [browse, setBrowse] = useState<AllergenOption[]>([]); // весь каталог (обзор)
  const [results, setResults] = useState<AllergenOption[]>([]); // серверный поиск
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [loadErr, setLoadErr] = useState(false);
  const [query, setQuery] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Каталог для обзора грузится один раз.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fridgeApi.catalog();
        if (!cancelled) setBrowse(list);
      } catch {
        if (!cancelled) setLoadErr(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const onQuery = (q: string) => {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const t = q.trim();
    if (t.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const list = await fridgeApi.catalog(t);
        setResults(list);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  };

  const toggle = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    if (has(value, trimmed)) {
      onChange(value.filter((a) => a.trim().toLowerCase() !== trimmed.toLowerCase()));
    } else {
      onChange([...value, trimmed]);
    }
  };

  const remove = (name: string) => onChange(value.filter((a) => a !== name));

  const searchMode = query.trim().length >= 2;
  const groups = useMemo(() => group(searchMode ? results : browse), [searchMode, results, browse]);
  const canAddCustom = query.trim().length > 0 && !has(value, query);

  return (
    <div>
      {/* Чипы выбранных аллергенов */}
      {value.length > 0 ? (
        <div className="flex flex-wrap gap-2 mb-3">
          {value.map((a) => (
            <span
              key={a}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-tomato/10 text-tomato text-sm border border-tomato/20"
            >
              {a}
              <button
                type="button"
                onClick={() => remove(a)}
                aria-label={`Убрать ${a}`}
                className="text-tomato/70 hover:text-tomato font-bold leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 mb-3">Аллергены не выбраны.</p>
      )}

      {/* Поиск по каталогу */}
      <input
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        placeholder="Поиск по списку или свой аллерген…"
        className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
      />

      {/* Добавить произвольный аллерген (когда нет в списке) */}
      {canAddCustom && (
        <button
          type="button"
          onClick={() => {
            toggle(query);
            onQuery('');
          }}
          className="mt-2 w-full text-left px-3 py-2 rounded-xl text-sm text-avocado bg-avocado/5 hover:bg-avocado/10 border border-avocado/20"
        >
          + Добавить свой аллерген «{query.trim()}»
        </button>
      )}

      {/* Список аллергенов (схлопнутый каталог) */}
      <div className="mt-2 max-h-72 overflow-auto rounded-xl border border-gray-200 divide-y divide-gray-100">
        {loading && <div className="px-3 py-3 text-sm text-gray-400">Загрузка каталога…</div>}
        {!loading && loadErr && (
          <div className="px-3 py-3 text-sm text-red-500">
            Не удалось загрузить каталог. Можно ввести аллерген вручную выше.
          </div>
        )}
        {!loading && !loadErr && searching && (
          <div className="px-3 py-3 text-sm text-gray-400">Поиск…</div>
        )}
        {!loading && !loadErr && !searching && groups.length === 0 && (
          <div className="px-3 py-3 text-sm text-gray-400">Ничего не найдено.</div>
        )}
        {!loading &&
          !loadErr &&
          !searching &&
          groups.map((g) => (
            <div key={g.cat}>
              <div className="sticky top-0 bg-gray-50 px-3 py-1 text-xs font-semibold text-gray-500">
                {g.cat}
              </div>
              {g.items.map((p) => {
                const checked = has(value, p.name);
                const hint = p.examples.filter((e) => e.toLowerCase() !== p.name.toLowerCase());
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => toggle(p.name)}
                    className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-tomato/5"
                  >
                    <span
                      className={
                        'mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border text-xs ' +
                        (checked
                          ? 'bg-tomato border-tomato text-white'
                          : 'border-gray-300 text-transparent')
                      }
                    >
                      ✓
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block truncate">{p.name}</span>
                      {hint.length > 0 && (
                        <span className="block truncate text-xs text-gray-400">
                          {hint.join(', ')}
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
      </div>
    </div>
  );
};
