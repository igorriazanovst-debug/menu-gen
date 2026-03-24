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
  { path: '/subscriptions', icon: '💳', label: 'Подписка'     },
  { path: '/profile',       icon: '👤', label: 'Профиль'      },
];

export const Sidebar: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);

  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-100 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🍅</span>
          <span className="font-bold text-lg text-chocolate">MenuGen</span>
        </div>
        {user && (
          <p className="text-xs text-gray-500 mt-1 truncate">{user.name}</p>
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
                  ? 'bg-tomato/10 text-tomato font-semibold'
                  : 'text-gray-600 hover:bg-gray-50',
              ].join(' ')
            }
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={() => dispatch(logout())}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-xl text-sm text-red-600 hover:bg-red-50 transition-colors"
        >
          <span>🚪</span> Выйти
        </button>
      </div>
    </aside>
  );
};
