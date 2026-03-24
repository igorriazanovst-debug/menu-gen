# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 3 — React веб-приложение ✅

---

## Этап 1 (бэкенд) — ЗАВЕРШЁН ✅
## Этап 2 (Flutter) — ЗАВЕРШЁН ✅
## Этап 3 (React Web) — ЗАВЕРШЁН ✅

---

## Веб-приложение (`web/menugen-web/`) — 29 TS/TSX файлов

### Стек
- React 18 + TypeScript, CRA
- Redux Toolkit (authSlice + initAuth)
- React Router v6 (вложенные роуты)
- Axios (JWT interceptor + auto-refresh)
- React Hook Form + Zod (валидация)
- Tailwind CSS (design system: tomato/avocado/lemon/rice/chocolate)

### Структура
```
src/
├── App.tsx                   # Router + PrivateRoute + store Provider
├── api/                      # client.ts (JWT interceptor), auth/recipes/menu/family/subscriptions
├── store/slices/authSlice.ts # Redux: initAuth, login, logout
├── hooks/useAppDispatch.ts   # Типизированные хуки
├── types/index.ts            # Все TypeScript интерфейсы
├── utils/api.ts              # getErrorMessage, formatDate
├── components/
│   ├── ui/                   # Button, Input, Card, Badge, Spinner
│   └── layout/               # Sidebar (навигация), AppLayout (Outlet)
└── pages/
    ├── Auth/LoginPage        # Форма входа с react-hook-form + zod
    ├── Dashboard/            # Быстрые действия, превью меню на сегодня
    ├── Menu/                 # Генератор + просмотр по дням (grid)
    ├── Recipes/              # Список + поиск + модальная карточка рецепта
    ├── Family/               # Участники, приглашение, удаление
    ├── Diary/                # Дневник питания + калории за день
    ├── Subscriptions/        # Тарифы + кнопка «Подключить» → ЮKassa
    └── Profile/              # Редактирование профиля
```

### Дизайн (цветовая схема ТЗ)
- Primary: `#E63946` (tomato)
- Secondary: `#588157` (avocado)
- Accent: `#F4A261` (lemon)
- Background: `#F1FAEE` (rice)
- Text: `#1D3557` (chocolate)

### TypeScript — 0 ошибок
`npx tsc --noEmit` — чисто

---

## Следующий шаг

**Этап 4 — Интеграции: VK OAuth + пуш-уведомления (FCM) + доставка**

- VK OAuth для авторизации (мобайл + веб)
- Firebase Cloud Messaging для пуш-уведомлений
- Ссылки на доставку (Яндекс/СберМаркет/ВкусВилл)
- Публикация меню в VK

---

## Запуск веб-приложения
```bash
cd web/menugen-web
cp .env.example .env
# Заполнить REACT_APP_API_BASE_URL
npm install --legacy-peer-deps
npm start
```

## Репозиторий
GitHub: (указать URL при пуше)
