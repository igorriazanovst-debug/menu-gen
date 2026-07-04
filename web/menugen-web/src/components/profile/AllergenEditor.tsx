// MG_ALLERGEN_V_web = 1
// Редактор аллергенов профиля: чипы выбранных + поиск по каталогу продуктов
// (/fridge/products/search/) + ручной ввод произвольного аллергена.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fridgeApi } from '../../api/fridge';
import type { Product } from '../../types';

interface Props {
  /** Текущий список аллергенов (нижний регистр не гарантируется). */
  value: string[];
  /** Вызывается с новым списком; родитель сохраняет на бэкенд. */
  onChange: (next: string[]) => void;
  disabled?: boolean;
}

/** Есть ли уже такой аллерген (без учёта регистра/пробелов). */
function has(list: string[], name: string): boolean {
  const n = name.trim().toLowerCase();
  return list.some((a) => a.trim().toLowerCase() === n);
}

export const AllergenEditor: React.FC<Props> = ({ value, onChange, disabled }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Закрывать выпадашку по клику вне.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const runSearch = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const t = q.trim();
    if (t.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const list = await fridgeApi.searchProducts(t);
        setResults(list);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
  }, []);

  const onQuery = (q: string) => {
    setQuery(q);
    setOpen(true);
    runSearch(q);
  };

  const add = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    if (!has(value, trimmed)) {
      onChange([...value, trimmed]);
    }
    setQuery('');
    setResults([]);
    setOpen(false);
  };

  const remove = (name: string) => {
    onChange(value.filter((a) => a !== name));
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (query.trim()) add(query);
    }
  };

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
              {!disabled && (
                <button
                  type="button"
                  onClick={() => remove(a)}
                  aria-label={`Убрать ${a}`}
                  className="text-tomato/70 hover:text-tomato font-bold leading-none"
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 mb-3">Аллергены не выбраны.</p>
      )}

      {!disabled && (
        <div className="relative" ref={boxRef}>
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            onFocus={() => query.trim() && setOpen(true)}
            onKeyDown={onKeyDown}
            placeholder="Поиск продукта или свой аллерген…"
            className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
          />

          {open && (loading || results.length > 0 || canAddCustom) && (
            <div className="absolute z-10 mt-1 w-full max-h-60 overflow-auto rounded-xl border border-gray-200 bg-white shadow-lg">
              {loading && (
                <div className="px-3 py-2 text-sm text-gray-400">Поиск…</div>
              )}

              {!loading &&
                results.map((p) => {
                  const already = has(value, p.name);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      disabled={already}
                      onClick={() => add(p.name)}
                      className={
                        'flex w-full items-center gap-2 px-3 py-2 text-left text-sm ' +
                        (already
                          ? 'text-gray-300 cursor-default'
                          : 'text-gray-700 hover:bg-tomato/5')
                      }
                    >
                      <span className="truncate flex-1">{p.name}</span>
                      {already && <span className="text-xs">добавлен</span>}
                    </button>
                  );
                })}

              {!loading && canAddCustom && (
                <button
                  type="button"
                  onClick={() => add(query)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-avocado hover:bg-avocado/5 border-t border-gray-100"
                >
                  + Добавить «{query.trim()}»
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
