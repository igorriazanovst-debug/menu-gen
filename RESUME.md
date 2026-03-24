# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 2 — Flutter мобильное приложение ✅

---

## Все шаги Этапа 1 (бэкенд) выполнены ✅

---

## Этап 2 — Flutter мобильное приложение

### Структура проекта (`mobile/menugen_app/`)
```
lib/
├── main.dart                        # Точка входа, MultiBlocProvider
├── core/
│   ├── api/
│   │   ├── api_client.dart          # Dio + JWT interceptor + auto-refresh
│   │   ├── api_exception.dart       # Единый обработчик ошибок
│   │   └── token_storage.dart       # FlutterSecureStorage (зашифрованное хранение)
│   ├── db/
│   │   ├── app_database.dart        # Drift (SQLite) + все CRUD операции
│   │   └── tables.dart              # 5 таблиц + SyncQueue
│   ├── models/                      # Freezed-модели (User, Recipe, Menu, FridgeItem, DiaryEntry)
│   ├── router/app_router.dart       # GoRouter + redirect по AuthState
│   ├── theme/app_theme.dart         # Цветовая схема по ТЗ (томатный/авокадо/лимонный)
│   ├── connectivity/                # ConnectivityCubit (online/offline)
│   └── widgets/                     # MainShell (Tab Bar), ConnectivityBanner
└── features/
    ├── auth/     (BLoC + LoginScreen)
    ├── menu/     (BLoC + MenuScreen + MenuDayCard + GenerateMenuBottomSheet)
    ├── recipes/  (BLoC + RecipesScreen с поиском)
    ├── fridge/   (BLoC + FridgeScreen)
    ├── diary/    (BLoC + DiaryScreen с выбором даты)
    └── profile/  (ProfileScreen)
```

### Ключевые решения
- **Offline-First**: Drift (SQLite) как первичное хранилище + SyncQueue
- **JWT auto-refresh**: в `_AuthInterceptor` при 401 автоматически обновляет токен
- **API_BASE_URL** задаётся через `--dart-define` (не хардкод)
- **Навигация**: GoRouter + ShellRoute + redirect по AuthState
- **Офлайн-баннер**: ConnectivityCubit + ConnectivityBanner в shell
- **Цвета**: строго по ТЗ — Primary #E63946, Secondary #588157, Accent #F4A261

### Зависимости (pubspec.yaml)
flutter_bloc, go_router, dio, drift + drift_flutter, flutter_secure_storage,
connectivity_plus, freezed, go_router, intl, cached_network_image, shimmer

### Тесты
- `test/auth_bloc_test.dart` — BLoC-тесты через bloc_test + mocktail

### CI
- `.github/workflows/flutter_ci.yml` — analyze + test при push в mobile/

---

## Следующий шаг

**Этап 2, шаг 2 — Drift миграции + code generation**

```bash
cd mobile/menugen_app
flutter pub run build_runner build --delete-conflicting-outputs
```

Затем:
- Реализовать SyncService (push локальных изменений → сервер)
- Экраны: Семья, Список покупок, Настройки
- VK OAuth экран

---

## Репозиторий
GitHub: (указать URL при пуше)
