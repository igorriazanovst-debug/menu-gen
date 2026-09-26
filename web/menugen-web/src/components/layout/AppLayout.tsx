import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { SyncIndicator } from './SyncIndicator'; // MG_T08
import { ErrorBoundary } from '../ErrorBoundary';

/**
 * MG_WEBMOBILE: оболочка сайта на узком экране.
 *
 * Раньше боковое меню стояло в одной строке с содержимым и имело жёсткую
 * ширину 224 пикселя — всегда, на любом экране. На телефоне шириной 360 это
 * забирало почти две трети, и контенту оставалось полтораста пикселей.
 * Свернуть меню было нельзя: ни бургера, ни выдвижной панели не существовало.
 *
 * Теперь до ширины `md` меню — выдвижная панель поверх содержимого, а сверху
 * полоса с кнопкой. От `md` и выше всё как было: панель на месте, полоса
 * скрыта. Правка сознательно не трогает сами страницы — они чинятся отдельно.
 */
export const AppLayout: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  // Переход по ссылке закрывает панель. Без этого человек нажимает пункт меню
  // и остаётся смотреть на ту же панель поверх новой страницы.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Панель: на узком экране выезжает поверх, на широком стоит в потоке. */}
      <div
        className={[
          'fixed inset-y-0 left-0 z-40 overflow-y-auto transition-transform duration-200',
          'md:static md:z-auto md:translate-x-0',
          menuOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        <Sidebar onNavigate={() => setMenuOpen(false)} />
      </div>

      {/* Затемнение под панелью: нажатие мимо меню — самый ожидаемый способ
          его закрыть. Только на узком экране: на широком закрывать нечего. */}
      {menuOpen && (
        <button
          type="button"
          aria-label="Закрыть меню"
          onClick={() => setMenuOpen(false)}
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
        />
      )}

      {/* min-w-0 обязателен: без него флекс-элемент не сжимается уже своего
          содержимого, и широкая таблица растягивает страницу целиком — вместе
          с ней уезжает и шапка. */}
      <main className="flex-1 min-w-0 p-4 md:p-6 overflow-auto">
        <div className="max-w-7xl mx-auto">
          {/* Полоса с кнопкой меню — только там, где панель спрятана. */}
          <div className="md:hidden flex items-center gap-3 mb-3">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Открыть меню"
              aria-expanded={menuOpen}
              className="rounded-xl border border-border px-3 py-2 text-lg leading-none text-chocolate"
            >
              ☰
            </button>
            <span className="font-bold text-chocolate">MenuGen</span>
            <div className="ml-auto">
              <SyncIndicator />
            </div>
          </div>

          {/* MG_T08: на широком экране индикатор остаётся справа сверху. */}
          <div className="hidden md:flex justify-end mb-2">
            <SyncIndicator />
          </div>

          {/* Падение страницы не должно сносить навигацию/всё приложение. */}
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
