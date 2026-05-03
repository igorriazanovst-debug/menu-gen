import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { menuApi } from '../../api/menu';
import type { DeletedMenu, SwapResult } from '../../api/menu';
import { recipesApi } from '../../api/recipes';
import { swapMenuItem } from '../../api/menu'; // MG-402
import { useAppSelector } from '../../hooks/useAppDispatch';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import type { Menu, MenuItem, MealType, ComponentRole } from '../../types';
import { MEAL_LABELS, COMPONENT_ROLE_LABELS, COMPONENT_ROLE_ICONS } from '../../types';

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
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<{ id: number; title: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancel = false;
    setLoading(true); setErr(null);
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
    return () => { cancel = true; };
  }, [open, search, foodGroup, currentRecipeId]);

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
        <div className="mt-2 border border-gray-200 rounded-lg p-2 bg-gray-50">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Поиск рецепта..."
            className="w-full px-2 py-1 text-sm rounded-md border border-gray-200 focus:outline-none focus:border-tomato"
          />
          {loading && <p className="text-xs text-gray-400 mt-2">Загрузка...</p>}
          {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
          {!loading && !err && items.length === 0 && (
            <p className="text-xs text-gray-400 mt-2">Ничего не найдено</p>
          )}
          {items.length > 0 && (
            <ul className="mt-2 max-h-48 overflow-y-auto divide-y divide-gray-200 bg-white rounded-md">
              {items.map(r => (
                <li
                  key={r.id}
                  onClick={() => handlePick(r.id)}
                  className="px-2 py-1.5 text-xs cursor-pointer hover:bg-rice"
                >
                  {r.title}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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

  const handlePrintRecipes = () => {
    const win = window.open('', '_blank');
    if (!win) return;
    const html = sorted.map(item => {
      const r = item.recipe;
      const ings = (r.ingredients || []).map((i: any) =>
        `<li>${i.name}${i.quantity ? ': ' + i.quantity : ''}${i.unit ? ' ' + i.unit : ''}</li>`).join('');
      const steps = (r.steps || []).map((s: any) => `<li>${s.text || s}</li>`).join('');
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
    win.document.write(`
      <html><head><title>${mealLabel} — ${dayLabel}</title>
      <style>body{font-family:sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#222}
      h1{color:#c2410c}h2{color:#444;margin-top:24px}h3{margin-top:12px}
      ul,ol{padding-left:22px}li{margin:4px 0}hr{border:0;border-top:1px solid #ddd;margin:24px 0}</style>
      </head><body><h1>${mealLabel} · ${dayLabel}</h1>${html}</body></html>
    `);
    win.document.close();
    setTimeout(() => win.print(), 300);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6"
           onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-chocolate">{mealLabel}</h2>
            <p className="text-sm text-gray-500 capitalize">{dayLabel}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={handlePrintRecipes}
              className="px-3 py-1.5 rounded-xl bg-tomato text-white text-sm hover:bg-tomato/90">
              🖨 Печать
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
                  {item.recipe.image_url ? (
                    <img src={item.recipe.image_url} alt="" className="w-20 h-20 rounded-xl object-cover flex-shrink-0"
                         onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                  ) : (
                    <div className="w-20 h-20 rounded-xl bg-rice flex items-center justify-center text-3xl flex-shrink-0">
                      {COMPONENT_ROLE_ICONS[role]}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-tomato/10 text-tomato">
                        {COMPONENT_ROLE_ICONS[role]} {COMPONENT_ROLE_LABELS[role]}
                      </span>
                    </div>
                    <h3 className="font-semibold text-chocolate">{item.recipe.title}</h3>
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
                      {item.recipe.cook_time && <span>⏱ {item.recipe.cook_time}</span>}
                      {item.recipe.nutrition?.calories &&
                        <span>🔥 {item.recipe.nutrition.calories.value} {item.recipe.nutrition.calories.unit}</span>}
                    </div>
                    <SwapInline
                      itemId={item.id}
                      menuId={menuId}
                      foodGroup={(item.recipe as any).food_group ?? null}
                      currentRecipeId={item.recipe.id}
                      onSwapped={onSwapped}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
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
  const [expanded, setExpanded] = useState(false);
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

  const roleIcons = sorted.map(i =>
    COMPONENT_ROLE_ICONS[(i.component_role || 'other') as ComponentRole]
  ).join('');

  return (
    <div className={[
      'p-3 rounded-xl transition-all',
      hasWarn ? 'border-2 border-red-400 bg-red-50' : 'bg-rice',
    ].join(' ')}>
      <button
        type="button"
        className="w-full text-left"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-1 mb-1">
          <span>{MEAL_ICONS[dbType] ?? '🍽'}</span>
          <span className="text-xs text-gray-500">{label}</span>
          <span className="ml-auto text-xs text-gray-400">
            {expanded ? '▾' : '▸'}
          </span>
        </div>
        <p className="text-xs text-chocolate font-medium">
          {sorted.length} {sorted.length === 1 ? 'компонент' : sorted.length < 5 ? 'компонента' : 'компонентов'}
        </p>
        <p className="text-sm mt-0.5">{roleIcons}</p>
        {hasWarn && <p className="text-xs text-red-600 mt-1">⚠️</p>}
      </button>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-gray-200 space-y-1.5">
          {sorted.map(item => {
            const role = (item.component_role || 'other') as ComponentRole;
            return (
              <div key={item.id} className="flex items-start gap-2 text-xs">
                <span className="flex-shrink-0">{COMPONENT_ROLE_ICONS[role]}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-chocolate line-clamp-2 leading-tight">{item.recipe.title}</p>
                  <p className="text-[10px] text-gray-400">{COMPONENT_ROLE_LABELS[role]}</p>
                </div>
              </div>
            );
          })}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOpenModal(); }}
            className="mt-2 w-full text-xs text-tomato hover:underline"
          >
            Подробнее →
          </button>
        </div>
      )}
    </div>
  );
};

// ── MenuPage ────────────────────────────────────────────────────────────────

export const MenuPage: React.FC = () => {
  const user = useAppSelector(s => s.auth.user);
  const [menus, setMenus] = useState<Menu[]>([]);
  const [activeMenu, setActiveMenu] = useState<Menu | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [periodDays, setPeriodDays] = useState(7);
  const [startDate, setStartDate] = useState(today());
  const [mealPlanType, setMealPlanType] = useState<'3' | '5'>(
    (user?.profile?.meal_plan_type ?? '3')
  );
  const [showGenerateForm, setShowGenerateForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const { data } = await menuApi.list();
      const list = data.results ?? [];
      setMenus(list);
      if (list.length && !activeMenu) {
        await loadDetail(list[0].id);
      } else if (!list.length) {
        setActiveMenu(null);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось загрузить меню');
    } finally { setLoading(false); }
  }, [activeMenu]);

  const loadDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const { data } = await menuApi.get(id);
      setActiveMenu(data);
    } catch {
      setError('Не удалось загрузить меню');
    } finally { setDetailLoading(false); }
  };

  useEffect(() => { load(); }, []);  // eslint-disable-line

  const handleGenerate = async () => {
    setGenerating(true); setError('');
    try {
      const payload: any = {
        period_days: periodDays,
        start_date: startDate,
        meal_plan_type: mealPlanType,
      };
      const { data } = await menuApi.generate(payload);
      setActiveMenu(data);
      setShowGenerateForm(false);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка генерации меню');
    } finally { setGenerating(false); }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить это меню? Его можно будет восстановить из Корзины в течение 24 часов.')) return;
    try {
      await menuApi.delete(id);
      setActiveMenu(null);
      await load();
    } catch { alert('Ошибка удаления'); }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Меню</h1>
        <Button onClick={() => setShowGenerateForm(s => !s)}>
          ✨ Сгенерировать
        </Button>
      </div>

      {showGenerateForm && (
        <Card className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">С даты</label>
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Период (дней)</label>
              <input type="number" min={1} max={14} value={periodDays}
                onChange={e => setPeriodDays(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl border border-gray-200" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Приёмов пищи</label>
              <div className="flex gap-1">
                <button type="button" onClick={() => setMealPlanType('3')}
                  className={[
                    'flex-1 px-3 py-2 rounded-xl border text-sm',
                    mealPlanType === '3'
                      ? 'border-tomato bg-tomato/10 text-tomato'
                      : 'border-gray-200 bg-white text-gray-600',
                  ].join(' ')}>3</button>
                <button type="button" onClick={() => setMealPlanType('5')}
                  className={[
                    'flex-1 px-3 py-2 rounded-xl border text-sm',
                    mealPlanType === '5'
                      ? 'border-tomato bg-tomato/10 text-tomato'
                      : 'border-gray-200 bg-white text-gray-600',
                  ].join(' ')}>5</button>
              </div>
            </div>
          </div>
          <div className="flex justify-end mt-3">
            <Button onClick={handleGenerate} loading={generating}>Создать меню</Button>
          </div>
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
  const [warnings] = useState<Record<number, SwapResult>>({});
  const [mealModal, setMealModal] = useState<{ items: MenuItem[]; label: string; dayLabel: string } | null>(null);

  // Определяем 3 vs 5 приёмов:
  // если у любого item meal_slot = snack2 — это 5 приёмов
  const hasTwoSnacks = useMemo(() => {
    return (menu.items || []).some(i => getSlotKey(i) === 'snack2');
  }, [menu.items]);

  const slots: readonly string[] = hasTwoSnacks ? MEAL_SLOTS_5 : MEAL_SLOTS_3;

  const daysArr = Array.from({ length: menu.period_days }, (_, i) => i);

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

      {daysArr.map(day => {
        const date = new Date(menu.start_date);
        date.setDate(date.getDate() + day);
        const dayLabel = date.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' });
        const dayItems = (menu.items ?? []).filter(i => i.day_offset === day);

        return (
          <Card key={day} className="p-4">
            <h3 className="font-semibold text-chocolate mb-3 capitalize">{dayLabel}</h3>
            <div className={`grid gap-2 ${slots.length === 5 ? 'grid-cols-2 sm:grid-cols-5' : 'grid-cols-3'}`}>
              {slots.map(slot => {
                const slotItems = dayItems.filter(i => getSlotKey(i) === slot);
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
