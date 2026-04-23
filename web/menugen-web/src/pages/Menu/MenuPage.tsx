import React, { useState, useEffect, useCallback } from 'react';
import { menuApi } from '../../api/menu';
import type { DeletedMenu, SwapResult } from '../../api/menu';
import { recipesApi } from '../../api/recipes';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import type { Menu, MealType } from '../../types';
import { MEAL_LABELS } from '../../types';

const MEAL_ICONS: Record<MealType, string> = {
  breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎',
};

// ── helpers ──────────────────────────────────────────────────────────────────

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('ru', { day: 'numeric', month: 'short' });
}

function addDays(dateStr: string, n: number) {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
}

function today() {
  return new Date().toISOString().split('T')[0];
}

// ── MenuPage ─────────────────────────────────────────────────────────────────

export const MenuPage: React.FC = () => {
  const user = useAppSelector((s) => s.auth.user);

  const [menus, setMenus]                   = useState<Menu[]>([]);
  const [loading, setLoading]               = useState(true);
  const [generating, setGenerating]         = useState(false);
  const [showForm, setShowForm]             = useState(false);
  const [showQuarantine, setShowQuarantine] = useState(false);
  const [quarantine, setQuarantine]         = useState<DeletedMenu[]>([]);

  // form
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate]     = useState(() => addDays(today(), 6));
  const [days, setDays]           = useState(7);
  const [country, setCountry]     = useState('');
  const [countries, setCountries] = useState<string[]>([]);
  const [maxCookTime, setMaxCookTime]   = useState<number | ''>('');
  const [calorieMin, setCalorieMin]     = useState<number | ''>('');
  const [calorieMax, setCalorieMax]     = useState<number | ''>('');

  // active menu detail
  const [activeMenuId, setActiveMenuId]         = useState<number | null>(null);
  const [activeMenuDetail, setActiveMenuDetail] = useState<Menu | null>(null);
  const [detailLoading, setDetailLoading]       = useState(false);

  // ── load list ──────────────────────────────────────────────────────────────
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
      .then((r: any) => setCountries(r.data || []))
      .catch(() => {});
  }, [load]);

  // recalc days on date change
  useEffect(() => {
    const s = new Date(startDate), e = new Date(endDate);
    if (e >= s) setDays(Math.min(30, Math.max(1, Math.round((e.getTime() - s.getTime()) / 86400000) + 1)));
  }, [startDate, endDate]);

  // load detail on active change
  useEffect(() => {
    if (!activeMenuId) { setActiveMenuDetail(null); return; }
    setDetailLoading(true);
    menuApi.get(activeMenuId)
      .then(({ data }) => setActiveMenuDetail(data))
      .catch(() => setActiveMenuDetail(null))
      .finally(() => setDetailLoading(false));
  }, [activeMenuId]);

  // ── generate ───────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const { data } = await menuApi.generate({
        period_days: days,
        start_date: startDate,
        country: country || undefined,
        ...(maxCookTime ? { max_cook_time: Number(maxCookTime) } : {}),
        ...(calorieMin  ? { calorie_min:   Number(calorieMin)  } : {}),
        ...(calorieMax  ? { calorie_max:   Number(calorieMax)  } : {}),
      });
      setMenus((prev) => [data, ...prev.filter((m) => m.id !== data.id)]);
      setActiveMenuId(data.id);
      setActiveMenuDetail(data);
      setShowForm(false);
    } catch (e) { alert('Ошибка генерации'); }
    finally { setGenerating(false); }
  };

  // ── delete ─────────────────────────────────────────────────────────────────
  const handleDelete = async (menuId: number) => {
    if (!window.confirm('Переместить меню в карантин? Его можно будет восстановить в течение 24 часов.')) return;
    try {
      await menuApi.delete(menuId);
      setMenus((prev) => prev.filter((m) => m.id !== menuId));
      if (activeMenuId === menuId) {
        const next = menus.find((m) => m.id !== menuId);
        setActiveMenuId(next?.id ?? null);
      }
    } catch { alert('Ошибка удаления'); }
  };

  // ── quarantine ─────────────────────────────────────────────────────────────
  const loadQuarantine = async () => {
    try {
      const { data } = await menuApi.quarantine();
      setQuarantine(Array.isArray(data) ? data : []);
    } catch { setQuarantine([]); }
    setShowQuarantine(true);
  };

  const handleRestore = async (deletedId: number) => {
    try {
      const { data } = await menuApi.restore(deletedId);
      setQuarantine((prev) => prev.filter((d) => d.id !== deletedId));
      setMenus((prev) => [data, ...prev]);
      setActiveMenuId(data.id);
      setActiveMenuDetail(data);
    } catch { alert('Ошибка восстановления'); }
  };

  if (loading) return <PageSpinner />;

  const activeMenu = activeMenuDetail?.id === activeMenuId ? activeMenuDetail : null;
  const isHead = user?.user_type === 'admin'; // упрощённо; расширяется через API

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-chocolate">Меню</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={loadQuarantine}>🗑 Карантин</Button>
          <Button onClick={() => setShowForm(!showForm)}>✨ Сгенерировать</Button>
        </div>
      </div>

      {/* quarantine modal */}
      {showQuarantine && (
        <Card className="p-5 border-2 border-yellow-400">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-chocolate">Карантин меню</h2>
            <button onClick={() => setShowQuarantine(false)} className="text-gray-400 hover:text-gray-600">✕</button>
          </div>
          {quarantine.length === 0 ? (
            <p className="text-sm text-gray-400">Карантин пуст</p>
          ) : (
            <div className="space-y-2">
              {quarantine.map((d) => (
                <div key={d.id} className="flex items-center justify-between p-3 rounded-xl bg-yellow-50 border border-yellow-200">
                  <div>
                    <p className="text-sm font-medium text-chocolate">
                      Меню #{d.menu_id} &nbsp;
                      <span className="text-xs text-gray-400">
                        {formatDate(d.data.start_date)} — {formatDate(d.data.end_date)}
                      </span>
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Удалено: {new Date(d.deleted_at).toLocaleString('ru')} &nbsp;|&nbsp;
                      {d.can_purge
                        ? <span className="text-red-500">можно удалить навсегда</span>
                        : <span>восстановление до {new Date(d.purge_after).toLocaleString('ru')}</span>
                      }
                    </p>
                  </div>
                  {!d.can_purge && (
                    <Button variant="secondary" onClick={() => handleRestore(d.id)}>Восстановить</Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* generate form */}
      {showForm && (
        <Card className="p-5">
          <h2 className="font-semibold mb-4">Новое меню</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-chocolate">Дата начала</label>
                <input type="date" value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-sm font-medium text-chocolate">Дата окончания</label>
                <input type="date" value={endDate} min={startDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-chocolate">Количество дней: {days}</label>
              <input type="range" min={1} max={30} value={days}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setDays(n);
                  setEndDate(addDays(startDate, n - 1));
                }}
                className="w-full mt-1 accent-tomato" />
            </div>
            <div>
              <label className="text-sm font-medium text-chocolate">Кухня (страна)</label>
              <select value={country} onChange={(e) => setCountry(e.target.value)}
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm bg-white">
                <option value="">Любая</option>
                {countries.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-chocolate">Макс. время готовки (мин)</label>
              <input type="number" value={maxCookTime} min={5} max={300} step={5}
                onChange={(e) => setMaxCookTime(e.target.value ? Number(e.target.value) : '')}
                placeholder="Не ограничено"
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-chocolate">Калории от (ккал/день)</label>
                <input type="number" value={calorieMin} min={500} max={5000} step={100}
                  onChange={(e) => setCalorieMin(e.target.value ? Number(e.target.value) : '')}
                  placeholder="Не ограничено"
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-sm font-medium text-chocolate">Калории до (ккал/день)</label>
                <input type="number" value={calorieMax} min={500} max={5000} step={100}
                  onChange={(e) => setCalorieMax(e.target.value ? Number(e.target.value) : '')}
                  placeholder="Не ограничено"
                  className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex gap-3">
              <Button onClick={handleGenerate} loading={generating}>Сгенерировать</Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>Отмена</Button>
            </div>
          </div>
        </Card>
      )}

      {/* menu tabs */}
      {menus.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {menus.map((m) => (
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

      {/* active menu */}
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
          canDelete={true}
        />
      ) : null}
    </div>
  );
};

// ── MenuGrid ─────────────────────────────────────────────────────────────────

interface MenuGridProps {
  menu: Menu;
  onRefresh: () => void;
  onDelete: () => void;
  canDelete: boolean;
}

const MenuGrid: React.FC<MenuGridProps> = ({ menu, onRefresh, onDelete, canDelete }) => {
  const [warnings, setWarnings] = useState<Record<number, SwapResult>>({});
  const [swapping, setSwapping] = useState<number | null>(null);
  const [searchRecipe, setSearchRecipe] = useState('');
  const [swapTarget, setSwapTarget] = useState<number | null>(null); // item id
  const [recipeOptions, setRecipeOptions] = useState<{ id: number; title: string }[]>([]);

  const days = Array.from({ length: menu.period_days }, (_, i) => i);

  // search recipes for swap
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
      setWarnings((prev) => ({ ...prev, [itemId]: data }));
      setSwapTarget(null);
      setSearchRecipe('');
      onRefresh();
    } catch { alert('Ошибка замены блюда'); }
    finally { setSwapping(null); }
  };

  return (
    <div className="space-y-3">
      {/* menu header actions */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {formatDate(menu.start_date)} — {formatDate(menu.end_date)} · {menu.period_days} дн.
        </p>
        {canDelete && (
          <Button variant="ghost" onClick={onDelete} className="text-red-400 hover:text-red-600 text-sm">
            🗑 Удалить меню
          </Button>
        )}
      </div>

      {days.map((day) => {
        const date = new Date(menu.start_date);
        date.setDate(date.getDate() + day);
        const dayItems = (menu.items ?? []).filter((i) => i.day_offset === day);

        return (
          <Card key={day} className="p-4">
            <h3 className="font-semibold text-chocolate mb-3">
              {date.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' })}
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(['breakfast', 'lunch', 'dinner', 'snack'] as MealType[]).map((meal) => {
                const item = dayItems.find((i) => i.meal_type === meal);
                const warn = item ? warnings[item.id] : undefined;
                const hasAllergen = warn?.allergen_warning;
                const hasCal = warn?.calorie_warning;
                const hasWarn = hasAllergen || hasCal;

                return (
                  <div key={meal}
                    className={[
                      'p-3 rounded-xl transition-all',
                      hasWarn
                        ? 'border-4 border-red-600 animate-pulse bg-red-50'
                        : 'bg-rice',
                    ].join(' ')}>
                    <div className="flex items-center gap-1 mb-1">
                      <span>{MEAL_ICONS[meal]}</span>
                      <span className="text-xs text-gray-500">{MEAL_LABELS[meal]}</span>
                    </div>
                    <p className="text-xs text-chocolate font-medium line-clamp-2 mb-1">
                      {item?.recipe.title ?? '—'}
                    </p>
                    {hasAllergen && (
                      <p className="text-xs text-red-700 font-bold">
                        ⚠️ Аллергены: {warn!.allergens_found.join(', ')}
                      </p>
                    )}
                    {hasCal && (
                      <p className="text-xs text-red-700 font-bold">
                        ⚠️ Вне коридора калорий ({Math.round(warn!.recipe_calories)} ккал)
                      </p>
                    )}
                    {item && (
                      <button
                        onClick={() => setSwapTarget(swapTarget === item.id ? null : item.id)}
                        className="mt-1 text-xs text-tomato hover:underline">
                        ✏️ Заменить
                      </button>
                    )}
                    {item && swapTarget === item.id && (
                      <div className="mt-2 space-y-1">
                        <input
                          type="text"
                          value={searchRecipe}
                          onChange={(e) => setSearchRecipe(e.target.value)}
                          placeholder="Поиск рецепта..."
                          className="w-full text-xs rounded border border-gray-300 px-2 py-1"
                        />
                        {recipeOptions.map((r) => (
                          <button key={r.id}
                            disabled={swapping === item.id}
                            onClick={() => handleSwap(item.id, r.id)}
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
    </div>
  );
};
