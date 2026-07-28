import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { menuApi } from '../../api/menu';
import type { DeletedMenu, SwapResult } from '../../api/menu';
import { recipesApi } from '../../api/recipes';
import { fridgeApi } from '../../api/fridge'; // MG_PRODDISH: поиск продуктов
import { swapMenuItem, swapMenuItemProduct } from '../../api/menu'; // MG-402 / MG_PRODDISH
import type { Product } from '../../types';
import { useAppSelector, useAppDispatch } from '../../hooks/useAppDispatch';
import { initAuth } from '../../store/slices/authSlice'; // Freemium: refresh quota after generate
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import { ImageLightbox } from '../../components/ui/ImageLightbox'; // MG_PHOTOZOOM
import type { Menu, MenuItem, MealType, ComponentRole, Recipe } from '../../types';
import { MEAL_LABELS, COMPONENT_ROLE_LABELS, COMPONENT_ROLE_ICONS } from '../../types';
import type { NutritionTargets } from '../../types'; // MG_204_V_menu = 1
import { DayNutritionSummary } from '../../components/menu/DayNutritionSummary';
import { AllergenBadges } from '../../components/recipe/AllergenBadges';
import { MadePhotoControl } from '../../components/recipes/MadePhotoControl'; // MG_MADEPHOTO
import { useEscapeKey } from '../../hooks/useEscapeKey'; // MG_ESC
// MG_607_V_menupage
import { GenerateMenuForm } from '../../components/menu/GenerateMenuForm';

const MEAL_ICONS: Record<string, string> = {
  breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎',
};

const MEAL_SLOTS_3 = ['breakfast', 'lunch', 'dinner'] as const;
const MEAL_SLOTS_5 = ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner'] as const;

const MEAL_SLOT_LABEL: Record<string, string> = {
  breakfast: 'Завтрак', snack1: 'Перекус 1', lunch: 'Обед',
  snack2: 'Перекус 2', dinner: 'Ужин', snack: 'Перекус',
};

const ROLE_ORDER: ComponentRole[] = ['protein', 'grain', 'vegetable', 'fruit', 'dairy', 'oil', 'other'];

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('ru', { day: 'numeric', month: 'short' });
}
function addDays(dateStr: string, n: number) {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
}
function today() { return new Date().toISOString().split('T')[0]; }

// ── slot helpers ─────────────────────────────────────────────────────────────

/** Извлекаем slot для item: используем meal_slot, если есть; иначе fallback по meal_type */
function getSlotKey(item: MenuItem): string {
  if (item.meal_slot && typeof item.meal_slot === 'string' && item.meal_slot !== '') {
    return item.meal_slot;
  }
  return item.meal_type;
}

/** dbType из slot: snack1/snack2 → snack */
function slotToMealType(slot: string): MealType {
  if (slot.startsWith('snack')) return 'snack';
  return slot as MealType;
}

/** Сортирует компоненты по канонической роли */
function sortByRole(items: MenuItem[]): MenuItem[] {
  return [...items].sort((a, b) => {
    const ra = ROLE_ORDER.indexOf((a.component_role || 'other') as ComponentRole);
    const rb = ROLE_ORDER.indexOf((b.component_role || 'other') as ComponentRole);
    return (ra === -1 ? 99 : ra) - (rb === -1 ? 99 : rb);
  });
}


// ── MG-402: inline swap по food_group ───────────────────────────────────────

interface SwapInlineProps {
  itemId: number;
  menuId: number;
  foodGroup?: string | null;
  currentRecipeId: number;
  onSwapped: () => void;
}

const SwapInline: React.FC<SwapInlineProps> = ({ itemId, menuId, foodGroup, currentRecipeId, onSwapped }) => {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<'recipe' | 'product'>('recipe'); // MG_PRODDISH
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<{ id: number; title: string }[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pickedProduct, setPickedProduct] = useState<Product | null>(null);
  const [grams, setGrams] = useState('100');

  useEffect(() => {
    if (!open) return;
    let cancel = false;
    setLoading(true); setErr(null);
    if (mode === 'recipe') {
      const params: any = { page_size: 25 };
      if (search) params.search = search;
      if (foodGroup) params.food_group = foodGroup;
      recipesApi.list(params)
        .then(res => {
          if (cancel) return;
          const list = (res.data.results || []).filter((r: any) => r.id !== currentRecipeId);
          setItems(list);
        })
        .catch(() => { if (!cancel) setErr('Не удалось загрузить рецепты'); })
        .finally(() => { if (!cancel) setLoading(false); });
    } else {
      if (search.trim().length < 2) { setProducts([]); setLoading(false); return; }
      fridgeApi.searchProducts(search.trim())
        .then(list => { if (!cancel) setProducts(list); })
        .catch(() => { if (!cancel) setErr('Не удалось загрузить продукты'); })
        .finally(() => { if (!cancel) setLoading(false); });
    }
    return () => { cancel = true; };
  }, [open, search, foodGroup, currentRecipeId, mode]);

  const handlePick = async (recipeId: number) => {
    setErr(null);
    try {
      await swapMenuItem(menuId, itemId, recipeId);
      setOpen(false);
      onSwapped();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Ошибка замены');
    }
  };

  const handlePickProduct = async () => {
    if (!pickedProduct) return;
    setErr(null);
    try {
      await swapMenuItemProduct(menuId, itemId, pickedProduct.id, Math.max(1, Number(grams) || 100));
      setOpen(false);
      setPickedProduct(null);
      onSwapped();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Ошибка замены');
    }
  };

  const tabCls = (active: boolean) =>
    ['px-2 py-0.5 text-xs rounded border', active ? 'bg-tomato text-white border-tomato' : 'text-gray-500 border-border'].join(' ');

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="text-xs text-tomato hover:underline"
        title={foodGroup ? `Заменить (группа: ${foodGroup})` : 'Заменить'}
      >
        ✏️ Заменить
      </button>
      {open && (
        <div className="mt-2 border border-border rounded-lg p-2 bg-gray-50">
          <div className="flex items-center gap-2 mb-2">
            <button type="button" onClick={() => { setMode('recipe'); setPickedProduct(null); }} className={tabCls(mode === 'recipe')}>Рецепт</button>
            <button type="button" onClick={() => { setMode('product'); }} className={tabCls(mode === 'product')}>Продукт</button>
          </div>
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={mode === 'recipe' ? 'Поиск рецепта...' : 'Поиск продукта (напр. огурец)...'}
            className="w-full px-2 py-1 text-sm rounded-md border border-border focus:outline-none focus:border-tomato"
          />
          {loading && <p className="text-xs text-gray-400 mt-2">Загрузка...</p>}
          {err && <p className="text-xs text-red-600 mt-2">{err}</p>}

          {mode === 'recipe' && !loading && !err && items.length === 0 && (
            <p className="text-xs text-gray-400 mt-2">Ничего не найдено</p>
          )}
          {mode === 'recipe' && items.length > 0 && (
            <ul className="mt-2 max-h-48 overflow-y-auto divide-y divide-gray-200 bg-surface rounded-md">
              {items.map(r => (
                <li key={r.id} onClick={() => handlePick(r.id)}
                    className="px-2 py-1.5 text-xs cursor-pointer hover:bg-rice">
                  {r.title}
                </li>
              ))}
            </ul>
          )}

          {mode === 'product' && (
            pickedProduct ? (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-chocolate flex-1">{pickedProduct.name}</span>
                <input type="number" min={1} value={grams} onChange={e => setGrams(e.target.value)}
                       className="w-20 px-2 py-1 text-sm rounded-md border border-border text-center" title="Порция, г" />
                <span className="text-xs text-gray-400">г</span>
                <button type="button" onClick={handlePickProduct}
                        className="px-2 py-1 text-xs rounded bg-tomato text-white">ОК</button>
                <button type="button" onClick={() => setPickedProduct(null)}
                        className="text-xs text-gray-400">✕</button>
              </div>
            ) : products.length > 0 ? (
              <ul className="mt-2 max-h-48 overflow-y-auto divide-y divide-gray-200 bg-surface rounded-md">
                {products.map(p => (
                  <li key={p.id} onClick={() => { setPickedProduct(p); setGrams('100'); }}
                      className="px-2 py-1.5 text-xs cursor-pointer hover:bg-rice flex items-center gap-2">
                    <span className="flex-1">{p.name}</span>
                    {p.is_own && <span className="text-[10px] text-avocado">мой</span>}
                    {p.calories_per_100g != null && <span className="text-[10px] text-gray-400">{p.calories_per_100g} ккал/100г</span>}
                  </li>
                ))}
              </ul>
            ) : (!loading && search.trim().length >= 2 && (
              <p className="text-xs text-gray-400 mt-2">Продукт не найден</p>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// ── RecipeDetailModal ───────────────────────────────────────────────────────
// В меню у блюда только «список»-рецепт (без ingredients/steps) — догружаем полный.

const stepText = (s: unknown): string =>
  typeof s === 'string' ? s : (s && typeof s === 'object' && 'text' in (s as object)
    ? String((s as { text: unknown }).text) : '');

const RecipeDetailModal: React.FC<{ recipeId: number; onClose: () => void }> = ({ recipeId, onClose }) => {
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [zoom, setZoom] = useState(false); // MG_PHOTOZOOM
  useEscapeKey(() => { if (zoom) setZoom(false); else onClose(); }); // MG_ESC/PHOTOZOOM

  useEffect(() => {
    let cancel = false;
    setLoading(true); setErr(null);
    recipesApi.get(recipeId)
      .then(res => { if (!cancel) setRecipe(res.data); })
      .catch(() => { if (!cancel) setErr('Не удалось загрузить рецепт'); })
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, [recipeId]);

  const cal = recipe?.nutrition?.calories;
  const ingredients = recipe?.ingredients ?? [];
  const steps = recipe?.steps ?? [];

  return (
    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4"
         onClick={(e) => { e.stopPropagation(); onClose(); }}>
      <div className="bg-surface rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
           onClick={e => e.stopPropagation()}>
        {loading ? (
          <div className="p-10 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tomato" />
          </div>
        ) : err ? (
          <div className="p-6">
            <p className="text-red-600 text-sm">{err}</p>
            <button onClick={onClose} className="mt-3 text-sm text-tomato hover:underline">Закрыть</button>
          </div>
        ) : recipe ? (
          <>
            {recipe.image_url && (
              <img src={recipe.image_url} alt=""
                   onClick={() => setZoom(true)}
                   className="w-full h-52 object-cover rounded-t-2xl cursor-zoom-in"
                   onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
            )}
            {zoom && recipe.image_url && (
              <ImageLightbox src={recipe.image_url} alt={recipe.title} onClose={() => setZoom(false)} />
            )}
            <div className="p-6">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h2 className="text-xl font-bold text-chocolate">{recipe.title}</h2>
                <div className="flex items-center gap-2 shrink-0">
                  {/* MG_MADEPHOTO: «я приготовил — вот фото» */}
                  <MadePhotoControl recipeId={recipe.id} initialPhotos={(recipe as any).made_photos} />
                  <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
                </div>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500 mb-4">
                {recipe.cook_time && <span>⏱ {recipe.cook_time}</span>}
                {cal && <span>🔥 {cal.value} {cal.unit}</span>}
                {recipe.servings ? <span>🍽 {recipe.servings} порц.</span> : null}
              </div>

              <AllergenBadges allergens={recipe.allergens} className="mb-4" />

              {ingredients.length > 0 && (
                <div className="mb-4">
                  <h3 className="font-semibold text-chocolate mb-1">Ингредиенты</h3>
                  <ul className="list-disc pl-5 text-sm text-gray-700 space-y-0.5">
                    {ingredients.map((ing, i) => (
                      <li key={i}>
                        {ing.name}{ing.quantity ? `: ${ing.quantity}` : ''}{ing.unit ? ` ${ing.unit}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {steps.length > 0 && (
                <div>
                  <h3 className="font-semibold text-chocolate mb-1">Приготовление</h3>
                  <ol className="list-decimal pl-5 text-sm text-gray-700 space-y-1">
                    {steps.map((s, i) => <li key={i}>{stepText(s)}</li>)}
                  </ol>
                </div>
              )}

              {ingredients.length === 0 && steps.length === 0 && (
                <p className="text-sm text-gray-400">У этого рецепта не заполнены ингредиенты и шаги.</p>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};

// ── MealDetailModal ─────────────────────────────────────────────────────────

interface MealDetailModalProps {
  items: MenuItem[];
  mealLabel: string;
  dayLabel: string;
  onClose: () => void;
  menuId: number; // MG-402
  onSwapped: () => void; // MG-402
}

const MealDetailModal: React.FC<MealDetailModalProps> = ({ items, mealLabel, dayLabel, onClose, menuId, onSwapped }) => {
  const sorted = useMemo(() => sortByRole(items), [items]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [printing, setPrinting] = useState(false);
  // MG_ESC: Escape закрывает окно блюда, но только если поверх не открыта
  // карточка рецепта (её Escape закрывает её же).
  useEscapeKey(() => { if (detailId == null) onClose(); });

  const handlePrintRecipes = async () => {
    // В меню — только «список»-рецепты (без ingredients/steps): догружаем полные.
    // Окно открываем СРАЗУ (в обработчике клика), иначе блокировщик попапов сработает.
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write('<p style="font-family:sans-serif;margin:24px">Загрузка рецептов…</p>');
    setPrinting(true);
    try {
      // MG_PRODDISH: продукты-блюда не печатаем (у них нет рецепта) — пропускаем.
      const printable = sorted.filter((it) => it.recipe && it.recipe.id && !it.product);
      if (printable.length === 0) {
        win.document.open();
        win.document.write('<p style="font-family:sans-serif;margin:24px">В этом приёме только продукты — печатать нечего.</p>');
        win.document.close();
        return;
      }
      const full = await Promise.all(
        printable.map(async (item) => ({ item, recipe: (await recipesApi.get(item.recipe.id)).data })),
      );
      const html = full.map(({ item, recipe: r }) => {
        const ings = (r.ingredients || []).map((i) =>
          `<li>${i.name}${i.quantity ? ': ' + i.quantity : ''}${i.unit ? ' ' + i.unit : ''}</li>`).join('');
        const steps = (r.steps || []).map((s) => `<li>${stepText(s)}</li>`).join('');
        const cal = r.nutrition?.calories ? `${r.nutrition.calories.value} ${r.nutrition.calories.unit}` : '';
        const role = item.component_role || 'other';
        const roleLabel = COMPONENT_ROLE_LABELS[role as ComponentRole] || role;
        return `
          <h2>${COMPONENT_ROLE_ICONS[role as ComponentRole] || '🍽'} ${r.title}</h2>
          <p><em>Роль: ${roleLabel}</em></p>
          ${cal ? `<p>Калории: ${cal}</p>` : ''}
          ${r.cook_time ? `<p>Время: ${r.cook_time}</p>` : ''}
          ${ings ? `<h3>Ингредиенты</h3><ul>${ings}</ul>` : ''}
          ${steps ? `<h3>Приготовление</h3><ol>${steps}</ol>` : ''}
          <hr/>
        `;
      }).join('');
      win.document.open();
      win.document.write(`
        <html><head><title>${mealLabel} — ${dayLabel}</title>
        <style>body{font-family:sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#222}
        h1{color:#c2410c}h2{color:#444;margin-top:24px}h3{margin-top:12px}
        ul,ol{padding-left:22px}li{margin:4px 0}hr{border:0;border-top:1px solid #ddd;margin:24px 0}</style>
        </head><body><h1>${mealLabel} · ${dayLabel}</h1>${html}</body></html>
      `);
      win.document.close();
      setTimeout(() => win.print(), 300);
    } catch {
      win.document.open();
      win.document.write('<p style="font-family:sans-serif;margin:24px;color:#c00">Не удалось загрузить рецепты для печати.</p>');
      win.document.close();
    } finally {
      setPrinting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6"
           onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-chocolate">{mealLabel}</h2>
            <p className="text-sm text-gray-500 capitalize">{dayLabel}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={handlePrintRecipes} disabled={printing}
              className="px-3 py-1.5 rounded-xl bg-tomato text-white text-sm hover:bg-tomato/90 disabled:opacity-60">
              {printing ? '…' : '🖨 Печать'}
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
          </div>
        </div>

        <div className="space-y-4">
          {sorted.map(item => {
            const role = (item.component_role || 'other') as ComponentRole;
            return (
              <Card key={item.id} className="p-4">
                <div className="flex items-start gap-3">
                  {/* MG_IMGFIX: клик по изображению открывает рецепт */}
                  {item.recipe.image_url ? (
                    <img src={item.recipe.image_url} alt=""
                         className="w-20 h-20 rounded-xl object-cover flex-shrink-0 cursor-pointer"
                         onClick={() => setDetailId(item.recipe.id)}
                         onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                  ) : (
                    <div onClick={() => setDetailId(item.recipe.id)}
                         className="w-20 h-20 rounded-xl bg-rice flex items-center justify-center text-3xl flex-shrink-0 cursor-pointer">
                      {COMPONENT_ROLE_ICONS[role]}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-tomato/10 text-tomato">
                        {COMPONENT_ROLE_ICONS[role]} {COMPONENT_ROLE_LABELS[role]}
                      </span>
                    </div>
                    <button type="button" onClick={() => setDetailId(item.recipe.id)}
                            className="text-left font-semibold text-chocolate hover:text-tomato">
                      {item.recipe.title}
                    </button>
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
                      {item.recipe.cook_time && <span>⏱ {item.recipe.cook_time}</span>}
                      {item.recipe.nutrition?.calories &&
                        <span>🔥 {item.recipe.nutrition.calories.value} {item.recipe.nutrition.calories.unit}</span>}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <button type="button" onClick={() => setDetailId(item.recipe.id)}
                              className="text-xs text-tomato hover:underline">
                        📖 Рецепт
                      </button>
                      <SwapInline
                        itemId={item.id}
                        menuId={menuId}
                        foodGroup={(item.recipe as any).food_group ?? null}
                        currentRecipeId={item.recipe.id}
                        onSwapped={onSwapped}
                      />
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {detailId != null && (
        <RecipeDetailModal recipeId={detailId} onClose={() => setDetailId(null)} />
      )}
    </div>
  );
};

// ── MealCard (сворачиваемая карточка приёма) ────────────────────────────────

interface MealCardProps {
  slot: string;
  items: MenuItem[];
  warnings: Record<number, SwapResult>;
  onOpenModal: () => void;
}

const MealCard: React.FC<MealCardProps> = ({ slot, items, warnings, onOpenModal }) => {
  const sorted = useMemo(() => sortByRole(items), [items]);
  const dbType = slotToMealType(slot);
  const label  = MEAL_SLOT_LABEL[slot] || MEAL_LABELS[dbType] || slot;
  const hasWarn = sorted.some(i => warnings[i.id]?.allergen_warning || warnings[i.id]?.calorie_warning);

  if (sorted.length === 0) {
    return (
      <div className="p-3 rounded-xl bg-rice/50">
        <div className="flex items-center gap-1 mb-1">
          <span>{MEAL_ICONS[dbType] ?? '🍽'}</span>
          <span className="text-xs text-gray-500">{label}</span>
        </div>
        <p className="text-xs text-gray-400">—</p>
      </div>
    );
  }

  // DIARY_CHART/menu: приём показываем карточками блюд (миниатюра + название +
  // КБЖУ) — как в mobile; клик по карточке открывает подробности.
  return (
    <div
      role="button"
      onClick={onOpenModal}
      className={[
        'p-3 rounded-xl transition-all cursor-pointer hover:ring-1 hover:ring-tomato/40',
        hasWarn ? 'border-2 border-red-400 bg-red-50' : 'bg-rice',
      ].join(' ')}
    >
      <div className="flex items-center gap-1 mb-2">
        <span>{MEAL_ICONS[dbType] ?? '🍽'}</span>
        <span className="text-xs text-gray-500">{label}</span>
        <span className="ml-auto text-xs text-gray-400">{sorted.length}</span>
      </div>
      <div className="space-y-1.5">
        {sorted.map(item => {
          const role = (item.component_role || 'other') as ComponentRole;
          const cal = item.recipe.nutrition?.calories;
          return (
            <div key={item.id} className="flex items-center gap-2">
              {item.recipe.image_url ? (
                <img src={item.recipe.image_url} alt=""
                     className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                     onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
              ) : (
                <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center text-lg flex-shrink-0">
                  {COMPONENT_ROLE_ICONS[role]}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs text-chocolate leading-tight line-clamp-2">{item.recipe.title}</p>
                <p className="text-[10px] text-gray-400 truncate">
                  {COMPONENT_ROLE_LABELS[role]}
                  {cal && ` · 🔥 ${cal.value} ${cal.unit}`}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      {hasWarn && <p className="text-xs text-red-600 mt-1">⚠️</p>}
      <p className="mt-2 text-xs text-tomato">Подробнее →</p>
    </div>
  );
};

// ── MenuPage ────────────────────────────────────────────────────────────────

export const MenuPage: React.FC = () => {
  const user = useAppSelector(s => s.auth.user);
  const dispatch = useAppDispatch();
  const [menus, setMenus] = useState<Menu[]>([]);
  const [activeMenu, setActiveMenu] = useState<Menu | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [mealPlanType] = useState<'3' | '5'>(
    (user?.profile?.meal_plan_type ?? '3')
  );
  const [showGenerateForm, setShowGenerateForm] = useState(false);

  // MG_608_V_menupage: карантин
  const [showQuarantine, setShowQuarantine] = useState(false);
  const [quarantine, setQuarantine] = useState<DeletedMenu[]>([]);
  const [quarantineLoading, setQuarantineLoading] = useState(false);

  const STORAGE_KEY = 'menugen.lastMenuId';

  const loadDetail = useCallback(async (id: number) => {
    setDetailLoading(true);
    try {
      const { data } = await menuApi.get(id);
      setActiveMenu(data);
      try { localStorage.setItem(STORAGE_KEY, String(id)); } catch {}
    } catch {
      setError('Не удалось загрузить меню');
    } finally { setDetailLoading(false); }
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const { data } = await menuApi.list();
      const d = data as any;
      const list: Menu[] = Array.isArray(d) ? d : (Array.isArray(d?.results) ? d.results : []);
      setMenus(list);
      if (list.length) {
        // MG_608: восстанавливаем последний выбранный из localStorage
        let pickId = list[0].id;
        try {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (saved) {
            const sid = Number(saved);
            if (list.some(m => m.id === sid)) pickId = sid;
          }
        } catch {}
        await loadDetail(pickId);
      } else {
        setActiveMenu(null);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось загрузить меню');
    } finally { setLoading(false); }
  }, [loadDetail]);

  useEffect(() => { load(); }, []);  // eslint-disable-line

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить это меню? Его можно будет восстановить из Корзины в течение 24 часов.')) return;
    try {
      await menuApi.delete(id);
      setActiveMenu(null);
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      await load();
    } catch { alert('Ошибка удаления'); }
  };

  // ── quarantine ─────────────────────────────────────────────────────────
  const loadQuarantine = async () => {
    setQuarantineLoading(true);
    try {
      const { data } = await menuApi.quarantine();
      setQuarantine(Array.isArray(data) ? data : []);
    } catch {
      setQuarantine([]);
    } finally {
      setQuarantineLoading(false);
    }
    setShowQuarantine(true);
  };

  const handleRestore = async (deletedId: number) => {
    try {
      const { data } = await menuApi.restore(deletedId);
      setQuarantine(prev => prev.filter(d => d.id !== deletedId));
      setActiveMenu(data);
      try { localStorage.setItem(STORAGE_KEY, String(data.id)); } catch {}
      await load();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Ошибка восстановления');
    }
  };

  const handlePurge = async (deletedId: number) => {
    if (!window.confirm('Удалить это меню НАВСЕГДА? Это действие нельзя отменить.')) return;
    try {
      await menuApi.purge(deletedId);
      setQuarantine(prev => prev.filter(d => d.id !== deletedId));
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Ошибка');
    }
  };

  const handlePurgeAll = async () => {
    if (!window.confirm('Очистить ВЕСЬ карантин? Это действие нельзя отменить.')) return;
    try {
      await menuApi.purgeAll();
      setQuarantine([]);
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Ошибка');
    }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-chocolate">Меню</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={loadQuarantine}>🗑 Карантин</Button>
          <Button onClick={() => setShowGenerateForm(s => !s)}>
            ✨ Сгенерировать
          </Button>
        </div>
      </div>

      {/* MG_608_V_menupage: чипы выбора меню */}
      {menus.length > 1 && !showGenerateForm && (
        <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
          {menus.map(m => {
            const isActive = activeMenu?.id === m.id;
            return (
              <button
                key={m.id}
                onClick={() => loadDetail(m.id)}
                className={[
                  'flex-shrink-0 px-3 py-2 rounded-xl text-xs font-medium transition border',
                  isActive
                    ? 'bg-tomato text-white border-tomato'
                    : 'bg-surface text-chocolate border-border hover:border-tomato',
                ].join(' ')}
              >
                {formatDate(m.start_date)} — {formatDate(m.end_date)}
                <span className="ml-1 text-[10px] opacity-70">· {m.period_days} дн.</span>
              </button>
            );
          })}
        </div>
      )}

      {showGenerateForm && (
        <GenerateMenuForm
          initialMealPlan={mealPlanType}
          userAllergies={user?.allergies ?? []}
          userDisliked={user?.disliked_products ?? []}
          userProfile={user?.profile}
          menuQuota={user?.subscription_status?.menu_quota}
          onCancel={() => setShowGenerateForm(false)}
          onCreated={(m) => {
            setActiveMenu(m);
            try { localStorage.setItem(STORAGE_KEY, String(m.id)); } catch {}
            setShowGenerateForm(false);
            load();
            dispatch(initAuth()); // Freemium: обновить остаток квоты
          }}
        />
      )}

      {/* MG_608_V_menupage: модалка карантина */}
      {showQuarantine && (
        <Card className="p-5 border-2 border-yellow-400">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h2 className="font-semibold text-chocolate">Карантин меню</h2>
            <div className="flex gap-2">
              {quarantine.length > 0 && (
                <Button variant="ghost" onClick={handlePurgeAll} className="text-red-500 text-xs">
                  Очистить всё
                </Button>
              )}
              <button onClick={() => setShowQuarantine(false)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
          </div>
          {quarantineLoading ? (
            <p className="text-sm text-gray-400">Загрузка…</p>
          ) : quarantine.length === 0 ? (
            <p className="text-sm text-gray-400">Карантин пуст</p>
          ) : (
            <div className="space-y-2">
              {quarantine.map(d => (
                <div key={d.id}
                     className="flex items-center justify-between p-3 rounded-xl bg-yellow-50 border border-yellow-200 gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-chocolate">
                      Меню #{d.menu_id}
                      <span className="text-xs text-gray-400 ml-2">
                        {d.data?.start_date && d.data?.end_date
                          ? `${formatDate(d.data.start_date)} — ${formatDate(d.data.end_date)}`
                          : ''}
                      </span>
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Удалено: {new Date(d.deleted_at).toLocaleString('ru')}
                      {d.deleted_by_name ? ` · ${d.deleted_by_name}` : ''}
                    </p>
                    <p className="text-[11px] text-gray-400">
                      Истекает: {new Date(d.purge_after).toLocaleString('ru')}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRestore(d.id)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-avocado text-white hover:bg-avocado/90">
                      ↩ Восстановить
                    </button>
                    <button
                      onClick={() => handlePurge(d.id)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600">
                      🗑 Навсегда
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>}

      {menus.length === 0 ? (
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
          onRefresh={() => loadDetail(activeMenu.id)}
          onDelete={() => handleDelete(activeMenu.id)}
        />
      ) : null}
    </div>
  );
};

// ── MenuGrid ────────────────────────────────────────────────────────────────

interface MenuGridProps {
  menu: Menu;
  onRefresh: () => void;
  onDelete: () => void;
}

const MenuGrid: React.FC<MenuGridProps> = ({ menu, onRefresh, onDelete }) => {
  // MG_204_V_menu_inner
  const userProfile = useAppSelector(state => state.auth.user?.profile);
  const targets: NutritionTargets | null = (
    userProfile && userProfile.calorie_target
      ? {
          calorie_target:   userProfile.calorie_target,
          protein_target_g: String(userProfile.protein_target_g ?? ''),
          fat_target_g:     String(userProfile.fat_target_g ?? ''),
          carb_target_g:    String(userProfile.carb_target_g ?? ''),
          fiber_target_g:   String(userProfile.fiber_target_g ?? ''),
        }
      : (userProfile?.targets_calculated ?? null)
  );
  const [warnings] = useState<Record<number, SwapResult>>({});
  const [mealModal, setMealModal] = useState<{ items: MenuItem[]; label: string; dayLabel: string } | null>(null);

  // Определяем 3 vs 5 приёмов по meal_plan_type из filters_used.
  // Фоллбек через наличие snack2-item для старых меню без этого поля.
  const hasTwoSnacks = useMemo(() => {
    const mpt = (menu.filters_used as Record<string, unknown>)?.meal_plan_type;
    if (mpt === '5') return true;
    if (mpt === '3') return false;
    return (menu.items || []).some(i => getSlotKey(i) === 'snack2');
  }, [menu.filters_used, menu.items]);

  const slots: readonly string[] = hasTwoSnacks ? MEAL_SLOTS_5 : MEAL_SLOTS_3;

  const daysArr = Array.from({ length: menu.period_days }, (_, i) => i);

  // MG_FAMILYGEN: режим «каждому своё» → фильтр приёмов по члену семьи.
  const isPerMember = ((menu.filters_used as Record<string, unknown>)?.mode) === 'per_member';
  const myMemberId = menu.my_member_id ?? null;
  const isHead = !!menu.is_head;
  const memberOptions = useMemo(() => {
    if (!isPerMember) return [] as { id: number; name: string }[];
    const map = new Map<number, string>();
    (menu.items ?? []).forEach(i => {
      if (i.member != null) map.set(i.member, i.member_name || 'Участник');
    });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [isPerMember, menu.items]);
  const [viewMemberId, setViewMemberId] = useState<number | null>(myMemberId);
  useEffect(() => {
    // По умолчанию — свои приёмы; если своих нет (глава без блюд) — первый член.
    setViewMemberId(myMemberId ?? (memberOptions[0]?.id ?? null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menu.id]);
  const visibleItems = useMemo(() => {
    const all = menu.items ?? [];
    if (!isPerMember || viewMemberId == null) return all;
    return all.filter(i => i.member == null || i.member === viewMemberId);
  }, [menu.items, isPerMember, viewMemberId]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {formatDate(menu.start_date)} — {formatDate(menu.end_date)} · {menu.period_days} дн.
        </p>
        <Button variant="ghost" onClick={onDelete} className="text-red-400 hover:text-red-600 text-sm">
          🗑 Удалить
        </Button>
      </div>

      {/* MG_FAMILYGEN: выбор члена семьи (глава — любые; обычный член — только свои) */}
      {isPerMember && memberOptions.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500">
            {isHead ? 'Приёмы члена семьи:' : 'Ваши приёмы:'}
          </span>
          {isHead ? (
            memberOptions.map(m => (
              <button
                key={m.id}
                type="button"
                onClick={() => setViewMemberId(m.id)}
                className={[
                  'px-3 py-1 rounded-full border text-xs transition',
                  viewMemberId === m.id
                    ? 'border-tomato bg-tomato text-white'
                    : 'border-border bg-surface text-gray-600 hover:border-tomato/50',
                ].join(' ')}
              >
                {m.name}{m.id === myMemberId ? ' (вы)' : ''}
              </button>
            ))
          ) : (
            <span className="px-3 py-1 rounded-full bg-tomato/10 text-tomato text-xs">
              {memberOptions.find(m => m.id === myMemberId)?.name ?? 'Вы'}
            </span>
          )}
        </div>
      )}

      {daysArr.map(day => {
        const date = new Date(menu.start_date);
        date.setDate(date.getDate() + day);
        const dayLabel = date.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' });
        const dayItems = visibleItems.filter(i => i.day_offset === day);

        return (
          <Card key={day} className="p-4">
            <h3 className="font-semibold text-chocolate mb-3 capitalize">{dayLabel}</h3>
            {/* MG-204: дневная сводка КБЖУ */}
            <DayNutritionSummary items={dayItems} targets={targets} />
            <div className={`grid gap-2 ${slots.length === 5 ? 'grid-cols-2 sm:grid-cols-5' : 'grid-cols-3'}`}>
              {slots.map(slot => {
                const rawSlotItems = dayItems.filter(i => getSlotKey(i) === slot);
                const seenIds = new Set<number>();
                const slotItems = rawSlotItems.filter(i => {
                  if (seenIds.has(i.recipe.id)) return false;
                  seenIds.add(i.recipe.id);
                  return true;
                });
                const dbType = slotToMealType(slot);
                const label  = MEAL_SLOT_LABEL[slot] || MEAL_LABELS[dbType] || slot;
                return (
                  <MealCard
                    key={slot}
                    slot={slot}
                    items={slotItems}
                    warnings={warnings}
                    onOpenModal={() => setMealModal({ items: slotItems, label, dayLabel })}
                  />
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
          menuId={menu.id}
          onSwapped={() => { setMealModal(null); onRefresh(); }}
        />
      )}
    </div>
  );
};
