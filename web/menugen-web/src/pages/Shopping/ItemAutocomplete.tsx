// MG_RUBRIC004/008 — rubricator autocomplete + qty/unit/price staging.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { shoppingApi, AddItemPayload } from '../../api/shopping';
import { fridgeApi } from '../../api/fridge';
import { Button } from '../../components/ui/Button';
import type {
  ShoppingV2RubricResult,
  ShoppingV2RubricSuggestion,
} from '../../types';

const UNITS = ['шт', 'г', 'кг', 'мл', 'л', 'упак', 'банка', 'пучок', 'головка', 'бутылка', 'тюбик'];

interface Props {
  onAdd: (payload: AddItemPayload) => Promise<void>;
  currency?: string;
}

// Staging model: a chosen/new item awaiting qty/unit/price before being added.
interface Staged {
  name: string;
  unit: string;
  product_id: number | null;
  category_slug: string;
  category_name: string;
  price: string; // string for input; '' = none
}

export const ItemAutocomplete: React.FC<Props> = ({ onAdd, currency = 'RUB' }) => {
  const [text, setText] = useState('');
  const [results, setResults] = useState<ShoppingV2RubricResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  // new-product classify flow
  const [suggestion, setSuggestion] = useState<ShoppingV2RubricSuggestion | null>(null);
  const [categories, setCategories] = useState<{ slug: string; name: string }[]>([]);
  const [chosenSlug, setChosenSlug] = useState('');

  // staging row (qty/unit/price)
  const [staged, setStaged] = useState<Staged | null>(null);
  const [qty, setQty] = useState('1');

  const boxRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const knownCats = useRef<Map<string, string>>(new Map());

  // full category list for override + new-product flow
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await fridgeApi.categories();
        if (cancelled) return;
        (data ?? []).forEach((c) => knownCats.current.set(c.slug, c.name_ru));
        setCategories(
          Array.from(knownCats.current.entries())
            .map(([slug, name]) => ({ slug, name }))
            .sort((a, b) => a.name.localeCompare(b.name, 'ru')),
        );
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await shoppingApi.rubricSearch(q.trim(), false);
      data.results.forEach((r) => knownCats.current.set(r.category_slug, r.category_name));
      setResults(data.results);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (staged) return; // don't search while staging
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => runSearch(text), 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [text, runSearch, staged]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const resetAll = () => {
    setText('');
    setResults([]);
    setOpen(false);
    setSuggestion(null);
    setChosenSlug('');
    setStaged(null);
    setQty('1');
  };

  // Pick an existing rubric item → stage it (prefill unit; price prefill via product happens server-side too).
  const pick = (r: ShoppingV2RubricResult) => {
    setOpen(false);
    setStaged({
      name: r.name,
      unit: UNITS.includes(r.unit) ? r.unit : r.unit || UNITS[0],
      product_id: r.product_id,
      category_slug: r.category_slug,
      category_name: r.category_name,
      price: '',
    });
    setQty('1');
  };

  // No match → classify → stage as new with chosen category.
  const startNew = async () => {
    const q = text.trim();
    if (!q) return;
    setBusy(true);
    try {
      const { data } = await shoppingApi.rubricSearch(q, true);
      if (data.results.length > 0) {
        setResults(data.results);
        setOpen(true);
        return;
      }
      const sug = data.suggestion;
      setSuggestion(sug);
      if (sug) knownCats.current.set(sug.category_slug, sug.category_name);
      const slug = sug?.category_slug ?? 'other';
      setChosenSlug(slug);
      setStaged({
        name: q,
        unit: UNITS[0],
        product_id: null,
        category_slug: slug,
        category_name: sug?.category_name ?? 'Прочее',
        price: '',
      });
      setQty('1');
      setOpen(false);
    } finally {
      setBusy(false);
    }
  };

  const confirmAdd = async () => {
    if (!staged) return;
    setBusy(true);
    try {
      const q = parseFloat(qty.replace(',', '.'));
      const priceNum = staged.price.trim() ? parseFloat(staged.price.replace(',', '.')) : null;
      await onAdd({
        name: staged.name,
        quantity: Number.isFinite(q) ? q : 1,
        unit: staged.unit,
        product_id: staged.product_id,
        category_slug: suggestion ? chosenSlug : staged.category_slug,
        price_per_unit: priceNum,
      });
      resetAll();
    } finally {
      setBusy(false);
    }
  };

  // ── staging row UI ──
  if (staged) {
    const q = parseFloat(qty.replace(',', '.')) || 0;
    const p = staged.price.trim() ? parseFloat(staged.price.replace(',', '.')) || 0 : null;
    const lineTotal = p != null ? (q * p).toFixed(2) : null;
    return (
      <div className="p-3 border border-tomato/30 bg-tomato/5 rounded-xl space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-medium text-sm">{staged.name}</span>
          <button onClick={resetAll} className="text-gray-400 hover:text-red-500 text-sm">✕</button>
        </div>

        {/* category: editable only for new products */}
        {suggestion ? (
          <div>
            <span className="text-xs text-gray-500">Категория (ИИ): </span>
            <select
              value={chosenSlug}
              onChange={(e) => setChosenSlug(e.target.value)}
              className="rounded-lg border border-gray-300 px-2 py-1 text-sm"
            >
              {categories.map((c) => (
                <option key={c.slug} value={c.slug}>{c.name}</option>
              ))}
            </select>
          </div>
        ) : (
          <div className="text-xs text-gray-500">Категория: {staged.category_name}</div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputMode="decimal"
            className="w-16 rounded-lg border border-gray-300 px-2 py-1 text-sm"
            placeholder="Кол-во"
          />
          <select
            value={staged.unit}
            onChange={(e) => setStaged({ ...staged, unit: e.target.value })}
            className="rounded-lg border border-gray-300 px-2 py-1 text-sm"
          >
            {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
          <span className="text-gray-400 text-sm">×</span>
          <input
            value={staged.price}
            onChange={(e) => setStaged({ ...staged, price: e.target.value })}
            inputMode="decimal"
            className="w-20 rounded-lg border border-gray-300 px-2 py-1 text-sm"
            placeholder="Цена"
          />
          <span className="text-xs text-gray-400">{currency}/ед</span>
          {lineTotal != null && (
            <span className="text-sm text-chocolate font-medium ml-auto">
              = {lineTotal} {currency}
            </span>
          )}
        </div>

        <Button onClick={confirmAdd} disabled={busy} className="w-full">
          Добавить в список
        </Button>
      </div>
    );
  }

  // ── search UI ──
  return (
    <div ref={boxRef} className="relative">
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Добавить позицию…"
          className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
        />
        <Button
          onClick={() => (results.length > 0 ? pick(results[0]) : startNew())}
          disabled={busy || !text.trim()}
        >
          +
        </Button>
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg max-h-72 overflow-auto">
          {results.map((r) => (
            <li
              key={r.product_id}
              onClick={() => pick(r)}
              className="px-3 py-2 text-sm hover:bg-tomato/5 cursor-pointer flex items-center justify-between"
            >
              <span>
                {r.name}
                {r.unit ? <span className="text-gray-400"> · {r.unit}</span> : null}
              </span>
              <span className="text-xs text-gray-400">{r.category_name}</span>
            </li>
          ))}
          <li
            onClick={startNew}
            className="px-3 py-2 text-sm text-tomato hover:bg-tomato/5 cursor-pointer border-t border-gray-100"
          >
            + Добавить «{text.trim()}» как новый товар
          </li>
        </ul>
      )}

      {open && results.length === 0 && text.trim() && !loading && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg p-2">
          <button
            onClick={startNew}
            className="w-full text-left px-2 py-1.5 text-sm text-tomato hover:bg-tomato/5 rounded-lg"
          >
            + Добавить «{text.trim()}» как новый товар
          </button>
        </div>
      )}
    </div>
  );
};
