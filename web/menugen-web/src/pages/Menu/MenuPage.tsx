import React, { useState, useEffect, useCallback, useRef } from 'react';
import { menuApi } from '../../api/menu';
import type { DeletedMenu, SwapResult } from '../../api/menu';
import { recipesApi } from '../../api/recipes';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import type { Menu, MenuItem, MealType, Recipe } from '../../types';
import { MEAL_LABELS } from '../../types';

const MEAL_ICONS: Record<string, string> = {
  breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎',
};

const MEAL_ORDER_3: MealType[] = ['breakfast', 'lunch', 'dinner'];
const MEAL_ORDER_5: MealType[] = ['breakfast', 'snack', 'lunch', 'snack', 'dinner'];
// Для 5 приёмов снэк встречается дважды — будем показывать первый и второй
const MEAL_SLOTS_5 = ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner'];
const MEAL_SLOT_LABEL: Record<string, string> = {
  breakfast: 'Завтрак', snack1: 'Перекус 1', lunch: 'Обед',
  snack2: 'Перекус 2', dinner: 'Ужин',
};

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('ru', { day: 'numeric', month: 'short' });
}
function addDays(dateStr: string, n: number) {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
}
function today() { return new Date().toISOString().split('T')[0]; }

// ── MealDetailModal ───────────────────────────────────────────────────────────

interface MealDetailModalProps {
  items: MenuItem[];          // основное блюдо + салаты приёма пищи
  mealLabel: string;
  dayLabel: string;
  onClose: () => void;
}

const MealDetailModal: React.FC<MealDetailModalProps> = ({ items, mealLabel, dayLabel, onClose }) => {
  const printRef = useRef<HTMLDivElement>(null);

  const handlePrintRecipes = () => {
    const win = window.open('', '_blank');
    if (!win) return;
    const html = items.map(item => {
      const r = item.recipe;
      const ings = (r.ingredients || []).map((i: any) => `<li>${i.name}${i.quantity ? ': ' + i.quantity : ''}${i.unit ? ' ' + i.unit : ''}</li>`).join('');
      const steps = (r.steps || []).map((s: any, idx: number) => `<li>${s.text || s}</li>`).join('');
      const cal = r.nutrition?.calories ? `${r.nutrition.calories.value} ${r.nutrition.calories.unit}` : '';
      return `
        <h2>${r.title}</h2>
        ${cal ? `<p>Калории: ${cal}</p>` : ''}
        ${r.cook_time ? `<p>Время: ${r.cook_time}</p>` : ''}
        <h3>Ингредиенты</h3><ul>${ings}</ul>
        <h3>Приготовление</h3><ol>${steps}</ol>
        <hr/>
      `;
    }).join('');
    win.document.write(`<html><head><title>Рецепты — ${mealLabel} ${dayLabel}</title>
      <style>body{font-family:Arial,sans-serif;padding:20px;max-width:700px;margin:0 auto}h2{color:#333}hr{margin:20px 0}</style>
      </head><body><h1>${mealLabel} · ${dayLabel}</h1>${html}</body></html>`);
    win.document.close();
    win.print();
  };

  const handlePrintProducts = () => {
    const win = window.open('', '_blank');
    if (!win) return;
    const all: string[] = [];
    items.forEach(item => {
      (item.recipe.ingredients || []).forEach((i: any) => {
        all.push(`<li>${i.name}${i.quantity ? ' — ' + i.quantity : ''}${i.unit ? ' ' + i.unit : ''}</li>`);
      });
    });
    win.document.write(`<html><head><title>Список продуктов</title>
      <style>body{font-family:Arial,sans-serif;padding:20px;max-width:500px;margin:0 auto}</style>
      </head><body><h1>Список продуктов — ${mealLabel} · ${dayLabel}</h1><ul>${all.join('')}</ul></body></html>`);
    win.document.close();
    win.print();
  };

  const handlePrintShopping = () => {
    const win = window.open('', '_blank');
    if (!win) return;
    // Агрегируем по названию продукта
    const map: Record<string, { qty: number; unit: string }> = {};
    items.forEach(item => {
      (item.recipe.ingredients || []).forEach((i: any) => {
        const key = i.name.toLowerCase();
        if (!map[key]) map[key] = { qty: 0, unit: i.unit || '' };
        const q = parseFloat(i.quantity) || 0;
        map[key].qty += q;
      });
    });
    const rows = Object.entries(map).map(([name, v]) =>
      `<tr><td>${name}</td><td>${v.qty > 0 ? v.qty : ''}</td><td>${v.unit}</td><td><input type="checkbox"/></td></tr>`
    ).join('');
    win.document.write(`<html><head><title>Список покупок</title>
      <style>body{font-family:Arial,sans-serif;padding:20px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px}th{background:#f5f5f5}</style>
      </head><body><h1>Список покупок — ${mealLabel} · ${dayLabel}</h1>
      <table><thead><tr><th>Продукт</th><th>Кол-во</th><th>Ед.</th><th>✓</th></tr></thead><tbody>${rows}</tbody></table>
      </body></html>`);
    win.document.close();
    win.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-chocolate">{mealLabel}</h2>
              <p className="text-sm text-gray-500">{dayLabel}</p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          <div className="space-y-4 mb-5">
            {items.map(item => (
              <div key={item.id} className="border border-gray-100 rounded-xl p-3">
                {item.recipe.image_url && (
                  <img src={item.recipe.image_url} alt={item.recipe.title}
                    className="w-full h-32 object-cover rounded-lg mb-2" />
                )}
                <h3 className="font-semibold text-chocolate text-sm">{item.recipe.title}</h3>
                {item.recipe.nutrition?.calories && (
                  <p className="text-xs text-gray-400 mt-1">
                    🔥 {item.recipe.nutrition.calories.value} {item.recipe.nutrition.calories.unit}
                    {item.recipe.cook_time && ` · ⏱ ${item.recipe.cook_time}`}
                  </p>
                )}
                {item.recipe.ingredients?.length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-tomato cursor-pointer">Ингредиенты ({item.recipe.ingredients.length})</summary>
                    <ul className="mt-1 text-xs text-gray-600 list-disc list-inside space-y-0.5">
                      {item.recipe.ingredients.slice(0, 10).map((ing: any, i: number) => (
                        <li key={i}>{ing.name}{ing.quantity ? ` — ${ing.quantity}${ing.unit ? ' ' + ing.unit : ''}` : ''}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
            <button onClick={handlePrintRecipes}
              className="flex-1 text-xs bg-tomato text-white rounded-xl py-2 px-3 hover:bg-tomato/90 transition">
              🖨 Рецепты
            </button>
            <button onClick={handlePrintProducts}
              className="flex-1 text-xs bg-avocado text-white rounded-xl py-2 px-3 hover:bg-avocado/90 transition">
              📋 Список продуктов
            </button>
            <button onClick={handlePrintShopping}
              className="flex-1 text-xs bg-chocolate text-white rounded-xl py-2 px-3 hover:bg-chocolate/90 transition">
              🛒 Список покупок
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── MenuPage ──────────────────────────────────────────────────────────────────

export const MenuPage: React.FC = () => {
  const user = useAppSelector((s) => s.auth.user);

  const [menus, setMenus]         = useState<Menu[]>([]);
  const [loading, setLoading]     = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showForm, setShowForm]   = useState(false);

  // form
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate]     = useState(() => addDays(today(), 6));
  const [days, setDays]           = useState(7);
  const [country, setCountry]     = useState('');
  const [countries, setCountries] = useState<string[]>([]);
  const [maxCookTime, setMaxCookTime] = useState<number | ''>('');
  const [calorieMin, setCalorieMin]   = useState<number | ''>('');
  const [calorieMax, setCalorieMax]   = useState<number | ''>('');
  const [mealPlanType, setMealPlanType] = useState<'3' | '5'>('3');

  const [activeMenuId, setActiveMenuId]       = useState<number | null>(null);
  const [activeMenuDetail, setActiveMenuDetail] = useState<Menu | null>(null);
  const [detailLoading, setDetailLoading]     = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await menuApi.list();
      const d = data as any;
      let list: Menu[] = [];
      if (Array.isArray(d)) list = d;
      else if (Array.isArray(d?.results)) list = d.results;
      setMenus(list);
      if (list.length) setActiveMenuId(list[0].id);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    (recipesApi as any).countries?.()
      .then((r: any) => setCountries(r.data?.countries ?? []))
      .catch(() => {});
  }, [load]);

  useEffect(() => {
    if (!activeMenuId) { setActiveMenuDetail(null); return; }
    setDetailLoading(true);
    menuApi.get(activeMenuId)
      .then(({ data }) => setActiveMenuDetail(data as Menu))
      .catch(() => {})
      .finally(() => setDetailLoading(false));
  }, [activeMenuId]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const { data } = await menuApi.generate({
        period_days: days,
        start_date: startDate,
        country: country || undefined,
        max_cook_time: maxCookTime || undefined,
        calorie_min: calorieMin || undefined,
        calorie_max: calorieMax || undefined,
        meal_plan_type: mealPlanType,
      } as any);
      setMenus(prev => [data, ...prev]);
      setActiveMenuId(data.id);
      setShowForm(false);
    } finally { setGenerating(false); }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить меню?')) return;
    try {
      await menuApi.delete(id);
      const next = menus.filter(m => m.id !== id);
      setMenus(next);
      setActiveMenuId(next.length ? next[0].id : null);
    } catch { alert('Ошибка удаления'); }
  };

  if (loading) return <PageSpinner />;

  const activeMenu = activeMenuDetail;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Меню</h1>
        <Button onClick={() => setShowForm(!showForm)}>✨ Сгенерировать</Button>
      </div>

      {showForm && (
        <Card className="p-5">
          <h2 className="font-semibold mb-4">Новое меню</h2>
          <div className="space-y-4">
            {/* Режим питания */}
            <div>
              <label className="text-sm font-medium text-chocolate block mb-1">Режим питания</label>
              <div className="flex gap-3">
                {(['3', '5'] as const).map(v => (
                  <label key={v} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="mealPlan" value={v}
                      checked={mealPlanType === v}
                      onChange={() => setMealPlanType(v)}
                      className="accent-tomato" />
                    <span className="text-sm">
                      {v === '3' ? '3 приёма (завтрак / обед / ужин)' : '5 приёмов (+ 2 перекуса)'}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-chocolate">Начало</label>
                <input type="date" value={startDate}
                  onChange={e => { setStartDate(e.target.value); setEndDate(addDays(e.target.value, days - 1)); }}
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-sm font-medium text-chocolate">Кол-во дней: {days}</label>
                <input type="range" min={1} max={14} value={days}
                  onChange={e => { const n = Number(e.target.value); setDays(n); setEndDate(addDays(startDate, n - 1)); }}
                  className="w-full mt-2 accent-tomato" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-chocolate">Страна</label>
                {countries.length > 0 ? (
                  <select value={country} onChange={e => setCountry(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm">
                    <option value="">Любая</option>
                    {countries.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                ) : (
                  <input type="text" value={country} onChange={e => setCountry(e.target.value)}
                    placeholder="Например: Россия"
                    className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
                )}
              </div>
              <div>
                <label className="text-sm font-medium text-chocolate">Макс. время (мин)</label>
                <input type="number" value={maxCookTime} onChange={e => setMaxCookTime(e.target.value ? Number(e.target.value) : '')}
                  placeholder="Без ограничений"
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-chocolate">Калории от</label>
                <input type="number" value={calorieMin} onChange={e => setCalorieMin(e.target.value ? Number(e.target.value) : '')}
                  placeholder="—" className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-sm font-medium text-chocolate">Калории до</label>
                <input type="number" value={calorieMax} onChange={e => setCalorieMax(e.target.value ? Number(e.target.value) : '')}
                  placeholder="—" className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
            </div>

            <div className="flex gap-3">
              <Button onClick={handleGenerate} loading={generating}>Сгенерировать</Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>Отмена</Button>
            </div>
          </div>
        </Card>
      )}

      {menus.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {menus.map(m => (
            <button key={m.id} onClick={() => setActiveMenuId(m.id)}
              className={[
                'px-3 py-1.5 rounded-xl text-sm whitespace-nowrap border transition',
                m.id === activeMenuId
                  ? 'bg-tomato text-white border-tomato'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-tomato',
              ].join(' ')}>
              {formatDate(m.start_date)} — {formatDate(m.end_date)}
            </button>
          ))}
        </div>
      )}

      {!activeMenu && !detailLoading ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📋</div>
          <p className="text-lg font-medium">Меню пока нет</p>
          <p className="text-sm mt-1">Нажмите «Сгенерировать» чтобы составить меню</p>
        </div>
      ) : detailLoading ? (
        <div className="flex justify-center py-10">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tomato" />
        </div>
      ) : activeMenu ? (
        <MenuGrid
          menu={activeMenu}
          onRefresh={load}
          onDelete={() => handleDelete(activeMenu.id)}
        />
      ) : null}
    </div>
  );
};

// ── MenuGrid ──────────────────────────────────────────────────────────────────

interface MenuGridProps {
  menu: Menu;
  onRefresh: () => void;
  onDelete: () => void;
}

const MenuGrid: React.FC<MenuGridProps> = ({ menu, onRefresh, onDelete }) => {
  const [editMode, setEditMode]       = useState(false);
  const [warnings, setWarnings]       = useState<Record<number, SwapResult>>({});
  const [swapping, setSwapping]       = useState<number | null>(null);
  const [searchRecipe, setSearchRecipe] = useState('');
  const [swapTarget, setSwapTarget]   = useState<number | null>(null);
  const [recipeOptions, setRecipeOptions] = useState<{ id: number; title: string }[]>([]);
  const [mealModal, setMealModal]     = useState<{ items: MenuItem[]; label: string; dayLabel: string } | null>(null);

  // Определяем режим: 3 или 5 приёмов из данных меню
  const hasTwoSnacks = (() => {
    const snackDays: Record<number, number> = {};
    (menu.items || []).forEach(i => {
      if (i.meal_type === 'snack') snackDays[i.day_offset] = (snackDays[i.day_offset] || 0) + 1;
    });
    return Object.values(snackDays).some(c => c >= 2);
  })();
  const mealSlots = hasTwoSnacks ? MEAL_SLOTS_5 : ['breakfast', 'lunch', 'dinner'];

  useEffect(() => {
    if (searchRecipe.length < 2) { setRecipeOptions([]); return; }
    const t = setTimeout(() => {
      (recipesApi as any).list?.({ params: { search: searchRecipe, page_size: 10 } })
        .then((r: any) => setRecipeOptions(r.data?.results ?? []))
        .catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [searchRecipe]);

  const handleSwap = async (itemId: number, recipeId: number) => {
    setSwapping(itemId);
    try {
      const { data } = await menuApi.swapItem(menu.id, itemId, recipeId);
      setWarnings(prev => ({ ...prev, [itemId]: data }));
      setSwapTarget(null);
      setSearchRecipe('');
      onRefresh();
    } catch { alert('Ошибка замены блюда'); }
    finally { setSwapping(null); }
  };

  const openMealModal = (dayItems: MenuItem[], slot: string, dayLabel: string) => {
    const dbType = slot.replace(/\d$/, '') as MealType; // snack1/snack2 → snack
    const slotItems = slot === 'snack1'
      ? dayItems.filter(i => i.meal_type === 'snack').slice(0, Math.ceil(dayItems.filter(i => i.meal_type === 'snack').length / 2))
      : slot === 'snack2'
      ? dayItems.filter(i => i.meal_type === 'snack').slice(Math.ceil(dayItems.filter(i => i.meal_type === 'snack').length / 2))
      : dayItems.filter(i => i.meal_type === dbType);
    if (!slotItems.length) return;
    const label = MEAL_SLOT_LABEL[slot] || MEAL_LABELS[dbType as MealType] || slot;
    setMealModal({ items: slotItems, label, dayLabel });
  };

  const daysArr = Array.from({ length: menu.period_days }, (_, i) => i);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {formatDate(menu.start_date)} — {formatDate(menu.end_date)} · {menu.period_days} дн.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setEditMode(e => !e)}
            className={[
              'px-3 py-1.5 rounded-xl text-sm border transition',
              editMode
                ? 'bg-tomato text-white border-tomato'
                : 'bg-white text-gray-600 border-gray-200 hover:border-tomato',
            ].join(' ')}>
            {editMode ? '👁 Просмотр' : '✏️ Редактировать'}
          </button>
          <Button variant="ghost" onClick={onDelete} className="text-red-400 hover:text-red-600 text-sm">
            🗑 Удалить
          </Button>
        </div>
      </div>

      {daysArr.map(day => {
        const date = new Date(menu.start_date);
        date.setDate(date.getDate() + day);
        const dayLabel = date.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' });
        const dayItems = (menu.items ?? []).filter(i => i.day_offset === day);

        return (
          <Card key={day} className="p-4">
            <h3 className="font-semibold text-chocolate mb-3 capitalize">{dayLabel}</h3>
            <div className={`grid gap-2 ${mealSlots.length === 5 ? 'grid-cols-2 sm:grid-cols-5' : 'grid-cols-3'}`}>
              {mealSlots.map(slot => {
                const dbType = slot.replace(/\d$/, '') as MealType;
                const slotIndex = slot === 'snack2' ? 1 : 0;
                const slotItemsAll = dayItems.filter(i => i.meal_type === dbType);
                const snackItems = slot.startsWith('snack')
                  ? dayItems.filter(i => i.meal_type === 'snack')
                  : [];
                const halfLen = Math.ceil(snackItems.length / 2);
                const slotItems = slot === 'snack1'
                  ? snackItems.slice(0, halfLen)
                  : slot === 'snack2'
                  ? snackItems.slice(halfLen)
                  : slotItemsAll;
                const mainItem = slotItems[0];
                const hasSalad = slotItems.length > 1;
                const warn = mainItem ? warnings[mainItem.id] : undefined;
                const hasWarn = warn?.allergen_warning || warn?.calorie_warning;
                const label = MEAL_SLOT_LABEL[slot] || MEAL_LABELS[dbType] || slot;

                return (
                  <div key={slot}
                    className={[
                      'p-3 rounded-xl transition-all',
                      hasWarn ? 'border-2 border-red-400 bg-red-50' : 'bg-rice',
                      !editMode && slotItems.length > 0 ? 'cursor-pointer hover:shadow-md hover:scale-[1.02]' : '',
                    ].join(' ')}
                    onClick={() => !editMode && openMealModal(dayItems, slot, dayLabel)}>
                    <div className="flex items-center gap-1 mb-1">
                      <span>{MEAL_ICONS[dbType] ?? '🍽'}</span>
                      <span className="text-xs text-gray-500">{label}</span>
                    </div>
                    <p className="text-xs text-chocolate font-medium line-clamp-2 mb-1">
                      {mainItem?.recipe.title ?? '—'}
                    </p>
                    {hasSalad && (
                      <p className="text-xs text-avocado">🥗 +салат</p>
                    )}
                    {hasWarn && (
                      <p className="text-xs text-red-600">⚠️</p>
                    )}
                    {editMode && mainItem && (
                      <button
                        onClick={e => { e.stopPropagation(); setSwapTarget(swapTarget === mainItem.id ? null : mainItem.id); }}
                        className="mt-1 text-xs text-tomato hover:underline">
                        ✏️ Заменить
                      </button>
                    )}
                    {editMode && mainItem && swapTarget === mainItem.id && (
                      <div className="mt-2 space-y-1" onClick={e => e.stopPropagation()}>
                        <input type="text" value={searchRecipe}
                          onChange={e => setSearchRecipe(e.target.value)}
                          placeholder="Поиск рецепта..."
                          className="w-full text-xs rounded border border-gray-300 px-2 py-1"
                        />
                        {recipeOptions.map(r => (
                          <button key={r.id} disabled={swapping === mainItem.id}
                            onClick={() => handleSwap(mainItem.id, r.id)}
                            className="block w-full text-left text-xs px-2 py-1 rounded hover:bg-tomato/10 disabled:opacity-50">
                            {r.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        );
      })}

      {mealModal && (
        <MealDetailModal
          items={mealModal.items}
          mealLabel={mealModal.label}
          dayLabel={mealModal.dayLabel}
          onClose={() => setMealModal(null)}
        />
      )}
    </div>
  );
};
