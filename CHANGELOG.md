# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to marker-based commit tracking (`MG_*`).

## [Unreleased]

### Added

### Changed

- **Changed** 2026-06-11 `MG_MENULABEL` — Пикер меню в создании списка покупок (из меню / меню-холодильник): лейбл «{имя создателя} DD.MM–DD.MM» вместо #id; MenuListSerializer отдаёт creator_name — files: `backend/apps/menu/serializers.py`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `web/menugen-web/src/types/index.ts`, `mobile/menugen_app/lib/features/shopping/screens/shopping_create_sheet.dart`

### Fixed

- **Fixed** 2026-06-12 `MG_B03` — Редактирование продуктов холодильника (backend+web+mobile). Backend: `FridgeItemWriteSerializer.update()` — зеркало `create()`, пере-резолв `Product` по `category_slug` при `PATCH /fridge/{id}/` (категория живёт на `product.category_fk`). Web: `fridgeApi.update`, `EditFridgeItemModal`, кнопка ✎ в карточке `FridgePage`. Mobile: `edit_fridge_item_sheet.dart`, ✎ в AppBar экрана деталей, reload списка по возврату (`fridge_screen` onTap → `FridgeLoadRequested`). Caveat: смена категории через `_resolve_product` может переписать `category_fk` общего `Product` (паритет с add). — files: `backend/apps/fridge/serializers.py`, `web/menugen-web/src/api/fridge.ts`, `web/menugen-web/src/pages/Fridge/FridgePage.tsx`, `web/menugen-web/src/components/fridge/EditFridgeItemModal.tsx`, `mobile/menugen_app/lib/features/fridge/screens/edit_fridge_item_sheet.dart`, `mobile/menugen_app/lib/features/fridge/screens/fridge_item_detail_screen.dart`, `mobile/menugen_app/lib/features/fridge/screens/fridge_screen.dart`

- **Fixed** 2026-06-12 `MG_B08` — Mobile: add-bar добавления товара недоступен в edit-mode детализации списка (реплика web B-07). Гейт `caps.manage && !_editMode` → `caps.manage` (список и так скроллится в `Expanded>ListView`, «Готово» = check в AppBar). — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`

- **Fixed** 2026-06-12 `MG_B11` — Mobile: toggle «покупка» сбрасывал скролл списка наверх. `_onToggle` обновляет item in-place (`copyWith`) и эмитит `ShoppingDetailLoaded` без промежуточного `ShoppingLoading` (полный re-fetch уничтожал ListView). Добавлены `copyWith` в `ShoppingItem`/`ShoppingListDetail`. — files: `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/models/shopping_models.dart`

- **Fixed** 2026-06-12 `MG_B10` — Mobile: после создания списка экран пуст до переключения вкладок. `_onCreate` теперь `_reloadLists` активных списков вместо `ShoppingDetailLoaded`; `_openCreate` убрал дублирующий `ShoppingListsRequested` (гонка stale-GET, перетиравшая результат create). — files: `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`

- **Fixed** 2026-06-11 `MG_B09` — Пикер меню в создании списка покупок: лейбл «{creator_name} DD.MM–DD.MM» реально заработал (web и mobile читали несуществующий `m.title`/`m['title']`, а backend `MenuListSerializer` не отдавал `creator_name` — правка MG_MENULABEL по факту не была подключена). Добавлен `creator_name` в сериализатор (`creator_id`→`User.name`); web `<option>` и mobile `_menuLabel` строят имя+даты (ISO через slice/substring, TZ-safe, fallback «Меню #id»). Восстанавливает B-06. — files: `backend/apps/menu/serializers.py`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `web/menugen-web/src/types/index.ts`, `mobile/menugen_app/lib/features/shopping/screens/shopping_create_sheet.dart`

- **Fixed** 2026-06-11 `MG_SHOPADDEDIT` — Веб, редактирование списка покупок: добавление товара доступно в edit-mode; add-bar (поле + Каталог + «Готово») закреплён над списком, зоны списка скроллятся внутри (max-h, фикс сломанного sticky из-за layout overflow-auto/min-h-screen); из шапки убран дубль «Готово» (MG_SHOPADDEDIT/2/3) — files: `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`

- **Fixed** 2026-06-11 `MG_B02CAT` — Веб: при добавлении в холодильник выбранная категория не применялась (товар уходил в «Прочее»). `fridgeApi.create` теперь шлёт `category_slug`; оба call-site (ручной submit + батч фото-распознавания) — files: `web/menugen-web/src/api/fridge.ts`, `web/menugen-web/src/components/fridge/AddFridgeItemModal.tsx`

- **Fixed** 2026-06-11 `MG_ALIASDEDUP` — Алиасы продуктов: «Сыр Фета»→«Фета» (id 69, cheese), «Филе куриное»/«Куриное филе»→«Курица (филе)» (id 11, meat). Миграция fridge 0010 (seed, идемпотентно; FridgeItem-репойнт не требовался) — files: `backend/apps/fridge/migrations/0010_seed_aliases_feta_chicken.py`

- **Removed** 2026-06-11 `MG_NOIMPORT` — Создание списка покупок: убраны источники «Импорт из текста (ИИ)» и «Импорт CSV» (web `<select>` + mobile dropdown). Backend choices/enum сохранены для отображения старых списков — files: `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `mobile/menugen_app/lib/features/shopping/screens/shopping_create_sheet.dart`

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

- **Added** 2026-06-09 `MG_RUBRICBROWSE_be` — Shopping: rubricator browse-by-category endpoints (IsAuthenticated): /shopping/rubric/categories/ and /shopping/rubric/browse/ — files: `backend/apps/shopping/services.py`, `backend/apps/shopping/views.py`, `backend/apps/shopping/urls.py`

- **Added** 2026-06-09 `MG_RUBRICBROWSE_web` — Web shopping: '+ Каталог' button opens category browser to add existing rubricator products without typing — files: `web/menugen-web/src/api/shopping.ts`, `web/menugen-web/src/pages/Shopping/ItemAutocomplete.tsx`

- **Added** 2026-06-09 `MG_RUBRICBROWSE_mob` — Mobile shopping: catalog browse sheet to add existing rubricator products by category; categories via /shopping/rubric/categories/ — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_add_item.dart`

- **Fixed** 2026-06-09 `MG_RUBRICUNIT` — Shopping add-item: unit dropdown tolerates product units outside preset list (fixes Flutter DropdownButton assertion crash on units like 'упаковка') — files: `mobile/menugen_app/lib/features/shopping/screens/shopping_add_item.dart`, `web/menugen-web/src/pages/Shopping/ItemAutocomplete.tsx`

- **Fixed** 2026-06-09 `MG_IMPORTTRUNC` — Shopping list import (menu/fridge/csv/ai): clamp item fields to column max_length so a long ingredient name no longer 500s the whole import — files: `backend/apps/shopping/views.py`

- **Added** 2026-06-09 `MG_AICLEAN` — Shopping list import from menu: AI-normalize ingredient names (drop non-product noise, canonical merge of variants, dedup with unit conversion). Recipes untouched; raw fallback on AI failure — files: `backend/apps/shopping/services.py`, `backend/apps/shopping/views.py`

- **Added** 2026-06-10 `MG_RECIPELINK` — MG_RECIPELINK — recipe<->product link table (RecipeProduct): AI canonicalize + match rubricator + categorize once; shopping import from menu reads links (category/colour + qty, no per-import AI); post_save hook builds links for new recipes; backfill command — files: `backend/apps/recipes/models.py`, `backend/apps/recipes/recipe_products.py`, `backend/apps/recipes/signals.py`, `backend/apps/recipes/apps.py`, `backend/apps/recipes/migrations/0015_recipeproduct.py`, `backend/apps/recipes/management/commands/mg_backfill_recipe_products.py`, `backend/apps/shopping/services.py`, `backend/apps/shopping/views.py`

- **Changed** 2026-06-10 `MG_RECIPELINK2` — Canonicalizer quality: mechanical split of compound/alt ingredient lines (фета или брынза -> 2 items), AI resolution to rubricator product (synonyms томат/томаты/помидор -> Помидоры), curated alias map, drop fat-% and nullish canon, empty slug -> other, hard singular+Capitalize, per-chunk/per-recipe progress log. linked_to_product 32.6% -> 48.5%. — files: `backend/apps/recipes/recipe_products.py`

- **Fixed** 2026-06-11 `MG_FRIDGESUB` — Shopping import menu-fridge: quantity-aware fridge subtraction (match by product_id else canonical name with %/brand strip + unit conversion); drop item only when remaining<=0 instead of binary raw-name match — files: `backend/apps/shopping/services.py`

- **Fixed** 2026-06-11 `MG_PRODALIAS` — Синонимы продуктов сводятся к одному товару: новая таблица ProductAlias + normalize_alias (ё/е, латиница→кириллица, сорт С1, число-префикс); резолв в холодильнике, канонизации рецептов, агрегации списка и поиске. Слит дубль «Яйца куриные C1»→«Яйца куриные». — files: `backend/apps/fridge/aliases.py`, `backend/apps/fridge/models.py`, `backend/apps/fridge/serializers.py`, `backend/apps/fridge/migrations/0008_productalias.py`, `backend/apps/fridge/migrations/0009_merge_eggs_seed_aliases.py`, `backend/apps/recipes/recipe_products.py`, `backend/apps/shopping/services.py`

- **Fixed** 2026-06-11 `MG_T06RELINK` — T-06: one-time no-AI relink of 86 stale unlinked egg RecipeProduct rows to canonical Product 41 (set product_id + name_canonical + category).

- **Fixed** 2026-06-12 `MG_T01_MAYO` — Слияние дубля Product «Майонез» (id=44→122, sauces): репойнт FK (FridgeItem/ShoppingListItem/RecipeProduct/ProductAlias), удаление дубля, seed alias 'майонез'→122. Миграция fridge 0011 (идемпотентна). — files: `backend/apps/fridge/migrations/0011_merge_mayo_seed_alias.py`

- **Fixed** 2026-06-12 `MG_T07` — Per-item категория холодильника без мутации общего Product (снимает caveat B-03): новое поле FridgeItem.category_fk + property effective_category; category_slug на записи кладётся на item; _resolve_product больше не перезаписывает категорию существующего общего Product (fill-only); read-сериализатор product_category_* читает effective_category (item-override → иначе product). Бэкенд-онли, клиенты без изменений. Миграция fridge 0012. — files: `backend/apps/fridge/models.py`, `backend/apps/fridge/serializers.py`, `backend/apps/fridge/views.py`, `backend/apps/fridge/migrations/0012_fridgeitem_category_fk.py`

- **Fixed** 2026-06-13 `MG_T04RELINK` — T-04: no-AI релинк 57 NULL RecipeProduct -> Product через product_ref_index (только product_id; name_canonical не трогаем). 51.9%->54.1%.

- **Fixed** 2026-06-13 `MG_T04SEED` — T-04: наполнение рубрикатора по выверенному воркшиту (freq>=3): +83 Product (с категориями), +11 ProductAlias (порядок слов), +9 FOLD (внутр. дубли: Яичные белки->Яичный белок, Маслины->Оливки, Замороженный шпинат->Шпинат, Тыква запечённая->Тыква, Казеин/Протеин->Протеин сывороточный), релинк 732. 54.1%->82.9%.

- **Fixed** 2026-06-13 `MG_T04C` — T-04 вариант C (новые рецепты): поле Product.source (manual|auto|import); rebuild_recipe_links(create_missing) + guard _is_seedable + инлайн get_or_create(Product, source=auto); backfill create_missing=True (покрывает bulk-импорт, минующий post_save); signals.post_save create_missing=True. Миграция fridge 0013. — files: `backend/apps/fridge/models.py`, `backend/apps/recipes/recipe_products.py`, `backend/apps/recipes/signals.py`, `backend/apps/fridge/migrations/0013_product_source.py`

- **Fixed** 2026-06-13 `MG_T05` — T-05: единый рантайм-нормализатор единиц _mg_norm_unit + _MG_UNIT_SYN (упак->упаковка, мн.формы кусочков, ложки/стакан/штука/грамм, числовой мусор->'', зубчик->шт); _fr_base/_fr_unit_factor прогоняются через него. Разные счётные единицы не сводятся; приблизительные изолированы. synonyms.yaml рантайм не использует. — files: `backend/apps/shopping/services.py`

- **Fixed** 2026-06-13 `MG_T05CLEAN` — T-05: чистка числового мусора в RecipeProduct.unit ('5'->'') — 2 строки.

- **Changed** 2026-06-14 `MG_T08_idempotent` — Shopping toggle endpoint made idempotent: same-value PATCH is a no-op (no duplicate PurchaseHistoryEntry / Product price update) so the offline queue can replay safely — files: `backend/apps/shopping/views.py`

- **Added** 2026-06-14 `MG_T08_web` — Offline-first shopping toggle (web): optimistic update, localStorage LWW queue (last action wins), online/offline status indicator (green/amber/red) in header, flush on reconnect — files: `web/menugen-web/src/hooks/useOnlineStatus.ts`, `web/menugen-web/src/utils/syncQueue.ts`, `web/menugen-web/src/components/layout/SyncIndicator.tsx`, `web/menugen-web/src/components/layout/AppLayout.tsx`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`

- **Added** 2026-06-14 `MG_T08_mobile` — Offline-first shopping toggle (mobile, NOT verified — needs rework): in-memory LWW queue in ShoppingBloc, global PendingSyncCubit, SyncIndicator strip, connectivity banner text -> 'Нет подключения', flush on reconnect — files: `mobile/menugen_app/lib/core/sync/pending_sync_cubit.dart`, `mobile/menugen_app/lib/core/widgets/sync_indicator.dart`, `mobile/menugen_app/lib/core/widgets/connectivity_banner.dart`, `mobile/menugen_app/lib/core/widgets/main_shell.dart`, `mobile/menugen_app/lib/main.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`, `mobile/menugen_app/lib/features/shopping/bloc/shopping_bloc.dart`

<!-- CHANGELOG_AUTO_ANCHOR — new entries inserted above this line by add_changelog.py -->
- **Fixed** 2026-06-14 `MG_T10` — Mobile офлайн-UX: сетевые ошибки → «Нет подключения к интернету» (вместо сырого Dio-текста); баннер → «Офлайн режим, функционал ограничен. Вернитесь в сеть :)»; при офлайне скрыты тело-ошибки и error-snackbar на вкладках (Холодильник/Меню/Рецепты/Дневник) и в Покупках — files: `mobile/menugen_app/lib/core/api/dio_api_client.dart`, `core/widgets/connectivity_banner.dart`, `features/fridge/screens/fridge_screen.dart`, `features/menu/screens/menu_screen.dart`, `features/recipes/screens/recipes_screen.dart`, `features/diary/screens/diary_screen.dart`, `features/shopping/screens/shopping_list_screen.dart`, `features/shopping/screens/shopping_detail_screen.dart`
- **Fixed** 2026-06-14 `MG_T09` — Mobile: индикатор соединения опущен под статус-бар (SafeArea); глобальная app-lifetime `OfflineToggleQueue` — офлайн-тоггл списка синхронизируется после ухода с вкладки и возврата сети — files: `mobile/menugen_app/lib/core/widgets/main_shell.dart`, `core/sync/offline_toggle_queue.dart`, `main.dart`, `features/shopping/bloc/shopping_bloc.dart`, `features/shopping/screens/shopping_list_screen.dart`
- **Added** 2026-06-14 `MG_T09` — Счётчики списков в падах Активные/Ожидают/Архив/История (backend `GET /shopping/counts/`) + фильтр «только некупленные» в списке (web+mobile+backend) — files: `backend/apps/shopping/views.py`, `backend/apps/shopping/urls.py`, `web/menugen-web/src/api/shopping.ts`, `web/menugen-web/src/pages/Shopping/ShoppingPage.tsx`, `mobile/menugen_app/lib/features/shopping/screens/shopping_list_screen.dart`, `mobile/menugen_app/lib/features/shopping/screens/shopping_detail_screen.dart`
