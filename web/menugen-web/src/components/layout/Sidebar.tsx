import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../hooks/useAppDispatch';
import { logout } from '../../store/slices/authSlice';

const NAV = [
  { path: '/dashboard',     icon: '🏠', label: 'Главная'      },
  { path: '/menu',          icon: '📋', label: 'Меню'         },
  { path: '/recipes',       icon: '📖', label: 'Рецепты'      },
  { path: '/family',        icon: '👨‍👩‍👧', label: 'Семья'        },
  { path: '/diary',         icon: '📓', label: 'Дневник'      },
  { path: '/fridge',        icon: '🧊', label: 'Холодильник'  },
  { path: '/shopping',      icon: '🛒', label: 'Покупки'      },
  { path: '/subscriptions', icon: '💳', label: 'Подписка'     },
  { path: '/profile',       icon: '👤', label: 'Профиль'      },
];

export const Sidebar: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);

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
        {NAV.map(({ path, icon, label }) => (
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
      </nav>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-white/10">
        <button
          onClick={() => dispatch(logout())}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-xl text-sm text-sidebar-muted hover:bg-white/5 hover:text-sidebar-fg transition-colors"
        >
          <span>🚪</span> Выйти
        </button>
      </div>
    </aside>
  );
};
