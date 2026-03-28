import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { swapMenuItemSpecialist } from "../../store/specialistSlice";
import api from "../../api/axios";

interface MenuDetail {
  id: number;
  start_date: string;
  end_date: string;
  period_days: number;
  status: string;
  items: MenuItem[];
}

interface MenuItem {
  id: number;
  day_offset: number;
  meal_type: string;
  quantity: number;
  recipe: {
    id: number;
    title: string;
    calories: number | null;
    cook_time: number | null;
  };
  member_name: string | null;
}

interface RecipeOption {
  id: number;
  title: string;
}

const MEAL_LABELS: Record<string, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  dinner: "Ужин",
  snack: "Перекус",
};

export const ClientMenuEditorPage: React.FC = () => {
  const { familyId, menuId } = useParams<{ familyId: string; menuId: string }>();
  const fid = Number(familyId);
  const mid = Number(menuId);
  const dispatch = useAppDispatch();

  const [menu, setMenu] = useState<MenuDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [swapItemId, setSwapItemId] = useState<number | null>(null);
  const [recipeSearch, setRecipeSearch] = useState("");
  const [recipeOptions, setRecipeOptions] = useState<RecipeOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api
      .get(`/specialists/cabinet/clients/${fid}/menus/${mid}/`)
      .then((r) => setMenu(r.data))
      .finally(() => setLoading(false));
  }, [fid, mid]);

  useEffect(() => {
    if (recipeSearch.length < 2) {
      setRecipeOptions([]);
      return;
    }
    const t = setTimeout(() => {
      api
        .get(`/recipes/?search=${encodeURIComponent(recipeSearch)}&page_size=10`)
        .then((r) => setRecipeOptions(r.data.results ?? r.data));
    }, 350);
    return () => clearTimeout(t);
  }, [recipeSearch]);

  const handleSwap = async (itemId: number, recipeId: number) => {
    setSaving(true);
    try {
      await dispatch(
        swapMenuItemSpecialist({ familyId: fid, menuId: mid, itemId, recipeId })
      ).unwrap();
      // перезагружаем меню
      const r = await api.get(`/specialists/cabinet/clients/${fid}/menus/${mid}/`);
      setMenu(r.data);
      setSwapItemId(null);
      setRecipeSearch("");
      showToast("Рецепт заменён");
    } catch {
      showToast("Ошибка замены");
    } finally {
      setSaving(false);
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-tomato" />
      </div>
    );
  }

  if (!menu) return <p className="text-center text-gray-400 mt-16">Меню не найдено.</p>;

  const days = Array.from({ length: menu.period_days }, (_, i) => i);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <Link
        to={`/specialist/clients/${fid}`}
        className="text-sm text-avocado hover:underline mb-2 inline-block"
      >
        ← Назад к клиенту
      </Link>
      <h1 className="text-2xl font-bold text-chocolate mb-1">
        Редактор меню
      </h1>
      <p className="text-sm text-gray-400 mb-6">
        {menu.start_date} — {menu.end_date} · {menu.period_days} дней
      </p>

      <div className="space-y-6">
        {days.map((d) => {
          const dayItems = menu.items.filter((i) => i.day_offset === d);
          const dateStr = (() => {
            const dt = new Date(menu.start_date);
            dt.setDate(dt.getDate() + d);
            return dt.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
          })();
          return (
            <div key={d} className="bg-white rounded-2xl shadow p-4">
              <h2 className="font-semibold text-chocolate capitalize mb-3">{dateStr}</h2>
              <div className="space-y-2">
                {dayItems.map((item) => (
                  <div key={item.id} className="border border-gray-100 rounded-xl px-3 py-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs text-lemon font-semibold uppercase">
                          {MEAL_LABELS[item.meal_type] ?? item.meal_type}
                        </span>
                        {item.member_name && (
                          <span className="text-xs text-gray-400 ml-2">· {item.member_name}</span>
                        )}
                        <p className="text-chocolate font-medium">{item.recipe.title}</p>
                        {item.recipe.calories && (
                          <p className="text-xs text-gray-400">{item.recipe.calories} ккал</p>
                        )}
                      </div>
                      <button
                        onClick={() =>
                          setSwapItemId(swapItemId === item.id ? null : item.id)
                        }
                        className="text-sm text-avocado border border-avocado px-3 py-1 rounded-lg hover:bg-avocado hover:text-white transition"
                      >
                        Заменить
                      </button>
                    </div>

                    {swapItemId === item.id && (
                      <div className="mt-3 border-t pt-3">
                        <input
                          type="text"
                          placeholder="Поиск рецепта..."
                          value={recipeSearch}
                          onChange={(e) => setRecipeSearch(e.target.value)}
                          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-avocado"
                        />
                        {recipeOptions.length > 0 && (
                          <ul className="mt-2 border border-gray-100 rounded-lg divide-y max-h-48 overflow-y-auto">
                            {recipeOptions.map((r) => (
                              <li
                                key={r.id}
                                className="px-3 py-2 text-sm cursor-pointer hover:bg-rice"
                                onClick={() => handleSwap(item.id, r.id)}
                              >
                                {r.title}
                              </li>
                            ))}
                          </ul>
                        )}
                        {saving && (
                          <p className="text-xs text-gray-400 mt-1">Сохранение...</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {dayItems.length === 0 && (
                  <p className="text-xs text-gray-300">Нет блюд</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-chocolate text-white text-sm px-5 py-2.5 rounded-full shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
};
