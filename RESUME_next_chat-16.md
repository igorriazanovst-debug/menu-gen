# MenuGen — резюме чата #15 → следующий чат #16

## Статус по бэклогу

### ✅ Закрыто в этом чате
- **MG-205-UI** — UI бейдж источника правок КБЖУ (auto / вручную / специалист) + dropdown с историей + кнопка «Сбросить к авто». Web (React) + Mobile (Flutter), переиспользуемый компонент `TargetField`.

### ✅ Закрыто ранее (контекст)
- **MG-101…104** — структура данных рецептов (food_group, suitable_for, protein_type, grain_type, is_fatty_fish, is_red_meat) + автоклассификатор.
- **MG-201…203** — Profile: targets КБЖУ + meal_plan_type, авторасчёт Mifflin-St Jeor, API.
- **MG-204** — Frontend (web + mobile): показ targets + meal_plan toggle в Profile + Family.
- **MG-205** — Backend: ProfileTargetAudit, отслеживание источника, lock авторасчёта, reset force=True, тесты (8/8).

## MG-205-UI — что сделано

### Backend (`apps/users` + `apps/family`)
- `users/serializers.py`:
  - `ProfileTargetAuditSerializer` — поля `id, field, source, old_value, new_value, reason, at, by_user{id,name}|null`
  - `ProfileSerializer.targets_meta` (SerializerMethodField) — для каждого из 5 target-полей: `{source, by_user, at}`. Берётся последняя запись `ProfileTargetAudit`.
  - константа `TARGET_FIELDS_MG205UI`
- `family/serializers.py`: read-only `ProfileSerializer.targets_meta` (тот же формат).
- `users/views.py`:
  - `TargetHistoryView` — `GET /api/v1/users/me/targets/{field}/history/` → `[TargetAuditEntry, ...]` (до 100 записей, order=-at)
  - `TargetResetView` — `POST /api/v1/users/me/targets/{field}/reset/` → пересчёт по `calculate_targets()`, запись аудита `source='auto', by_user=request.user`, возврат `UserMeSerializer`
  - валидация имени поля (400 + JSON со списком допустимых)
- `family/views.py`:
  - `FamilyMemberTargetHistoryView`, `FamilyMemberTargetResetView` (аналог для члена семьи)
  - права: head | self | verified specialist с активным `SpecialistAssignment`
- `users/urls/users.py`, `family/urls.py` — новые маршруты.

**Маркеры:** `MG_205UI_V_serializers`, `MG_205UI_V_views`, `MG_205UI_V_urls`, `MG_205UI_V_family_ser`, `MG_205UI_V_family_views`, `MG_205UI_V_family_urls`.

### Web (`web/menugen-web`)
- `types/index.ts`: `TargetSource`, `TargetMeta`, `TargetsMeta`, `TargetField` (literal union), `TargetAuditEntry`. В `UserProfile` добавлено `targets_meta?: TargetsMeta`.
- `api/users.ts` (новый): `usersApi.getTargetHistory`, `usersApi.resetTarget`.
- `api/family.ts`: `familyApi.getMemberTargetHistory`, `familyApi.resetMemberTarget`.
- `components/profile/TargetField.tsx` (новый) — пилюля КБЖУ с бейджем источника, popover с историей и кнопкой reset. Принимает `TargetLoader` (контракт `getHistory + reset`), что позволяет переиспользовать в Profile и Family.
- `pages/Profile/ProfilePage.tsx` — переписан с `MacroPill` на `TargetField` × 5; loader = `MeTargetLoader` (через `usersApi`).
- `components/family/FamilyMemberEditModal.tsx` — переписан, loader = переход через `familyApi`.

**Маркеры:** `MG_205UI_V_types`, `MG_205UI_V_api_users`, `MG_205UI_V_api_family`, `MG_205UI_V_target_field`, `MG_205UI_V_profile_page`, `MG_205UI_V_family_modal`.

**Verify:** `tsc --noEmit` exit=0, `eslint` exit=0.

### Mobile (`mobile/menugen_app`)
- `lib/core/widgets/target_field.dart` (новый) — `TargetField` (виджет) + `TargetFieldsRow` (готовый ряд из 5 пилюль) + `TargetSource`/`TargetSourceMeta` + `TargetLoader` (abstract) + 2 реализации: `MeTargetLoader`, `FamilyMemberTargetLoader`. Bottom sheet с историей и reset.
- `lib/features/profile/screens/profile_screen.dart`: вместо `MacroPillsRow` теперь `TargetFieldsRow(loader: MeTargetLoader(apiClient: widget.apiClient, onChanged: _load))`.
- `lib/features/family/screens/family_screen.dart`: в `_EditMemberSheet` `MacroPillsRow` → `TargetFieldsRow` с `FamilyMemberTargetLoader`, использующим `context.read<FamilyBloc>().apiClient`.

**Маркеры:** `MG_205UI_V_target_field`, `MG_205UI_V_profile`, `MG_205UI_V_family`.

**Verify:** flutter SDK на сервере не установлен — `flutter analyze` пропущен. Проверится при сборке мобилки в CI.

### Smoke (DRF APIClient внутри backend контейнера)
1. `GET /users/me/` → 200, `profile.targets_meta` присутствует со всеми 5 полями
2. `GET /users/me/targets/protein_target_g/history/` → массив записей с `auto`
3. `PATCH /users/me/` с `protein_target_g="180.0"` → meta перешла в `source=user, by_user={id, name}`
4. `POST /users/me/targets/protein_target_g/reset/` → значение пересчитано (112.5), `source=auto`
5. Bad field → 400, `{"field": "Допустимые значения: [...]"}`
6. Все 8 pytest-тестов `test_mg_205.py` прошли

## Что в бэклоге следующее

Согласно `MenuGen_Backlog.xlsx` (файл лежит в проекте):

### Спринт 3 (P0) — переписывание генератора меню
- **MG-301** — Метод тарелки в `MenuGenerator`: основной приём = `grain + protein + vegetable`, перекус = 1 компонент. В `MenuItem` добавить `component_role`. Миграция. **(зависит от MG-101, MG-104)** — оба ✅.
- **MG-302** — Недельные ограничения: red_meat ≤ 3/нед, fatty_fish ≥ 2/нед, plant_protein ежедневно.
- **MG-303** (P1) — Распределение калорий: завтрак 30 / обед 35 / ужин 25 / перекусы 5(+5).
- **MG-304** (P1) — ≥ 5 порций овощей/фруктов в день.

### Спринт 4 (P0/P1) — UI меню под новую структуру
- **MG-401** — отображение приёма пищи как карточки с 3 компонентами.
- **MG-402** (P1) — замена рецепта с фильтрацией по `food_group`.
- **MG-403** (P1) — `DayNutritionSummary` (прогресс-бары КБЖУ за день).

### Спринт 5 (P2) — дополнительные правила
- MG-501 (поля cooking_method, has_added_sugar, oil_tsp), MG-502 (≤5 ч.л. масла/день), MG-503 (нет сахара в основных), MG-504/505 (cheat-meal).

### Спринт 6 (P1)
- **MG-601** — pytest на все правила генератора меню.

## Архитектура (краткая шпаргалка)

### Backend stack
- Django 4.x + DRF, JWT (`djangorestframework-simplejwt`), drf-spectacular для OpenAPI.
- PostgreSQL, Redis, Celery, Celery-beat.
- Структура: `backend/apps/{users,recipes,family,fridge,menu,diary,specialists,subscriptions,payments,notifications,social,sync}`.
- API base: `/api/v1/...`.
- Запуск: `docker compose -f /opt/menugen/docker-compose.yml ...`.

### Web stack
- React 18 + TypeScript, axios, Redux Toolkit, Tailwind (кастомные цвета `tomato`, `chocolate`, `avocado`, `rice`).
- Корень: `/opt/menugen/web/menugen-web`.

### Mobile stack
- Flutter, flutter_bloc, dio, equatable, go_router.
- Корень: `/opt/menugen/mobile/menugen_app`.
- API client: `core/api/dio_api_client.dart` (реализует `ApiClient`).
- AppColors в `core/theme/app_theme.dart`.

### MG-205 модель данных (для справки)
- `users_profile`: 5 полей `*_target*` (calorie + 4 макроса).
- `profile_target_audit`: история, индекс `(profile, field, -at)`. Источник = последний `source`.
- `apps/users/audit.py`: `record_target_change`, `get_field_source`, `is_locked`. Дублирование в общий `apps.sync.AuditLog` (best-effort).
- `apps/users/nutrition.py`: `fill_profile_targets(profile, force=False, actor=None)` — НЕ перетирает `user`/`specialist` без force; пишет аудит.

## Правила взаимодействия (не забывать)
- Диалог на русском.
- При начале нового чата сначала читать резюме, затем файлы проекта (`/mnt/project/`).
- Не объяснять, не извиняться — только код.
- Никогда не хардкодить URL/токены/пароли.
- Всё через скрипты в `/opt/menugen/{backend,web,mobile}/scripts/` + `chmod +x` + запуск.
- Скрипты идемпотентны (маркеры `MG_*_V_*` или `MG_205UI_V_*`).
- Бэкапы в `/opt/menugen/backups/*_${TS}*`. БД-бэкап перед apply.
- Резюме нового чата делать файлом.

## Ключевые пути

```
/opt/menugen/                                  — корень проекта (git)
├── backend/                                   — Django
│   ├── apps/users/                            — Profile, ProfileTargetAudit
│   ├── apps/family/                           — Family + FamilyMember
│   ├── apps/specialists/                      — Specialist + SpecialistAssignment
│   └── scripts/                               — apply/diagnose/smoke скрипты
├── web/menugen-web/                           — React
│   ├── src/api/{users,family,client,...}.ts
│   ├── src/components/profile/TargetField.tsx — MG-205-UI
│   ├── src/components/family/FamilyMemberEditModal.tsx
│   └── src/pages/Profile/ProfilePage.tsx
├── mobile/menugen_app/                        — Flutter
│   └── lib/
│       ├── core/widgets/target_field.dart     — MG-205-UI
│       ├── features/profile/screens/
│       └── features/family/{bloc,screens,...}/
└── backups/                                   — все .bak файлы и pg_dump
```

## Команды для следующего чата
```bash
# Старт следующей задачи (MG-301 — генератор меню):
ls -la /opt/menugen/backend/apps/menu/
cat /opt/menugen/backend/apps/menu/generator.py | head -100
docker compose -f /opt/menugen/docker-compose.yml exec -T backend pytest apps/menu/ -v 2>&1 | tail -30
```
