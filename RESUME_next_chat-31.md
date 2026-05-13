# RESUME — chat 31 → chat 32

**Дата:** 2026-05-13
**Ветка:** `main`
**HEAD:** `a046cf0` — `fix(mobile): CI failures on 59ee4de`
**Предыдущий коммит:** `59ee4de` — `MG-204 mobile: diary plan/fact + import-from-menu + stats; MG-606 premium gate`

---

## Статус CI на HEAD `a046cf0`

| Workflow | Run # | Status |
|---|---|---|
| Flutter CI | #27 | ✅ **success** |
| CI (backend lint) | #86 | ❌ failure — **pre-existing** flake8 tech debt, не связано с MG-204 |

Backend CI падает на flake8 ещё с #84 (`ad9453f`, до нашего патча) — это не регрессия чата 31.

---

## Что сделано в чате 31 (MG-204 mobile + MG-606 mobile)

### MG-204-D (diary, follows backend MG-605.B/C/D)

**Новые файлы:**
- `lib/features/diary/models/diary_entry.dart` — `DiaryEntry`, `MealType` enum (plain Dart, без freezed)
- `lib/features/diary/models/diary_stats.dart` — `DiaryDayStats`, `NutritionBucket`
- `lib/features/diary/widgets/diary_stats_card.dart` — карточка КБЖУ план/факт

**Переписано:**
- `lib/features/diary/bloc/diary_bloc.dart` — конвертирован в `part of` layout
  - События: `DiaryLoadRequested(date, memberId?)`, `DiaryMarkEatenRequested(entryId, isEaten)`, `DiaryAddManualRequested`, `DiaryDeleteRequested`, `DiaryImportFromMenuRequested(menuId, date, memberId?)`
  - Состояния: `DiaryInitial`, `DiaryLoading`, `DiaryLoaded(date, memberId, entries, stats)`, `DiaryPremiumLocked(message, isWrite)`, `DiaryError`
  - `DiaryLoaded.plannedEntries` / `manualEntries` — разделение «План» vs «Факт»
- `lib/features/diary/screens/diary_screen.dart` — секции План/Факт, чекбокс is_eaten, swipe-delete, stats card, диалог импорта меню

**Соответствие backend-контракту:**
- `GET /api/v1/diary/?date=&member_id=` — paginated `{count, results}`
- `PATCH /api/v1/diary/{id}/` body `{is_eaten: bool}` — toggle факта
- `POST /api/v1/diary/` body `{date, meal_type, recipe?, custom_name?, nutrition?, quantity, is_eaten: true}` — manual
- `DELETE /api/v1/diary/{id}/`
- `POST /api/v1/diary/import-from-menu/?menu_id=&date=&member_id=` — параметры в query-string, не в body
- `GET /api/v1/diary/stats/?from=&to=&member_id=` — **plain array** (не paginated), `[{date, planned, actual, total}]`, bucket shape `{calories, proteins, fats, carbs}` (float)

### MG-204-P (premium gate, follows backend MG-606.A/B/C)

**Новое:**
- `lib/core/api/api_exception.dart` — типизированное `ApiException(statusCode, errorCode?, message, body?)`, getters `isPremiumLocked` (==403), `isUnauthorized`, `isNotFound`, `isServerError`, `isNetwork`
- `lib/core/premium/premium_gate_cubit.dart` — `PremiumGateCubit` + `PremiumGateState{status, lastLockedFeature, lastLockMessage}`, `PremiumStatus{unknown, lockedForRead, lockedForWrite}`. Подписывается на `DioApiClient.errorStream` + принимает явные `reportLock(feature, isWrite)` / `reportReadSuccess()` / `reset()`
- `lib/core/premium/paywall_banner.dart` — банер над content в `MainShell`, показывается только при locked
- `lib/core/premium/paywall_screen.dart` — заглушка `/paywall` (реальный flow — MG-payments)

**Изменено:**
- `lib/core/api/dio_api_client.dart` — бросает `ApiException` на non-2xx, парсит DRF `{detail, error_code?}`, broadcast в `errorStream<ApiException>`. 401-refresh logic сохранена.
- `MenuBloc`, `DiaryBloc`, `FridgeBloc` — `*PremiumLocked(message, isWrite)` state + report в `PremiumGateCubit`
- `MainShell` — встроен `PaywallBanner` над content
- `AppRouter` — добавлен `/paywall`

### Q1 cleanup (раздвоенные event/state файлы)

- `diary_bloc.dart` + `diary_event.dart` + `diary_state.dart` → конвертировано в `part of` layout
- `menu_bloc.dart` + `menu_event.dart` + `menu_state.dart` → конвертировано в `part of` layout; убрана несуществующая ссылка на `Menu` тип в state, исправлен type-mismatch `List<Menu>` vs `List<Map<String,dynamic>>`

### Тесты

- `test/api_exception_test.dart` — классификация статус-кодов (premium/network/server/unauthorized)
- `test/premium_gate_cubit_test.dart` — wiring со stream, `reportLock`, `reportReadSuccess`, `reset`
- `test/diary_bloc_test.dart` — load → Loaded с парсингом; 403 → PremiumLocked; generic → Error; markEaten → patches `/diary/{id}/`
- `test/menu_bloc_test.dart` — 403 read → PremiumLocked(isWrite=false); 403 generate → PremiumLocked(isWrite=true)
- `test/fridge_bloc_test.dart` — 403 → FridgePremiumLocked
- `test/widget_test.dart` — заменён pre-existing сломанный шаблон (`MyApp` не существует) на trivial smoke
- `test/family_bloc_test.dart` — исправлен pre-existing positional→named arg на `FamilyInviteMemberRequested`

---

## Out of scope чата 31 (явно отложено)

### 1. Drift offline cache (CachedDiaryEntries и др.)

`AppDatabase` пока stub из 2 строк, `tables.dart` определён, но не подключён. Реальная wiring drift — отдельный тикет:
- `@DriftDatabase` declaration с генерируемым кодом (`*.g.dart` через `build_runner`)
- DAO-слой для всех cached-таблиц (recipes, menus, fridge, diary, shopping)
- Write-through pattern в каждом bloc
- Conflict-resolution rules
- `SyncQueue` execution в `SyncService` (сейчас `start()`/`sync()` — no-op)

Решение чата 31: схема `CachedDiaryEntries` оставлена как есть для будущей wiring. Diary network-only.

### 2. Notifications mobile feature

`apps/notifications/` на бэке есть и закрыт MG-606 gate'ом. На мобиле фичи нет вообще:
- Push tokens
- FCM setup (Firebase project, `google-services.json`)
- AndroidManifest permissions (POST_NOTIFICATIONS на API 33+)
- Notification channels
- Background handlers
- BLoC + screen

Отдельный тикет (MG-notifications-mobile).

### 3. Premium статус на профиле

Backend не отдаёт `is_premium` / `premium_until` в `/users/me/`. Premium вычисляется server-side через `Subscription` table при каждом запросе. Мобила сейчас узнаёт о premium **только реактивно** — через 403.

Опции для отдельного тикета:
- Добавить derived `subscription_status: {plan, expires_at, has_history}` в `UserMeSerializer`
- Либо новый endpoint `GET /api/v1/subscriptions/my/` (он, возможно, уже есть — нужно проверить `apps/subscriptions/urls.py`)
- На основе этого — proactive `PremiumGateCubit.bootstrap(meResponse)` при старте, badge на профиле, скрытие paywall banner у активных подписчиков

### 4. Real paywall flow

`PaywallScreen` сейчас — заглушка с TODO. Реальный flow (выбор плана, оплата через `apps/payments/`) — это MG-payments-mobile.

### 5. Backend flake8 tech debt

CI #86 (и #84, #83, …, до самого `0317e18`) падает на flake8. Затронуто примерно:
- `fix_tests.py`, `fix_views.py` — служебные скрипты в корне
- `scripts/classify_recipes.py`, `scripts/mg_*.py`, `scripts/scrape_povar.py`, `scripts/nutritionist_agent.py`
- `apps/recipes/views.py`, `apps/recipes/tests/test_mg_501.py`
- `apps/users/audit.py`, `apps/users/nutrition.py`, `apps/users/serializers.py`, `apps/users/signals.py`, `apps/users/views.py`, `apps/users/tests/test_mg_205.py`, `apps/users/urls/users.py`
- `apps/specialists/views.py`
- `apps/subscriptions/tests/test_mg_606a_premium_helpers.py`

Типичные нарушения: E241, E221, E272, E303, E305, E302, E501, E701, E702, E722, E231, F401, F541, F841, W292.

Рекомендация для отдельного тикета: `autopep8 --in-place --aggressive --max-line-length 120 -r apps/ scripts/ fix_*.py` + ручная правка `F401`/`F841`/`F541` (autopep8 не убирает unused imports / vars).

---

## Что брать в чат 32 (приоритеты)

Из «out of scope» — порядок по полезности:

1. **#3 (Premium статус на профиле)** — даёт proactive UX: пользователь видит «Premium до 2026-12-01» в профиле и не натыкается на 403 неожиданно. Маленький бэкенд-патч + маленький фронт-патч.
2. **#5 (flake8 cleanup)** — снимает красный CI на бэке, разблокирует адекватные status-checks в PR.
3. **#1 (drift wiring)** — улучшает offline UX, но это большой объём; лучше после стабилизации фичей.
4. **#4 (real paywall)** — нужен реальный платёжный провайдер; разговор про MG-payments в целом.
5. **#2 (notifications mobile)** — нужен Firebase setup.

---

## Полезные команды для следующего чата

```bash
# Запуск Flutter-тестов локально (если ставить flutter):
cd /opt/menugen/mobile/menugen_app
flutter pub get
flutter test

# Backend-тесты:
cd /opt/menugen/backend
python -m pytest apps/diary/tests/ -v

# CI watcher (после установки GITHUB_TOKEN):
bash /opt/menugen/backend/scripts/list_and_fetch_ci.sh
bash /opt/menugen/backend/scripts/list_and_fetch_ci.sh fetch  # + логи failed runs

# Бэкапы патчей чата 31:
ls -la /opt/menugen/mobile/menugen_app/.bak-*
```

---

## Структура файлов после чата 31

```
mobile/menugen_app/lib/
├── core/
│   ├── api/
│   │   ├── api_client.dart              (interface, без изменений)
│   │   ├── api_exception.dart           ★ NEW: typed exception
│   │   ├── dio_api_client.dart          ✎ throws ApiException + errorStream
│   │   └── token_storage.dart           (без изменений)
│   ├── connectivity/                    (без изменений)
│   ├── db/                              (без изменений — drift не подключён)
│   ├── premium/                         ★ NEW DIR
│   │   ├── paywall_banner.dart
│   │   ├── paywall_screen.dart
│   │   └── premium_gate_cubit.dart
│   ├── router/
│   │   └── app_router.dart              ✎ + /paywall
│   ├── sync/                            (stub, без изменений)
│   ├── theme/                           (без изменений)
│   └── widgets/
│       └── main_shell.dart              ✎ + PaywallBanner
├── features/
│   ├── auth/                            (без изменений)
│   ├── diary/
│   │   ├── bloc/
│   │   │   ├── diary_bloc.dart          ✎ part-of layout, full rewrite
│   │   │   ├── diary_event.dart         ✎ part-of
│   │   │   └── diary_state.dart         ✎ part-of, + DiaryPremiumLocked
│   │   ├── models/                      ★ NEW DIR
│   │   │   ├── diary_entry.dart
│   │   │   └── diary_stats.dart
│   │   ├── screens/
│   │   │   └── diary_screen.dart        ✎ full rewrite
│   │   └── widgets/                     ★ NEW DIR
│   │       └── diary_stats_card.dart
│   ├── family/                          (без изменений)
│   ├── fridge/
│   │   └── bloc/
│   │       └── fridge_bloc.dart         ✎ + FridgePremiumLocked, event API сохранён
│   ├── menu/
│   │   └── bloc/
│   │       ├── menu_bloc.dart           ✎ part-of layout, + MenuPremiumLocked
│   │       ├── menu_event.dart          ✎ part-of
│   │       └── menu_state.dart          ✎ part-of, исправлен type-mismatch
│   ├── profile/                         (без изменений)
│   ├── recipes/                         (без изменений)
│   └── shopping/                        (без изменений)
└── main.dart                            ✎ + PremiumGateCubit wiring
```

★ = new file/dir, ✎ = modified, иначе без изменений.

---

## Backup directories

В случае нужды откатиться:
- `/opt/menugen/mobile/menugen_app/.bak-20260513-170735/` — состояние перед основным патчем (commit `59ee4de`)
- `/opt/menugen/mobile/menugen_app/.bak-20260513-184525/` — состояние перед CI-fix патчем (commit `a046cf0`)

Каждая папка содержит точные копии файлов в их relative-paths (например `lib/features/diary/bloc/diary_bloc.dart` → `.bak-.../lib/features/diary/bloc/diary_bloc.dart`).
