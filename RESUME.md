# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 2 — Flutter: code gen + SyncService + Семья + Покупки ✅

---

## Этап 1 (бэкенд) — ЗАВЕРШЁН ✅
## Этап 2 (Flutter) — В РАБОТЕ

### Шаг 1: Архитектура, BLoC, экраны ✅
### Шаг 2: Code gen + SyncService + Семья + Покупки ✅

---

## Структура Flutter (`mobile/menugen_app/`) — 58 файлов

```
lib/
├── main.dart                   # + SyncService.start()
├── core/
│   ├── api/                    # ApiClient (Dio + JWT interceptor), TokenStorage
│   ├── db/                     # AppDatabase (Drift), tables.dart, app_database.g.dart (stub)
│   ├── models/                 # 5 Freezed-моделей + .g.dart + .freezed.dart (написаны вручную)
│   ├── router/app_router.dart  # + /family + /shopping/:menuId маршруты
│   ├── sync/sync_service.dart  # SyncService (push + pull + enqueue)
│   ├── connectivity/           # ConnectivityCubit
│   └── widgets/                # MainShell, ConnectivityBanner
└── features/
    ├── auth/     BLoC + LoginScreen
    ├── menu/     BLoC + MenuScreen + DayCard + GenerateSheet
    ├── recipes/  BLoC + RecipesScreen (поиск)
    ├── fridge/   BLoC + FridgeScreen (add/delete/expiry)
    ├── diary/    BLoC + DiaryScreen (выбор даты)
    ├── family/   BLoC + FamilyScreen (список, приглашение, удаление)
    ├── shopping/ ShoppingListScreen (группировка, progress bar, share)
    └── profile/  ProfileScreen (→ /family, logout)
```

### SyncService (`core/sync/sync_service.dart`)
- `start()` — подписка на connectivity, auto-sync при восстановлении сети
- `_push()` — отправляет SyncQueue pending-записи на сервер
- `_pull()` — загружает fridge + menus + recipes в локальную Drift БД
- `enqueue()` — добавляет изменение в очередь (оффлайн-сценарий)
- Конфликты: Last Write Wins (User vs User), специалист имеет приоритет

### Экраны семьи
- Список участников с ролями (глава/участник)
- Приглашение по email
- Удаление с confirm-диалогом
- Проверка лимита тарифа (403 → toast)

### Экран списка покупок
- Группировка по категориям
- Progress bar «куплено X/Y»
- Checkbox → PATCH toggle к API
- Share → текстовый формат для копирования / отправки

### Code generation
Так как Flutter недоступен в контейнере, `.g.dart` и `.freezed.dart`
написаны вручную. При наличии Flutter:
```bash
cd mobile/menugen_app
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

---

## Следующий шаг

**Этап 3 — React веб-приложение**

Начать с:
1. `npx create-react-app menugen-web --template typescript`
2. Redux Toolkit + RTK Query
3. Экраны: Dashboard, Каталог рецептов, Редактор меню, Профиль и Семья

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек
- **Backend:** Python 3.11 + Django 4.2 + DRF (✅ завершён)
- **Mobile:** Flutter 3.x + BLoC + Drift + Dio
- **Web:** React 18 + TypeScript (следующий этап)
