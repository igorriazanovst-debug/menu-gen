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

<!-- CHANGELOG_AUTO_ANCHOR — new entries inserted above this line by add_changelog.py -->
