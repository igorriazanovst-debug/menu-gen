import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { logout } from '../../store/slices/authSlice';
import { useIsPremium } from '../../hooks/usePremium';

const NAV = [
  { path: '/dashboard',     icon: '🏠', label: 'Главная',      premium: true  },
  { path: '/menu',          icon: '📋', label: 'Меню',         premium: false },
  { path: '/recipes',       icon: '📖', label: 'Рецепты',      premium: false },
  { path: '/family',        icon: '👨‍👩‍👧', label: 'Семья',        premium: false },
  { path: '/diary',         icon: '📓', label: 'Дневник',      premium: false },
  { path: '/fridge',        icon: '🧊', label: 'Холодильник',  premium: true  },
  { path: '/shopping',      icon: '🛒', label: 'Покупки',      premium: false },
  { path: '/subscriptions', icon: '💳', label: 'Подписка',     premium: false },
  { path: '/profile',       icon: '👤', label: 'Профиль',      premium: false },
];

export const Sidebar: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const isPremium = useIsPremium();
  // Free-юзеру premium-пункты не показываем вовсе (страницы не грузятся).
  const items = NAV.filter((n) => !n.premium || isPremium);
  // MG_CONSTRUCTOR: конструктор — только специалистам/стаффу.
  const isSpecialist = !!(user && (user.is_staff || user.is_specialist));

  return (
    <aside className="w-56 min-h-screen bg-sidebar text-sidebar-fg flex flex-col">
      {/* MG_SKIN: слот логотипа (заменить на <Logo/> белой версией, когда придёт
          ассет: logo_full_white ~h-7, читаемый на тёмном сайдбаре). */}
      <div className="px-6 py-5 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🍅</span>
          <span className="font-bold text-lg text-sidebar-fg">MenuGen</span>
        </div>
        {user && (
          <p className="text-xs text-sidebar-muted mt-1 truncate">{user.name}</p>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {items.map(({ path, icon, label }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-colors',
                isActive
                  ? 'bg-primary/20 text-primary font-semibold'
                  : 'text-sidebar-muted hover:bg-white/5 hover:text-sidebar-fg',
              ].join(' ')
            }
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
        {/* MG_CONSTRUCTOR: пункт только для специалистов/стаффа */}
        {isSpecialist && (
          <NavLink
            to="/constructor"
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-colors',
                isActive
                  ? 'bg-primary/20 text-primary font-semibold'
                  : 'text-sidebar-muted hover:bg-white/5 hover:text-sidebar-fg',
              ].join(' ')
            }
          >
            <span className="text-base">🛠️</span>
            Конструктор
          </NavLink>
        )}
      </nav>

      {/* Logout + юридические ссылки */}
      <div className="px-3 py-4 border-t border-white/10">
        <button
          onClick={() => dispatch(logout())}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-xl text-sm text-sidebar-muted hover:bg-white/5 hover:text-sidebar-fg transition-colors"
        >
          <span>🚪</span> Выйти
        </button>
        {/* MG_LEGAL */}
        <div className="mt-2 px-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-sidebar-muted">
          <NavLink to="/requisites" className="hover:text-sidebar-fg">Реквизиты</NavLink>
          <NavLink to="/offer" className="hover:text-sidebar-fg">Оферта</NavLink>
        </div>
      </div>
    </aside>
  );
};
