# MenuGen — Резюме для нового чата

**Проект:** Генератор меню (MenuGen)
**Дата:** Март 2026
**Репозиторий:** https://github.com/igorriazanovst-debug/menu-gen

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

### Сервисы
| Сервис | URL |
|---|---|
| Swagger | http://localhost:8000/api/v1/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| React web | http://localhost:3000 |

---

## Этап 1: Бэкенд — ✅

**Стек:** Python 3.11, Django 4.2, DRF, JWT, PostgreSQL 15, Redis 7, Celery
**Файлов:** 155 Python, 92 теста, 0 ошибок `manage.py check`

---

## Этап 2: Flutter мобильное приложение — ✅

**Стек:** Flutter 3.22, Dart, BLoC, Drift, flutter_secure_storage, go_router, dio

### Важные особенности
- `lib/` был в `.gitignore` (Python-правило) — исправлено добавлением `!mobile/menugen_app/lib/`
- `.freezed.dart` и `.g.dart` файлы были с битыми `_\$` (экранирование Windows Git) — удалены, модели переписаны как plain Dart классы
- `AppDatabase` — абстрактный интерфейс (`abstract class AppDatabase { Future<void> close(); }`) для мокирования в тестах
- `ApiClient` — абстрактный интерфейс с `Future<dynamic>` (не `Future<Response<dynamic>>`) — иначе моки в тестах не работают
- Bloc-файлы НЕ используют `ApiException.fromDio` — только `e.toString()`
- `_data(dynamic r)` хелпер в каждом bloc: `try { return r.data; } catch (_) { return r; }` — для совместимости с MockResponse в тестах

### Расположение файлов
```
lib/core/api/api_client.dart      — абстрактный ApiClient (Future<dynamic>)
lib/core/api/token_storage.dart   — абстрактный TokenStorage
lib/core/api/api_exception.dart   — простой ApiException (без .fromDio)
lib/core/db/app_database.dart     — абстрактный AppDatabase
lib/core/models/                  — plain Dart классы (без freezed/json_serializable)
lib/features/auth/bloc/           — auth_bloc.dart (event+state+bloc в одном файле)
lib/features/family/bloc/         — family_bloc.dart
lib/features/fridge/bloc/         — fridge_bloc.dart
lib/features/menu/bloc/           — menu_bloc.dart
lib/features/diary/bloc/          — diary_bloc.dart
lib/features/recipes/bloc/        — recipes_bloc.dart
```

### Flutter CI — ✅ (CI #18, commit 226fc05)
```
.github/workflows/flutter_ci.yml
```

### Важно для PowerShell скриптов
- Всегда использовать абсолютный путь: `$r = "C:\Temp\2026\menu-gen\menu-gen\mobile\menugen_app\lib"`
- Запись файлов: `[IO.File]::WriteAllText("$r\path\file.dart", $content, [Text.UTF8Encoding]::new($false))`
- После записи: `git add -f mobile/menugen_app/lib` (нужен `-f` из-за `.gitignore`)

---

## Этап 3: React веб-приложение — ✅

**Стек:** React 18 + TypeScript, Redux Toolkit, React Router v6, Axios, RHF + Zod, Tailwind CSS v3

### Важные особенности
- Tailwind **v3** (не v4!) — иначе ломается PostCSS
- Хуки: `src/hooks/useAppDispatch.ts`
- HTTP-клиент: `src/api/client.ts`
- `menu.items`, `recipe.ingredients`, `recipe.steps`, `recipe.categories` — везде `?? []`

---

## Этап 5: Кабинет специалиста — ✅

Бэкенд: `backend/apps/specialists/`
React: `src/store/specialistSlice.ts` + `src/pages/specialist/` (5 страниц)
Маршруты: `/specialist`, `/specialist/register`, `/specialist/clients/:familyId`, и др.

---

## Этап 6: Тесты — 🔄

### React Jest тесты — ✅ (47/47)
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
**ВАЖНО:** секцию `jest` в package.json писать только через `[System.IO.File]::WriteAllText`

### Flutter тесты — ✅ CI зелёный (Flutter CI #18)
Тесты: auth, family, fridge, menu, diary, recipes bloc tests

### Что осталось
- Flutter тесты покрытие >50% (добавить больше тестов)
- Production: nginx + SSL + Яндекс.Облако/Selectel
- App Store / Google Play / RuStore
- Этап 4: VK OAuth, Firebase Cloud Messaging, доставка
