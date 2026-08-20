// MG_CONSTRUCTOR: ручной конструктор меню (специалисты/стафф).
// Список созданных меню + встроенный редактор одной структуры
// (меню → дни → приёмы → блюда).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { constructorApi, type ConstructedMenuPayload } from '../../api/constructor';
import { recipesApi } from '../../api/recipes';
import { fridgeApi } from '../../api/fridge';
import type {
  ConstructedMeal,
  ConstructedMealItem,
  ConstructedMenuListItem,
  ConstructorClient,
  Product,
  Recipe,
} from '../../types';

// ── редакторная модель (локальная, до сохранения) ────────────────────────────
// Позиция приёма — либо рецепт, либо продукт (с порцией в граммах). MG_PRODDISH.
interface DraftItem {
  kind: 'recipe' | 'product';
  ref_id: number;            // recipe_id либо product_id
  title: string;
  image_url?: string | null;
  grams: number;             // только для продукта
  quantity: number;
}
interface DraftMeal {
  key: string; // стабильный ключ для React
  day_index: number;
  name: string;
  target_calories: string;
  target_protein: string;
  target_fat: string;
  target_carbs: string;
  items: DraftItem[];
}
interface DraftMenu {
  id: number | null;
  name: string;
  client_family: number | null;
  days: number;
  status: 'draft' | 'published';
  meals: DraftMeal[];
}

let _kseq = 0;
const nextKey = () => `m${Date.now()}_${_kseq++}`;

const emptyMeal = (day: number, name = 'Приём'): DraftMeal => ({
  key: nextKey(),
  day_index: day,
  name,
  target_calories: '',
  target_protein: '',
  target_fat: '',
  target_carbs: '',
  items: [],
});

const numOrNull = (s: string): number | null => {
  const v = s.trim();
  if (!v) return null;
  const n = Number(v.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
};

// DRF-пагинация может завернуть список в {results:[…]} — приводим к массиву.
const asArray = <T,>(d: unknown): T[] =>
  Array.isArray(d) ? (d as T[]) : ((d as { results?: T[] } | null)?.results ?? []);

const blankDraft = (): DraftMenu => ({
  id: null,
  name: '',
  client_family: null,
  days: 1,
  status: 'draft',
  meals: [emptyMeal(0, 'Завтрак')],
});

// сервер → редакторная модель
const fromServerMeals = (meals: ConstructedMeal[]): DraftMeal[] =>
  meals
    .slice()
    .sort((a, b) => a.day_index - b.day_index || a.order - b.order)
    .map((m) => ({
      key: nextKey(),
      day_index: m.day_index,
      name: m.name,
      target_calories: m.target_calories != null ? String(m.target_calories) : '',
      target_protein: m.target_protein != null ? String(m.target_protein) : '',
      target_fat: m.target_fat != null ? String(m.target_fat) : '',
      target_carbs: m.target_carbs != null ? String(m.target_carbs) : '',
      items: (m.items || []).map((it: ConstructedMealItem): DraftItem =>
        it.product || it.product_id
          ? {
              kind: 'product',
              ref_id: it.product?.id ?? it.product_id ?? 0,
              title: it.product?.name ?? '—',
              image_url: it.product?.image_url,
              grams: Number(it.grams) || 100,
              quantity: Number(it.quantity) || 1,
            }
          : {
              kind: 'recipe',
              ref_id: it.recipe?.id ?? it.recipe_id ?? 0,
              title: it.recipe?.title ?? '—',
              image_url: it.recipe?.image_url,
              grams: 0,
              quantity: Number(it.quantity) || 1,
            },
      ),
    }));

// редакторная модель → payload
const toPayload = (d: DraftMenu): ConstructedMenuPayload => {
  const byDayCounter: Record<number, number> = {};
  return {
    name: d.name.trim(),
    client_family: d.client_family,
    days: d.days,
    status: d.status,
    meals: d.meals
      .filter((m) => m.day_index < d.days)
      .map((m) => {
        const order = (byDayCounter[m.day_index] = (byDayCounter[m.day_index] ?? -1) + 1);
        return {
          day_index: m.day_index,
          order,
          name: m.name.trim() || 'Приём',
          target_calories: numOrNull(m.target_calories),
          target_protein: numOrNull(m.target_protein),
          target_fat: numOrNull(m.target_fat),
          target_carbs: numOrNull(m.target_carbs),
          items: m.items
            .filter((it) => it.ref_id)
            .map((it) =>
              it.kind === 'product'
                ? { product_id: it.ref_id, grams: it.grams || 100, quantity: it.quantity || 1 }
                : { recipe_id: it.ref_id, quantity: it.quantity || 1 },
            ),
        };
      }),
  };
};

// ── поиск блюда: рецепт ИЛИ продукт (порция в граммах) ────────────────────────
const DishSearch: React.FC<{ onAdd: (it: DraftItem) => void }> = ({ onAdd }) => {
  const [mode, setMode] = useState<'recipe' | 'product'>('recipe');
  const [q, setQ] = useState('');
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newKcal, setNewKcal] = useState('');

  useEffect(() => {
    setRecipes([]);
    setProducts([]);
    if (q.trim().length < 2) return;
    setLoading(true);
    const term = q.trim();
    const t = setTimeout(() => {
      if (mode === 'recipe') {
        recipesApi
          .list({ search: term, page_size: 10 })
          .then((r) => setRecipes(r.data.results ?? []))
          .catch(() => setRecipes([]))
          .finally(() => setLoading(false));
      } else {
        fridgeApi
          .searchProducts(term)
          .then((list) => setProducts(list))
          .catch(() => setProducts([]))
          .finally(() => setLoading(false));
      }
    }, 350);
    return () => clearTimeout(t);
  }, [q, mode]);

  const reset = () => {
    setQ('');
    setRecipes([]);
    setProducts([]);
    setCreating(false);
    setNewKcal('');
  };

  const addRecipe = (r: Recipe) => {
    onAdd({ kind: 'recipe', ref_id: r.id, title: r.title, image_url: r.image_url, grams: 0, quantity: 1 });
    reset();
  };
  const addProduct = (p: Product) => {
    onAdd({ kind: 'product', ref_id: p.id, title: p.name, image_url: p.image_url, grams: 100, quantity: 1 });
    reset();
  };

  const createProduct = async () => {
    const name = q.trim();
    if (!name) return;
    const kcal = newKcal.trim() ? Number(newKcal.replace(',', '.')) : null;
    try {
      const { data } = await fridgeApi.createProduct({
        name,
        calories_per_100g: kcal,
        nutrition: kcal != null ? { calories: kcal } : undefined,
      });
      addProduct(data);
    } catch {
      /* тихо: пусть пользователь повторит */
    }
  };

  const tabCls = (active: boolean) =>
    [
      'px-3 py-1 text-xs rounded-lg border',
      active ? 'bg-avocado text-white border-avocado' : 'text-gray-500 border-border hover:bg-rice',
    ].join(' ');

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <button type="button" onClick={() => setMode('recipe')} className={tabCls(mode === 'recipe')}>
          Рецепт
        </button>
        <button type="button" onClick={() => setMode('product')} className={tabCls(mode === 'product')}>
          Продукт
        </button>
      </div>
      <input
        type="text"
        placeholder={mode === 'recipe' ? 'Поиск рецепта…' : 'Поиск продукта (напр. огурец)…'}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setCreating(false);
        }}
        className="w-full border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-avocado"
      />
      {loading && <p className="text-xs text-gray-400 mt-1">Поиск…</p>}

      {mode === 'recipe' && recipes.length > 0 && (
        <ul className="mt-1 border border-border rounded-lg divide-y max-h-48 overflow-y-auto bg-surface">
          {recipes.map((r) => (
            <li
              key={r.id}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-rice flex items-center gap-2"
              onClick={() => addRecipe(r)}
            >
              {r.image_url && <img src={r.image_url} alt="" className="w-8 h-8 rounded object-cover" />}
              <span className="text-chocolate">{r.title}</span>
            </li>
          ))}
        </ul>
      )}

      {mode === 'product' && (
        <>
          {products.length > 0 && (
            <ul className="mt-1 border border-border rounded-lg divide-y max-h-48 overflow-y-auto bg-surface">
              {products.map((p) => (
                <li
                  key={p.id}
                  className="px-3 py-2 text-sm cursor-pointer hover:bg-rice flex items-center gap-2"
                  onClick={() => addProduct(p)}
                >
                  {p.image_url && <img src={p.image_url} alt="" className="w-8 h-8 rounded object-cover" />}
                  <span className="text-chocolate flex-1">{p.name}</span>
                  {p.is_own && <span className="text-[10px] text-avocado">наш</span>}
                  {p.calories_per_100g != null && (
                    <span className="text-[10px] text-gray-400">{p.calories_per_100g} ккал/100г</span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {/* если не нашли — предложить создать пользовательский продукт */}
          {!loading && q.trim().length >= 2 && products.length === 0 && (
            <div className="mt-1 text-xs">
              {!creating ? (
                <button
                  type="button"
                  onClick={() => setCreating(true)}
                  className="text-avocado hover:underline"
                >
                  + Создать продукт «{q.trim()}»
                </button>
              ) : (
                <div className="flex items-center gap-2 border border-border rounded-lg p-2">
                  <span className="text-chocolate">{q.trim()}</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    placeholder="ккал/100г"
                    value={newKcal}
                    onChange={(e) => setNewKcal(e.target.value)}
                    className="w-24 border border-border rounded px-2 py-1"
                  />
                  <button
                    type="button"
                    onClick={createProduct}
                    className="px-2 py-1 rounded bg-tomato text-white"
                  >
                    Добавить
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ── редактор одного приёма ───────────────────────────────────────────────────
const MealCard: React.FC<{
  meal: DraftMeal;
  onChange: (m: DraftMeal) => void;
  onRemove: () => void;
}> = ({ meal, onChange, onRemove }) => {
  const set = (patch: Partial<DraftMeal>) => onChange({ ...meal, ...patch });

  return (
    <div className="border border-border rounded-xl p-3 bg-surface">
      <div className="flex items-center gap-2 mb-2">
        <input
          type="text"
          value={meal.name}
          onChange={(e) => set({ name: e.target.value })}
          placeholder="Наименование приёма"
          className="flex-1 border border-border rounded-lg px-3 py-1.5 text-sm font-medium focus:outline-none focus:border-avocado"
        />
        <button
          onClick={onRemove}
          className="text-xs text-red-500 border border-red-200 px-2 py-1 rounded-lg hover:bg-red-50"
          title="Удалить приём"
        >
          ✕
        </button>
      </div>

      {/* Цели (КБЖУ) */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        {([
          ['target_calories', 'ккал'],
          ['target_protein', 'Б, г'],
          ['target_fat', 'Ж, г'],
          ['target_carbs', 'У, г'],
        ] as const).map(([field, label]) => (
          <label key={field} className="text-xs text-gray-400">
            {label}
            <input
              type="number"
              inputMode="decimal"
              value={meal[field]}
              onChange={(e) => set({ [field]: e.target.value } as Partial<DraftMeal>)}
              className="w-full border border-border rounded-lg px-2 py-1 text-sm text-chocolate focus:outline-none focus:border-avocado"
            />
          </label>
        ))}
      </div>

      {/* Блюда */}
      {meal.items.length > 0 && (
        <ul className="space-y-1 mb-2">
          {meal.items.map((it, idx) => (
            <li
              key={`${it.kind}_${it.ref_id}_${idx}`}
              className="flex items-center gap-2 border border-border rounded-lg px-2 py-1"
            >
              {it.image_url && (
                <img src={it.image_url} alt="" className="w-8 h-8 rounded object-cover" />
              )}
              <span className="flex-1 text-sm text-chocolate">
                {it.title}
                {it.kind === 'product' && <span className="ml-1 text-[10px] text-gray-400">продукт</span>}
              </span>
              {it.kind === 'product' && (
                <label className="flex items-center gap-1 text-[11px] text-gray-400">
                  <input
                    type="number"
                    min={1}
                    value={it.grams}
                    onChange={(e) => {
                      const items = meal.items.slice();
                      items[idx] = { ...it, grams: Math.max(1, Number(e.target.value) || 1) };
                      set({ items });
                    }}
                    className="w-16 border border-border rounded px-1 py-0.5 text-sm text-center"
                    title="Порция, г"
                  />
                  г
                </label>
              )}
              <input
                type="number"
                min={1}
                value={it.quantity}
                onChange={(e) => {
                  const items = meal.items.slice();
                  items[idx] = { ...it, quantity: Math.max(1, Number(e.target.value) || 1) };
                  set({ items });
                }}
                className="w-14 border border-border rounded px-1 py-0.5 text-sm text-center"
                title="Порций"
              />
              <button
                onClick={() => set({ items: meal.items.filter((_, i) => i !== idx) })}
                className="text-xs text-red-500 px-1"
                title="Убрать блюдо"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <DishSearch onAdd={(it) => set({ items: [...meal.items, it] })} />
    </div>
  );
};

// ── редактор всего меню ──────────────────────────────────────────────────────
const MenuEditor: React.FC<{
  draft: DraftMenu;
  clients: ConstructorClient[];
  onClose: () => void;
  onSaved: () => void;
}> = ({ draft: initial, clients, onClose, onSaved }) => {
  const [draft, setDraft] = useState<DraftMenu>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Partial<DraftMenu>) => setDraft((d) => ({ ...d, ...patch }));

  const setMeal = (key: string, m: DraftMeal) =>
    setDraft((d) => ({ ...d, meals: d.meals.map((x) => (x.key === key ? m : x)) }));

  const removeMeal = (key: string) =>
    setDraft((d) => ({ ...d, meals: d.meals.filter((x) => x.key !== key) }));

  const addMeal = (day: number) =>
    setDraft((d) => ({ ...d, meals: [...d.meals, emptyMeal(day)] }));

  const changeDays = (n: number) => {
    const days = Math.max(1, Math.min(31, n || 1));
    // приёмы вне диапазона просто скрываем (не теряем — вернутся, если увеличить)
    setDraft((d) => ({ ...d, days }));
  };

  const save = async (status: 'draft' | 'published') => {
    if (!draft.name.trim()) {
      setError('Укажите имя меню');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = toPayload({ ...draft, status });
    try {
      if (draft.id) await constructorApi.update(draft.id, payload);
      else await constructorApi.create(payload);
      onSaved();
    } catch (e: unknown) {
      const err = e as { response?: { data?: unknown } };
      setError(
        typeof err.response?.data === 'string'
          ? err.response.data
          : 'Не удалось сохранить меню'
      );
    } finally {
      setSaving(false);
    }
  };

  const dayList = Array.from({ length: draft.days }, (_, i) => i);

  return (
    <div className="max-w-3xl mx-auto">
      <button onClick={onClose} className="text-sm text-avocado hover:underline mb-3 inline-block">
        ← К списку
      </button>

      {/* Шапка меню */}
      <div className="bg-surface rounded-2xl shadow p-4 mb-5 space-y-3">
        <label className="block text-sm">
          <span className="text-gray-400 text-xs">Имя меню</span>
          <input
            type="text"
            value={draft.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="Например: Меню на неделю для Ивановых"
            className="w-full border border-border rounded-lg px-3 py-2 text-sm mt-0.5 focus:outline-none focus:border-avocado"
          />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-gray-400 text-xs">Клиент</span>
            <select
              value={draft.client_family ?? ''}
              onChange={(e) => set({ client_family: e.target.value ? Number(e.target.value) : null })}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm mt-0.5 focus:outline-none focus:border-avocado bg-white"
            >
              <option value="">— без клиента —</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-gray-400 text-xs">Количество дней</span>
            <input
              type="number"
              min={1}
              max={31}
              value={draft.days}
              onChange={(e) => changeDays(Number(e.target.value))}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm mt-0.5 focus:outline-none focus:border-avocado"
            />
          </label>
        </div>
      </div>

      {/* Дни */}
      <div className="space-y-5">
        {dayList.map((day) => {
          const dayMeals = draft.meals.filter((m) => m.day_index === day);
          return (
            <div key={day} className="bg-rice/40 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-chocolate">День {day + 1}</h2>
                <button
                  onClick={() => addMeal(day)}
                  className="text-sm text-avocado border border-avocado px-3 py-1 rounded-lg hover:bg-avocado hover:text-white transition"
                >
                  + Приём
                </button>
              </div>
              <div className="space-y-3">
                {dayMeals.map((m) => (
                  <MealCard
                    key={m.key}
                    meal={m}
                    onChange={(nm) => setMeal(m.key, nm)}
                    onRemove={() => removeMeal(m.key)}
                  />
                ))}
                {dayMeals.length === 0 && (
                  <p className="text-xs text-gray-400">Нет приёмов. Нажмите «+ Приём».</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {error && <p className="text-sm text-red-500 mt-4">{error}</p>}

      {/* Действия */}
      <div className="sticky bottom-0 mt-6 -mx-4 px-4 py-3 bg-bg/90 backdrop-blur border-t border-border flex items-center gap-3">
        <button
          onClick={() => save('draft')}
          disabled={saving}
          className="px-4 py-2 rounded-lg border border-border text-sm text-chocolate hover:bg-rice disabled:opacity-50"
        >
          {saving ? 'Сохранение…' : 'Сохранить черновик'}
        </button>
        <button
          onClick={() => save('published')}
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-tomato text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          Опубликовать
        </button>
      </div>
    </div>
  );
};

// ── страница ─────────────────────────────────────────────────────────────────
export const ConstructorPage: React.FC = () => {
  const [list, setList] = useState<ConstructedMenuListItem[]>([]);
  const [clients, setClients] = useState<ConstructorClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<DraftMenu | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    Promise.all([constructorApi.list(), constructorApi.clients()])
      .then(([l, c]) => {
        // Список может прийти как массивом, так и в пагинированной обёртке
        // ({results:[…]}) — DRF-пагинация включена глобально.
        setList(asArray<ConstructedMenuListItem>(l.data));
        setClients(asArray<ConstructorClient>(c.data));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const openNew = () => setEditing(blankDraft());

  const openExisting = async (id: number) => {
    const r = await constructorApi.get(id);
    const m = r.data;
    setEditing({
      id: m.id,
      name: m.name,
      client_family: m.client_family ?? null,
      days: m.days,
      status: m.status,
      meals: fromServerMeals(m.meals),
    });
  };

  const remove = async (id: number) => {
    if (!window.confirm('Удалить меню?')) return;
    await constructorApi.remove(id);
    reload();
  };

  const clientName = useMemo(() => {
    const map = new Map(clients.map((c) => [c.id, c.name]));
    return (id?: number | null) => (id ? map.get(id) ?? '' : '');
  }, [clients]);

  if (editing) {
    return (
      <div className="px-4 py-6">
        <MenuEditor
          draft={editing}
          clients={clients}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-chocolate">Конструктор меню</h1>
          <p className="text-sm text-gray-400">Ручное создание меню для клиента.</p>
        </div>
        <button
          onClick={openNew}
          className="px-4 py-2 rounded-lg bg-tomato text-white text-sm font-semibold hover:opacity-90"
        >
          + Новое меню
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tomato" />
        </div>
      ) : list.length === 0 ? (
        <p className="text-center text-gray-400 mt-16">
          Пока нет созданных меню. Нажмите «+ Новое меню».
        </p>
      ) : (
        <ul className="space-y-2">
          {list.map((m) => (
            <li
              key={m.id}
              className="bg-surface rounded-2xl shadow p-4 flex items-center justify-between"
            >
              <button className="text-left flex-1" onClick={() => openExisting(m.id)}>
                <p className="font-semibold text-chocolate">{m.name || 'Без названия'}</p>
                <p className="text-xs text-gray-400">
                  {m.days} дн. · {m.meals_count} приёмов
                  {m.client_family_name || clientName(m.client_family)
                    ? ` · ${m.client_family_name || clientName(m.client_family)}`
                    : ''}
                  {' · '}
                  {m.status === 'published' ? 'опубликовано' : 'черновик'}
                </p>
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openExisting(m.id)}
                  className="text-sm text-avocado hover:underline"
                >
                  Открыть
                </button>
                <button
                  onClick={() => remove(m.id)}
                  className="text-sm text-red-500 hover:underline"
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default ConstructorPage;
