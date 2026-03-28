# MenuGen — Резюме для нового чата

**Проект:** Генератор меню (MenuGen)
**Дата:** Март 2026
**Репозиторий:** https://github.com/igorriazanovst-debug/menugen

---

## Правила работы

1. Диалог на русском языке
2. Если непонятно — задавай вопрос
3. Исправления через скрипт где возможно
4. Файлы проекта в Project Knowledge (GitHub)
5. Не объясняй. Не извиняйся. Только код.
6. НИКОГДА не хардкодь URL, токены, пароли
7. Резюме для нового чата — в виде файла
8. В начале нового чата: резюме → файлы проекта → вопрос если нужен

---

## Статус этапов

| Этап | Описание | Статус |
|---|---|---|
| 1 | Бэкенд (Django + PostgreSQL) | ✅ |
| 2 | Flutter мобильное приложение | ✅ |
| 3 | React веб-приложение | ✅ |
| 3.5 | Локальный стенд Windows 11 | ✅ |
| 4 | Интеграции (VK, FCM, доставка) | ⏳ |
| 5 | Кабинет специалиста (React) | ✅ |
| 6 | Тестирование и релиз | 🔄 |

---

## Локальный стенд Windows 11 — ✅

**Путь проекта:** `C:\Temp\2026\menu-gen\menu-gen`

### Запуск
```powershell
cd C:\Temp\2026\menu-gen\menu-gen
docker compose up -d
cd web\menugen-web
npm start
```

### Если порты заняты
```powershell
Stop-Service postgresql-x64-15
Stop-Service redis*
taskkill /F /IM redis-server.exe
docker compose up -d
```

### Сервисы
| Сервис | URL |
|---|---|
| Swagger | http://localhost:8000/api/v1/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| API | http://localhost:8000/api/v1/ |
| React web | http://localhost:3000 |

### Тестовый пользователь
- Email: i.ryazanov78@yandex.ru
- Семья создана (family id: 1, role: head)

---

## Этап 1: Бэкенд — ✅

**Стек:** Python 3.11, Django 4.2, DRF, JWT, drf-spectacular, PostgreSQL 15, Redis 7, Celery
**Файлов:** 155 Python, 92 теста, 0 ошибок `manage.py check`

### Важные особенности API
- `GET /menu/` — возвращает список без пагинации
- `GET /diary/` — возвращает список без пагинации
- `GET /subscriptions/current/` — 404 если нет подписки (норм)
- `GET /subscriptions/plans/` — возвращает список без пагинации
- `Family.objects.create()` требует `owner=user` обязательно

---

## Этап 3: React веб-приложение — ✅

**Стек:** React 18 + TypeScript, Redux Toolkit, React Router v6, Axios, RHF + Zod, Tailwind CSS v3

### Важные особенности
- Tailwind **v3** (не v4!) — иначе ломается PostCSS
- Хуки: `src/hooks/useAppDispatch.ts` (не `store/hooks`)
- HTTP-клиент: `src/api/client.ts` (не `api/axios`)
- `menu.items`, `recipe.ingredients`, `recipe.steps`, `recipe.categories` — везде `?? []`

### Запуск
```powershell
cd web\menugen-web
npm install --legacy-peer-deps
npm start
```

---

## Этап 5: Кабинет специалиста — ✅

Бэкенд: `backend/apps/specialists/` — serializers.py, views.py, urls.py заполнены полностью.

React: `src/store/specialistSlice.ts` + `src/pages/specialist/` (5 страниц S-01..S-05).

Маршруты: `/specialist`, `/specialist/register`, `/specialist/clients/:familyId`, `/specialist/clients/:familyId/menus/:menuId`, `/specialist/clients/:familyId/recommendations/new`

---

## Этап 6: React Jest тесты — ✅ (47/47)

### Конфигурация (package.json)
CRA 5 + react-router-dom v7 + Windows — много подводных камней. Итоговая рабочая конфигурация:

```json
"jest": {
  "transformIgnorePatterns": ["node_modules/(?!(react-router|react-router-dom)/)"],
  "moduleNameMapper": {
    "^(\\.\\./)+api/auth$": "<rootDir>/src/api/__mocks__/auth.js",
    "^(\\.\\./)+api/client$": "<rootDir>/src/api/__mocks__/client.js",
    "react-router-dom": "<rootDir>/node_modules/react-router-dom/dist/index.js",
    "react-router/dom": "<rootDir>/node_modules/react-router/dist/development/dom-export.js"
  }
}
```

**ВАЖНО:** секцию `jest` в package.json писать только через `[System.IO.File]::WriteAllText` — PowerShell `ConvertTo-Json` экранирует `<` и `>` в Unicode что ломает `<rootDir>`.

### Файлы моков
```
src/api/__mocks__/auth.js    — мок authApi (CommonJS)
src/api/__mocks__/client.js  — мок axios client (CommonJS)
src/setupTests.js            — полифил TextEncoder/TextDecoder
```

### Расположение тестов
```
src/store/slices/authSlice.test.ts       — 16 тестов
src/store/specialistSlice.test.ts        — 15 тестов
src/pages/Auth/LoginPage.test.tsx        — 10 тестов
src/components/layout/Sidebar.test.tsx   — 6 тестов
```

### Запуск тестов
```powershell
cd web\menugen-web
npm test -- --watchAll=false
npm test -- --watchAll=false --coverage
```

### Особенности компонентов (важно для тестов)
- Кнопка при `loading=true` показывает "Загрузка..." (не "Войти")
- Label поля пароля: `for="пароль"` — искать по точному тексту `'Пароль'`, не regex
- Файлы тестов сохранять только через `[System.IO.File]::WriteAllText` с UTF-8 без BOM

---

## Что осталось

### Этап 4: Интеграции
- VK OAuth (мобайл + веб)
- Firebase Cloud Messaging
- Публикация меню в VK
- Ссылки на доставку (Яндекс/СберМаркет/ВкусВилл)

### Этап 6: Продолжение
- Flutter тесты (>50%)
- Production: nginx + SSL + Яндекс.Облако/Selectel
- App Store / Google Play / RuStore
- CI/CD pipeline (добавить React тесты в .github/workflows/ci.yml)
