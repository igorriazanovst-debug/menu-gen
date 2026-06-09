# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to marker-based commit tracking (`MG_*`).

## [Unreleased]

### Added

### Changed

### Fixed

- **Added** 2026-06-03 `MG_CHANGELOG001` — Introduce CHANGELOG.md + add_changelog.py helper — files: `CHANGELOG.md`, `scripts/add_changelog.py`

- **Added** 2026-06-03 `MG_SHOP001_shopping_app` — Shopping lists domain: multiple lists, edit, access levels, history, AI/CSV/menu import, export data — files: `backend/apps/shopping/models.py`, `backend/apps/shopping/views.py`, `backend/apps/shopping/serializers.py`, `backend/apps/shopping/services.py`, `backend/apps/shopping/permissions.py`, `backend/apps/shopping/urls.py`, `backend/apps/shopping/admin.py`, `config/settings.py`, `config/urls.py`

- **Added** 2026-06-03 `MG_SHOP002_shopping_web` — Web shopping lists page: CRUD, sources (empty/menu/fridge/AI/CSV), access mgmt, history, print/PDF — files: `web/menugen-web/src/api/shopping.ts`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `web/menugen-web/src/utils/printShoppingList.ts`, `web/menugen-web/src/types/index.ts`, `web/menugen-web/src/components/layout/Sidebar.tsx`, `web/menugen-web/src/App.tsx`

- **Added** 2026-06-03 `MG_SHOP003_shopping_mobile` — Mobile shopping lists: CRUD, sources, access mgmt, history, PDF print (printing pkg), bottom-nav tab — files: `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_create_sheet.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_access_sheet.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_history_view.dart`, `mobile/menugen_app/lib/core/router/app_router.dart`, `mobile/menugen_app/lib/core/widgets/main_shell.dart`, `mobile/menugen_app/pubspec.yaml`

- **Fixed** 2026-06-03 `MG_SHOP004_lint` — Lint fixes in apps/shopping (F401 unused import, E501 long lines), black/isort — files: `backend/apps/shopping/models.py`, `backend/apps/shopping/services.py`, `backend/apps/shopping/urls.py`

- **Fixed** 2026-06-04 `MG_RUBRIC003` — Resolve product field clash: legacy product_id renamed to legacy_product_id (db_column kept); FK product/category_fk on ShoppingListItem — files: `backend/apps/shopping/models.py`, `backend/apps/shopping/views.py`, `backend/apps/shopping/serializers.py`

- **Added** 2026-06-04 `MG_RUBRIC004` — Web: rubricator autocomplete on add-item (search + AI category suggest with override) — files: `web/menugen-web/src/api/shopping.ts`, `web/menugen-web/src/types/index.ts`, `web/menugen-web/src/pages/Shopping/ItemAutocomplete.tsx`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`

- **Added** 2026-06-04 `MG_RUBRIC006` — Shopping prices: Product.last_price, ShoppingListItem/PurchaseHistory price_per_unit, Family.currency; add-item qty/unit/price + last_price prefill; toggle bumps last_price; list & export totals — files: `backend/apps/fridge/models.py`, `backend/apps/family/models.py`, `backend/apps/family/serializers.py`, `backend/apps/shopping/models.py`, `backend/apps/shopping/serializers.py`, `backend/apps/shopping/views.py`

- **Added** 2026-06-04 `MG_SHOPMOB001` — Mobile shopping: rubricator autocomplete (search/qty/unit/price), category grouping, family currency + grand total, prices in print & history — files: `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_event.dart`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_add_item.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_history_view.dart`

- **Added** 2026-06-04 `MG_SHOPMOB002` — Mobile family: currency selector (head sets family currency via PATCH /family/) — files: `mobile/menugen_app/lib/features/family/bloc/family_bloc.dart`, `mobile/menugen_app/lib/features/family/screens/family_screen.dart`

- **Changed** 2026-06-04 `MG_PRINTWEB001` — Web print: render per-item prices, line totals, grand total and family currency — files: `web/menugen-web/src/types/index.ts`, `web/menugen-web/src/utils/printShoppingList.ts`

- **Changed** 2026-06-04 `MG_HISTWEB001` — Web purchase history: show price_per_unit with family currency — files: `web/menugen-web/src/types/index.ts`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`

- **Fixed** 2026-06-04 `MG_SHOPBUG_BE` — Backend: quantize shopping line_total and total_price to 2 decimal places — files: `backend/apps/shopping/serializers.py`, `backend/apps/shopping/views.py`

- **Fixed** 2026-06-04 `MG_SHOPBUG_MOB` — Mobile shopping: edit existing item, 2-dp money display, Cyrillic PDF font, list creation date — files: `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_event.dart`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_edit_item.dart`

- **Fixed** 2026-06-04 `MG_SHOPBUG_WEB` — Web print: 2-dp money formatting for line totals, prices, grand total — files: `web/menugen-web/src/utils/printShoppingList.ts`

- **Fixed** 2026-06-04 `MG_SHOPBUG_MOB_FIX1` — Mobile: add createdAt to ShoppingExportData (PDF header rendering) — files: `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`

- **Changed** 2026-06-04 `MG_SHOPBUG_EDITMODE` — Shopping list: global edit-mode (web+mobile): inline name/qty/unit/price, delete gated by edit mode — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_item_edit_row.dart`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`

- **Added** 2026-06-05 `MG_SHOPMOB_GROUP` — Mobile shopping detail: colored category zones with sort_order (parity with web ListDetail) — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`

- **Fixed** 2026-06-05 `MG_SHOPMOB_STRIKE` — Mobile shopping detail: line-through styling for purchased items (parity with web) — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`

- **Fixed** 2026-06-05 `MG_PUBLIC_BACKEND_URL` — Use BACKEND_PUBLIC_URL env var for absolute media URLs in API. Image URLs no longer depend on request Host, web and mobile now load images directly from backend regardless of frontend host. — files: `backend/apps/recipes/serializers.py`

- **Added** 2026-06-06 `MG_206` — Калькулятор КБЖУ (Web). 4 системы расчёта (Mifflin-St Jeor / Harris-Benedict / Роспотребнадзор / EFSA) + custom (граммы или % + дельта от TDEE). 3 пресета диет: сбалансированный (20/30/50), высокобелковый (35/25/40), низкоуглеводный (30/45/25). Кнопка на странице профиля → POST /users/me/calculator/{preview,apply}/. Дисклеймер про справочный характер. Прежний flow (заполнение в Django Admin) заменён. — files: `backend/apps/users/calculator.py`, `backend/apps/users/serializers.py`, `backend/apps/users/views.py`, `backend/apps/users/urls/users.py`, `web/menugen-web/src/types/index.ts`, `web/menugen-web/src/api/users.ts`, `web/menugen-web/src/App.tsx`, `web/menugen-web/src/pages/Profile/ProfilePage.tsx`, `web/menugen-web/src/pages/Profile/KBJUCalculatorPage.tsx`

- **Added** 2026-06-06 `MG_207` — Калькулятор КБЖУ (Mobile/Flutter). Порт web MG_206: 4 системы (Mifflin/Harris-Benedict/Роспотребнадзор/EFSA) + custom (граммы или % + дельта). 3 пресета диет. Кнопка на экране профиля → POST /users/me/calculator/{preview,apply}/. Дисклеймер про справочный характер. — files: `mobile/menugen_app/lib/features/profile/screens/kbju_calculator_screen.dart`, `mobile/menugen_app/lib/features/profile/screens/profile_screen.dart`, `mobile/menugen_app/lib/core/router/app_router.dart`

- **Added** 2026-06-06 `MG_SHAREACCEPT` — Общие списки покупок требуют принятия получателем: раздел «Ожидают» (pending/accept/reject), внешний доступ выдаётся как pending, до принятия — только просмотр — files: `backend/apps/shopping/models.py`, `backend/apps/shopping/permissions.py`, `backend/apps/shopping/serializers.py`, `backend/apps/shopping/views.py`, `backend/apps/shopping/urls.py`, `backend/apps/shopping/migrations/0005_shoppinglistaccess_status.py`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `web/menugen-web/src/api/shopping.ts`, `web/menugen-web/src/types/index.ts`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`

- **Fixed** 2026-06-06 `MG_TOKENFIX` — Mobile: при ротации refresh-токена сохраняется новый refresh + single-flight refresh — устранены ложные «токен просрочен, войдите заново» — files: `mobile/menugen_app/lib/core/api/dio_api_client.dart`

- **Changed** 2026-06-09 `MG_208` — Минимальная длина пароля снижена с 8 до 5 символов (web + backend) — files: `web/menugen-web/src/pages/Auth/LoginPage.tsx`, `web/menugen-web/src/pages/Auth/LoginPage.test.tsx`, `backend/apps/users/serializers.py`, `backend/config/settings.py`

<!-- CHANGELOG_AUTO_ANCHOR — new entries inserted above this line by add_changelog.py -->
