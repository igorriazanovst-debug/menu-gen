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

<!-- CHANGELOG_AUTO_ANCHOR — new entries inserted above this line by add_changelog.py -->
