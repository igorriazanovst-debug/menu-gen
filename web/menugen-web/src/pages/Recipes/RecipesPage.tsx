import React, { useState, useEffect, useCallback } from 'react';
import { recipesApi } from '../../api/recipes';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { RecipeEditModal } from '../../components/recipes/RecipeEditModal';
import { useAppSelector } from '../../hooks/useAppDispatch';
import type { Recipe } from '../../types';

export const RecipesPage: React.FC = () => {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [total,   setTotal]   = useState(0);
  const [page,    setPage]    = useState(1);
  const [search,  setSearch]  = useState('');
  const [loading, setLoading] = useState(false);
  const [selected,  setSelected]  = useState<Recipe | null>(null);
  const [editing,   setEditing]   = useState<Recipe | null>(null);

  const user = useAppSelector((s) => s.auth.user);
  const isAdmin = (user as any)?.user_type === 'admin';

  const load = useCallback(async (q = search, p = page) => {
    setLoading(true);
    try {
      const { data } = await recipesApi.list({ search: q || undefined, page: p });
      setRecipes(data.results ?? []);
      setTotal(data.count ?? 0);
    } finally { setLoading(false); }
  }, [search, page]);

  useEffect(() => { load(); }, []);

  const handleSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPage(1);
    load(search, 1);
  };

  const handleSaved = (updated: Recipe) => {
    setRecipes(prev => prev.map(r => r.id === updated.id ? updated : r));
    if (selected?.id === updated.id) setSelected(updated);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Рецепты</h1>
        <span className="text-sm text-gray-500">{total} рецептов</span>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3">
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

      {total > 20 && (
        <div className="flex justify-center gap-2 mt-4">
          {page > 1 && (
            <button onClick={() => { setPage(page-1); load(search, page-1); }}
              className="px-3 py-1 rounded-lg border text-sm hover:bg-gray-50">← Назад</button>
          )}
          <span className="px-3 py-1 text-sm text-gray-600">Стр. {page}</span>
          {page * 20 < total && (
            <button onClick={() => { setPage(page+1); load(search, page+1); }}
              className="px-3 py-1 rounded-lg border text-sm hover:bg-gray-50">Вперёд →</button>
          )}
        </div>
      )}

      {selected && (
        <RecipeModal
          recipe={selected}
          isAdmin={isAdmin}
          onClose={() => setSelected(null)}
          onEdit={() => { setEditing(selected); setSelected(null); }}
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
          className="w-full h-40 object-cover" loading="lazy"
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
        {(recipe.categories ?? []).slice(0, 2).map((c) => (
          <Badge key={c} color="gray">{c}</Badge>
        ))}
      </div>
    </div>
    {isAdmin && (
      <button
        onClick={(e) => { e.stopPropagation(); onEdit(); }}
        className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm text-gray-600 hover:text-tomato hover:bg-white rounded-lg px-2 py-1 text-xs font-medium shadow opacity-0 group-hover:opacity-100 transition-opacity"
      >
        ✏️ Изменить
      </button>
    )}
  </Card>
);

const RecipeModal: React.FC<{
  recipe: Recipe;
  isAdmin: boolean;
  onClose: () => void;
  onEdit: () => void;
}> = ({ recipe, isAdmin, onClose, onEdit }) => (
  <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      {recipe.image_url && (
        <img src={recipe.image_url} alt={recipe.title} className="w-full object-contain rounded-t-2xl bg-gray-50" />
      )}
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-xl font-bold text-chocolate">{recipe.title}</h2>
          <div className="flex items-center gap-2 shrink-0">
            {isAdmin && (
              <button
                onClick={onEdit}
                className="px-3 py-1 rounded-lg bg-tomato/10 text-tomato text-sm font-medium hover:bg-tomato/20 transition"
              >
                ✏️ Изменить
              </button>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>
        </div>
        {recipe.nutrition && (
          <div className="flex gap-4 mt-3 p-3 bg-rice rounded-xl flex-wrap">
            {[
              ['Калории', recipe.nutrition.calories],
              ['Белки',   recipe.nutrition.proteins],
              ['Жиры',    recipe.nutrition.fats],
              ['Углеводы',recipe.nutrition.carbs],
              ['Клетчатка',recipe.nutrition.fiber],
              ['Вес',     recipe.nutrition.weight],
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
        {(recipe.ingredients ?? []).length > 0 && (
          <div className="mt-4">
            <h3 className="font-semibold mb-2">Ингредиенты</h3>
            <ul className="space-y-1">
              {(recipe.ingredients ?? []).map((ing, i) => (
                <li key={i} className="text-sm flex gap-2">
                  <span className="text-tomato">•</span>
                  <span>{ing.name}</span>
                  {ing.quantity && <span className="text-gray-400">{ing.quantity} {ing.unit}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(recipe.steps ?? []).length > 0 && (
          <div className="mt-4">
            <h3 className="font-semibold mb-2">Приготовление</h3>
            <ol className="space-y-3">
              {(recipe.steps ?? []).map((step, i) => (
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
