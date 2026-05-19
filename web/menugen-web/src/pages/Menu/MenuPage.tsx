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
import type { NutritionTargets } from '../../types'; // MG_204_V_menu = 1
import { DayNutritionSummary } from '../../components/menu/DayNutritionSummary';
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
                    : 'bg-white text-chocolate border-gray-200 hover:border-tomato',
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
          onCancel={() => setShowGenerateForm(false)}
          onCreated={(m) => {
            setActiveMenu(m);
            try { localStorage.setItem(STORAGE_KEY, String(m.id)); } catch {}
            setShowGenerateForm(false);
            load();
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
            {/* MG-204: дневная сводка КБЖУ */}
            <DayNutritionSummary items={dayItems} targets={targets} />
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
