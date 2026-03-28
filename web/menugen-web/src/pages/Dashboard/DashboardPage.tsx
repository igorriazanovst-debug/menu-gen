import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppSelector } from '../../hooks/useAppDispatch';
import { menuApi } from '../../api/menu';
import { subscriptionsApi } from '../../api/subscriptions';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import type { Menu, Subscription } from '../../types';

const PLAN_COLOR: Record<string, 'gray' | 'blue' | 'green' | 'yellow' | 'red'> = {
  free: 'gray', lite: 'blue', basic: 'green', basic_plus: 'yellow', premium: 'red',
};

export const DashboardPage: React.FC = () => {
  const user = useAppSelector((s) => s.auth.user);
  const [menus, setMenus] = useState<Menu[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      menuApi.list().then((r) => {
        const d = r.data as any;
        if (Array.isArray(d)) setMenus(d);
        else if (Array.isArray(d?.results)) setMenus(d.results);
        else setMenus([]);
      }),
      subscriptionsApi.current().then((r) => setSub(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageSpinner />;

  const activeMenu = menus.find((m) => m.status === 'active');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-chocolate">
          Добро пожаловать, {user?.name}! 👋
        </h1>
        <p className="text-gray-500 text-sm mt-1">Планируйте питание легко и вкусно</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4">
          <p className="text-sm text-gray-500">Активное меню</p>
          <p className="text-xl font-bold text-chocolate mt-1">
            {activeMenu ? `${activeMenu.period_days} дней` : 'Нет'}
          </p>
          {activeMenu && (
            <p className="text-xs text-gray-400 mt-0.5">
              до {new Date(activeMenu.end_date).toLocaleDateString('ru')}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-sm text-gray-500">Тариф</p>
          <div className="mt-1 flex items-center gap-2">
            <p className="text-xl font-bold text-chocolate">{sub?.plan.name ?? 'Free'}</p>
            <Badge color={PLAN_COLOR[sub?.plan.code ?? 'free'] ?? 'gray'}>
              {sub?.status === 'active' ? 'Активна' : 'Free'}
            </Badge>
          </div>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-gray-500">Дата входа</p>
          <p className="text-xl font-bold text-chocolate mt-1">
            {user?.created_at
              ? new Date(user.created_at).toLocaleDateString('ru', { day: 'numeric', month: 'long' })
              : '—'}
          </p>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="font-semibold text-chocolate mb-4">Быстрые действия</h2>
        <div className="flex flex-wrap gap-3">
          <Link to="/menu"><Button>📋 Перейти к меню</Button></Link>
          <Link to="/recipes"><Button variant="secondary">📖 Каталог рецептов</Button></Link>
          <Link to="/family"><Button variant="ghost">👨‍👩‍👧 Управление семьёй</Button></Link>
        </div>
      </Card>

      {activeMenu && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-chocolate">Сегодняшнее меню</h2>
            <Link to="/menu" className="text-sm text-tomato hover:underline">Открыть →</Link>
          </div>
          <TodayMeals menu={activeMenu} />
        </Card>
      )}
    </div>
  );
};

const TodayMeals: React.FC<{ menu: Menu }> = ({ menu }) => {
  const items = menu.items ?? [];
  const today = new Date();
  const start = new Date(menu.start_date);
  const dayOffset = Math.floor((today.getTime() - start.getTime()) / 86400000);
  const todayItems = items.filter((i) => i.day_offset === dayOffset);

  if (!todayItems.length) return <p className="text-gray-400 text-sm">Нет блюд на сегодня</p>;

  const labels: Record<string, string> = {
    breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус',
  };

  return (
    <div className="space-y-2">
      {todayItems.map((item) => (
        <div key={item.id} className="flex items-center gap-3 p-3 rounded-xl bg-rice">
          <span className="text-sm text-gray-500 w-20 shrink-0">{labels[item.meal_type]}</span>
          <span className="font-medium text-chocolate text-sm">{item.recipe.title}</span>
        </div>
      ))}
    </div>
  );
};
