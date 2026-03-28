import React, { useState, useEffect } from 'react';
import { menuApi } from '../../api/menu';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import type { Menu, MenuItem, MealType } from '../../types';
import { MEAL_LABELS } from '../../types';

const MEAL_ICONS: Record<MealType, string> = {
  breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎',
};

export const MenuPage: React.FC = () => {
  const [menus, setMenus] = useState<Menu[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [days, setDays] = useState(7);
  const [country, setCountry] = useState('');
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await menuApi.list();
      const d = data as any;
      if (Array.isArray(d)) setMenus(d);
      else if (Array.isArray(d?.results)) setMenus(d.results);
      else setMenus([]);
      if (data.results.length) setActiveMenuId(data.results[0].id);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const { data } = await menuApi.generate({
        period_days: days,
        start_date: today,
        country: country || undefined,
      });
      setMenus([data, ...menus]);
      setActiveMenuId(data.id);
      setShowForm(false);
    } finally { setGenerating(false); }
  };

  if (loading) return <PageSpinner />;

  const activeMenu = menus.find((m) => m.id === activeMenuId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-chocolate">Меню</h1>
        <Button onClick={() => setShowForm(!showForm)}>✨ Сгенерировать</Button>
      </div>

      {/* Generate form */}
      {showForm && (
        <Card className="p-5">
          <h2 className="font-semibold mb-4">Новое меню</h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-chocolate">Количество дней: {days}</label>
              <input type="range" min={1} max={14} value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full mt-1 accent-tomato" />
            </div>
            <div>
              <label className="text-sm font-medium text-chocolate">Страна (необязательно)</label>
              <input type="text" value={country} onChange={(e) => setCountry(e.target.value)}
                placeholder="Например: Россия"
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm" />
            </div>
            <div className="flex gap-3">
              <Button onClick={handleGenerate} loading={generating}>Сгенерировать</Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>Отмена</Button>
            </div>
          </div>
        </Card>
      )}

      {/* Menu selector */}
      {menus.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {menus.map((m) => (
            <button key={m.id} onClick={() => setActiveMenuId(m.id)}
              className={[
                'px-3 py-1.5 rounded-xl text-sm whitespace-nowrap border transition',
                m.id === activeMenuId
                  ? 'bg-tomato text-white border-tomato'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-tomato',
              ].join(' ')}>
              {new Date(m.start_date).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}
              {' — '}
              {new Date(m.end_date).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}
            </button>
          ))}
        </div>
      )}

      {!activeMenu ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">📋</div>
          <p className="text-lg font-medium">Меню пока нет</p>
          <p className="text-sm mt-1">Нажмите «Сгенерировать» чтобы составить меню</p>
        </div>
      ) : (
        <MenuGrid menu={activeMenu} onRefresh={load} />
      )}
    </div>
  );
};

const MenuGrid: React.FC<{ menu: Menu; onRefresh: () => void }> = ({ menu, onRefresh }) => {
  const days = Array.from({ length: menu.period_days }, (_, i) => i);

  return (
    <div className="space-y-3">
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
                return (
                  <div key={meal} className="p-3 rounded-xl bg-rice">
                    <div className="flex items-center gap-1 mb-1">
                      <span>{MEAL_ICONS[meal]}</span>
                      <span className="text-xs text-gray-500">{MEAL_LABELS[meal]}</span>
                    </div>
                    <p className="text-xs text-chocolate font-medium line-clamp-2">
                      {item?.recipe.title ?? '—'}
                    </p>
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
