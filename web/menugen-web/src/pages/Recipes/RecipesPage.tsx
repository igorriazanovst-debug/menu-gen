import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { recipesApi } from '../../api/recipes';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { RecipeEditModal } from '../../components/recipes/RecipeEditModal';
import { AllergenBadges } from '../../components/recipe/AllergenBadges';
import { MadePhotoControl } from '../../components/recipes/MadePhotoControl';
import { ImageLightbox } from '../../components/ui/ImageLightbox';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { useEscapeKey } from '../../hooks/useEscapeKey';
import { categoryLabel } from '../../constants/categories'; // MG_CATRU
import type { Recipe } from '../../types';

const MEAL_TYPES = [
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch',     label: 'Обед'    },
  { value: 'dinner',    label: 'Ужин'    },
  { value: 'snack',     label: 'Перекус' },
];

interface Filters {
  meal_type:    string;
  country:      string;
  calories_min: string;
  calories_max: string;
}

const EMPTY_FILTERS: Filters = { meal_type: '', country: '', calories_min: '', calories_max: '' };

const PAGE_SIZE = 20;

// Список страниц для пагинатора: всегда первая/последняя, окно вокруг текущей,
// «…» на разрывах. Напр. 1 … 4 5 [6] 7 8 … 20.
function pageWindow(current: number, totalPages: number): (number | '…')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const out: (number | '…')[] = [1];
  const from = Math.max(2, current - 1);
  const to = Math.min(totalPages - 1, current + 1);
  if (from > 2) out.push('…');
  for (let p = from; p <= to; p++) out.push(p);
  if (to < totalPages - 1) out.push('…');
  out.push(totalPages);
  return out;
}

export const RecipesPage: React.FC = () => {
  // Состояние страницы/поиска/фильтров живёт в URL (?page=&search=&…) — при
  // перезагрузке восстанавливается текущая страница, а не сбрасывается на 1.
  const [searchParams, setSearchParams] = useSearchParams();
  const initPage = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const initFilters: Filters = {
    meal_type:    searchParams.get('meal_type')    || '',
    country:      searchParams.get('country')      || '',
    calories_min: searchParams.get('calories_min') || '',
    calories_max: searchParams.get('calories_max') || '',
  };

  const [recipes,  setRecipes]  = useState<Recipe[]>([]);
  const [total,    setTotal]    = useState(0);
  const [page,     setPage]     = useState(initPage);
  const [search,   setSearch]   = useState(searchParams.get('search') || '');
  const [loading,  setLoading]  = useState(false);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [editing,  setEditing]  = useState<Recipe | null>(null);
  const [filters,  setFilters]  = useState<Filters>(initFilters);
  const [showFilters, setShowFilters] = useState(false);

  // Записать текущее состояние навигации в URL (пустые значения не пишем).
  const syncUrl = useCallback((p: number, q: string, f: Filters) => {
    const next: Record<string, string> = {};
    if (p > 1)          next.page         = String(p);
    if (q)              next.search       = q;
    if (f.meal_type)    next.meal_type    = f.meal_type;
    if (f.country)      next.country      = f.country;
    if (f.calories_min) next.calories_min = f.calories_min;
    if (f.calories_max) next.calories_max = f.calories_max;
    setSearchParams(next, { replace: true });
  }, [setSearchParams]);
  // MG_COUNTRYFILTER: список стран берём из БД (значения совпадают с сохранёнными
  // в рецептах), иначе фильтр по стране ничего не находит.
  const [countries, setCountries] = useState<string[]>([]);

  const user    = useAppSelector((s) => s.auth.user);
  const isAdmin = (user as any)?.user_type === 'admin';

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  const load = useCallback(async (q = search, p = page, f = filters) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page: p };
      if (q)          params.search       = q;
      if (f.meal_type)    params.meal_type    = f.meal_type;
      if (f.country)      params.country      = f.country;
      if (f.calories_min) params.calories_min = f.calories_min;
      if (f.calories_max) params.calories_max = f.calories_max;
      const { data } = await recipesApi.list(params);
      setRecipes(data.results ?? []);
      setTotal(data.count ?? 0);
    } finally { setLoading(false); }
  }, [search, page, filters]);

  useEffect(() => { load(); }, []);

  // MG_COUNTRYFILTER: подтягиваем реальные страны из БД для селекта фильтра.
  useEffect(() => {
    recipesApi.countries()
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : ((data as any)?.countries ?? []);
        setCountries(list.filter(Boolean));
      })
      .catch(() => { /* оставляем пустой список */ });
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    syncUrl(1, search, filters);
    load(search, 1, filters);
  };

  const handleFilterChange = (key: keyof Filters, value: string) => {
    const next = { ...filters, [key]: value };
    setFilters(next);
    setPage(1);
    syncUrl(1, search, next);
    load(search, 1, next);
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
    setSearch('');
    syncUrl(1, '', EMPTY_FILTERS);
    load('', 1, EMPTY_FILTERS);
  };

  // Переход на страницу p (кламп к [1, totalPages]) + URL + загрузка.
  const goToPage = (p: number) => {
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const np = Math.min(Math.max(1, p), totalPages);
    if (np === page) return;
    setPage(np);
    syncUrl(np, search, filters);
    load(search, np, filters);
  };

  const handleSaved = (updated: Recipe) => {
    setRecipes(prev => prev.map(r => r.id === updated.id ? updated : r));
    if (selected?.id === updated.id) setSelected(updated);
  };

  const handleDeleted = (id: number) => {
    setRecipes(prev => prev.filter(r => r.id !== id));
    setTotal(t => t - 1);
    setSelected(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Рецепты</h1>
        <span className="text-sm text-gray-500">{total} рецептов</span>
      </div>

      {/* Search + filter toggle */}
      <div className="flex gap-3">
        <form onSubmit={handleSearch} className="flex gap-3 flex-1">
          <Input
            className="flex-1"
            placeholder="Поиск рецептов..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit"
            className="px-4 py-2 rounded-xl bg-tomato text-white text-sm font-semibold hover:bg-red-700 transition">
            Найти
          </button>
        </form>
        <button
          onClick={() => setShowFilters(v => !v)}
          className={`px-4 py-2 rounded-xl border text-sm font-medium transition flex items-center gap-1
            ${showFilters ? 'bg-tomato/10 border-tomato text-tomato' : 'border-border text-gray-600 hover:bg-gray-50'}`}
        >
          🔽 Фильтры
          {activeFilterCount > 0 && (
            <span className="bg-tomato text-white rounded-full w-5 h-5 text-xs flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="bg-surface rounded-2xl border border-border p-4 space-y-4 shadow-sm">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Тип приёма пищи */}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Приём пищи</label>
              <select
                value={filters.meal_type}
                onChange={e => handleFilterChange('meal_type', e.target.value)}
                className="w-full rounded-xl border border-border px-3 py-2 text-sm text-gray-700 focus:outline-none focus:border-tomato"
              >
                <option value="">Все</option>
                {MEAL_TYPES.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            {/* Кухня */}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Кухня</label>
              <select
                value={filters.country}
                onChange={e => handleFilterChange('country', e.target.value)}
                className="w-full rounded-xl border border-border px-3 py-2 text-sm text-gray-700 focus:outline-none focus:border-tomato"
              >
                <option value="">Все</option>
                {countries.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Калории от */}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Калории от</label>
              <Input
                type="number"
                placeholder="0"
                value={filters.calories_min}
                onChange={e => handleFilterChange('calories_min', e.target.value)}
              />
            </div>

            {/* Калории до */}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Калории до</label>
              <Input
                type="number"
                placeholder="1000"
                value={filters.calories_max}
                onChange={e => handleFilterChange('calories_max', e.target.value)}
              />
            </div>
          </div>

          {activeFilterCount > 0 && (
            <button onClick={clearFilters}
              className="text-xs text-tomato hover:underline">
              Сбросить фильтры
            </button>
          )}
        </div>
      )}

      {loading ? <PageSpinner /> : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {recipes.map((r) => (
            <RecipeCard
              key={r.id}
              recipe={r}
              isAdmin={isAdmin}
              onClick={() => setSelected(r)}
              onEdit={() => setEditing(r)}
            />
          ))}
        </div>
      )}

      {total > PAGE_SIZE && (() => {
        const totalPages = Math.ceil(total / PAGE_SIZE);
        const btn = 'min-w-[36px] h-9 px-2 rounded-lg border text-sm flex items-center justify-center';
        return (
          <nav className="flex flex-wrap justify-center items-center gap-1.5 mt-4" aria-label="Пагинация">
            <button onClick={() => goToPage(page - 1)} disabled={page <= 1}
              className={`${btn} hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed`}
              aria-label="Предыдущая страница">←</button>
            {pageWindow(page, totalPages).map((p, i) =>
              p === '…' ? (
                <span key={`e${i}`} className="px-1 text-sm text-gray-400 select-none">…</span>
              ) : (
                <button key={p} onClick={() => goToPage(p)}
                  aria-current={p === page ? 'page' : undefined}
                  className={`${btn} ${p === page
                    ? 'bg-primary border-primary text-primary-fg font-semibold'
                    : 'hover:bg-gray-50'}`}>{p}</button>
              )
            )}
            <button onClick={() => goToPage(page + 1)} disabled={page >= totalPages}
              className={`${btn} hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed`}
              aria-label="Следующая страница">→</button>

            {/* Переход на конкретную страницу */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const el = (e.currentTarget.elements.namedItem('goto') as HTMLInputElement);
                const n = parseInt(el.value, 10);
                if (!Number.isNaN(n)) goToPage(n);
                el.value = '';
              }}
              className="flex items-center gap-1.5 ml-2"
            >
              <span className="text-sm text-gray-500">Стр.</span>
              <input
                name="goto"
                type="number"
                min={1}
                max={totalPages}
                placeholder={String(page)}
                aria-label="Перейти на страницу"
                className="w-16 h-9 px-2 rounded-lg border text-sm text-center focus:outline-none focus:border-primary"
              />
              <span className="text-sm text-gray-500">из {totalPages}</span>
              <button type="submit" className={`${btn} hover:bg-gray-50`} aria-label="Перейти">→</button>
            </form>
          </nav>
        );
      })()}

      {selected && (
        <RecipeModal
          recipe={selected}
          isAdmin={isAdmin}
          onClose={() => setSelected(null)}
          onEdit={() => { setEditing(selected); setSelected(null); }}
          onDeleted={handleDeleted}
        />
      )}

      {editing && (
        <RecipeEditModal
          recipe={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
};

// ── RecipeCard ───────────────────────────────────────────────────────────────

const RecipeCard: React.FC<{
  recipe: Recipe;
  isAdmin: boolean;
  onClick: () => void;
  onEdit: () => void;
}> = ({ recipe, isAdmin, onClick, onEdit }) => (
  <Card className="cursor-pointer hover:shadow-md transition-shadow overflow-hidden relative group">
    <div onClick={onClick}>
      {recipe.image_url ? (
        <img src={recipe.image_url} alt={recipe.title}
          className="w-full object-contain rounded-t-2xl bg-gray-50" loading="lazy"
          onError={(e) => { e.currentTarget.style.display = 'none'; }} />
      ) : (
        <div className="w-full h-40 bg-gradient-to-br from-tomato/10 to-avocado/10 flex items-center justify-center">
          <span className="text-4xl">🍽️</span>
        </div>
      )}
      <div className="p-4">
        <h3 className="font-semibold text-chocolate text-sm line-clamp-2">{recipe.title}</h3>
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          {recipe.cook_time && <span className="text-xs text-gray-400">⏱ {recipe.cook_time}</span>}
          {recipe.nutrition?.calories && (
            <span className="text-xs text-gray-400">
              🔥 {recipe.nutrition.calories.value} {recipe.nutrition.calories.unit}
            </span>
          )}
        </div>
        {/* MG_CATRU: чипы категорий по-русски (незнакомые токены — как есть) */}
        {(recipe.categories ?? []).slice(0, 2).map((c) => (
          <Badge key={c} color="gray">{categoryLabel(c)}</Badge>
        ))}
      </div>
    </div>
    {isAdmin && (
      <button
        onClick={(e) => { e.stopPropagation(); onEdit(); }}
        className="absolute top-2 right-2 bg-surface/90 backdrop-blur-sm text-gray-600 hover:text-tomato hover:bg-surface rounded-lg px-2 py-1 text-xs font-medium shadow opacity-0 group-hover:opacity-100 transition-opacity"
      >
        ✏️ Изменить
      </button>
    )}
  </Card>
);

// ── RecipeModal ──────────────────────────────────────────────────────────────

const RecipeModal: React.FC<{
  recipe: Recipe;
  isAdmin: boolean;
  onClose: () => void;
  onEdit: () => void;
  onDeleted: (id: number) => void;
}> = ({ recipe, isAdmin, onClose, onEdit, onDeleted }) => {
  const [confirming, setConfirming] = useState(false);
  const [deleting,   setDeleting]   = useState(false);
  const [zoom, setZoom] = useState(false); // MG_PHOTOZOOM
  // MG_RECIPETEXT: карточка приходит из списка (RecipeListSerializer) без
  // ingredients/steps — догружаем полный рецепт по id, иначе в окне нет текста.
  const [full, setFull] = useState<Recipe>(recipe);
  useEscapeKey(onClose); // MG_ESC: закрытие по Escape
  useEffect(() => {
    let cancel = false;
    recipesApi.get(recipe.id)
      .then(res => { if (!cancel) setFull(res.data); })
      .catch(() => { /* оставляем данные из списка */ });
    return () => { cancel = true; };
  }, [recipe.id]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await recipesApi.delete(recipe.id);
      onDeleted(recipe.id);
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {full.image_url && (
          <img src={full.image_url} alt={full.title}
            onClick={() => setZoom(true)}
            className="w-full object-contain rounded-t-2xl bg-gray-50 cursor-zoom-in" />
        )}
        {zoom && full.image_url && (
          <ImageLightbox src={full.image_url} alt={full.title} onClose={() => setZoom(false)} />
        )}
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-xl font-bold text-chocolate">{full.title}</h2>
            <div className="flex items-center gap-2 shrink-0">
              {/* MG_MADEPHOTO: «я приготовил — вот фото» */}
              <MadePhotoControl recipeId={full.id} initialPhotos={(full as any).made_photos} />
              {isAdmin && !confirming && (
                <>
                  <button onClick={onEdit}
                    className="px-3 py-1 rounded-lg bg-tomato/10 text-tomato text-sm font-medium hover:bg-tomato/20 transition">
                    ✏️ Изменить
                  </button>
                  <button onClick={() => setConfirming(true)}
                    className="px-3 py-1 rounded-lg bg-red-50 text-red-500 text-sm font-medium hover:bg-red-100 transition">
                    🗑️
                  </button>
                </>
              )}
              {isAdmin && confirming && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Удалить?</span>
                  <button onClick={handleDelete} disabled={deleting}
                    className="px-3 py-1 rounded-lg bg-red-500 text-white text-xs font-medium hover:bg-red-600 transition disabled:opacity-50">
                    {deleting ? '...' : 'Да'}
                  </button>
                  <button onClick={() => setConfirming(false)}
                    className="px-3 py-1 rounded-lg border text-xs text-gray-500 hover:bg-gray-50 transition">
                    Нет
                  </button>
                </div>
              )}
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
            </div>
          </div>

          {full.nutrition && (
            <div className="flex gap-4 mt-3 p-3 bg-rice rounded-xl flex-wrap">
              {[
                ['Калории',   full.nutrition.calories],
                ['Белки',     full.nutrition.proteins],
                ['Жиры',      full.nutrition.fats],
                ['Углеводы',  full.nutrition.carbs],
                ['Клетчатка', full.nutrition.fiber],
                ['Вес',       full.nutrition.weight],
              ].map(([label, val]) => val && (
                <div key={String(label)} className="text-center">
                  <p className="text-xs text-gray-500">{String(label)}</p>
                  <p className="font-semibold text-chocolate text-sm">
                    {(val as any).value} {(val as any).unit}
                  </p>
                </div>
              ))}
            </div>
          )}

          <AllergenBadges allergens={full.allergens} className="mt-4" />

          {(full.ingredients ?? []).length > 0 && (
            <div className="mt-4">
              <h3 className="font-semibold mb-2">Ингредиенты</h3>
              <ul className="space-y-1">
                {(full.ingredients ?? []).map((ing, i) => (
                  <li key={i} className="text-sm flex gap-2">
                    <span className="text-tomato">•</span>
                    <span>{ing.name}</span>
                    {ing.quantity && <span className="text-gray-400">{ing.quantity} {ing.unit}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(full.steps ?? []).length > 0 && (
            <div className="mt-4">
              <h3 className="font-semibold mb-2">Приготовление</h3>
              <ol className="space-y-3">
                {(full.steps ?? []).map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="shrink-0 w-6 h-6 rounded-full bg-tomato text-white text-xs flex items-center justify-center font-bold">
                      {i + 1}
                    </span>
                    <p className="text-chocolate">{step.text}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
