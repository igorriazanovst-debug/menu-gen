# BACKLOG (баги и недоработки)

> Ведётся как changelog. Статусы: `OPEN` / `IN_PROGRESS` / `CLOSED`.
> Каждая задача: `PK → диагностика → вывод пользователя → патч`.

## Новые задачи (chat-83)

### T-21 — s1: разметка приёмов разошлась с ролями генератора · severity: medium · ✅ ИСПРАВЛЕНО в коде, ждёт прогона на проде (chat-83)
`mg_analyze_s1_repeats --runs 20 --days 7` после публикации say7 показал пять
рецептов в **20 прогонах из 20**, и все пять — десерты. Пул десертов при этом 45
при потребности 28, то есть формально «🟢 ок».

**Корень найден и подтверждён замером.** `suitable_for` отвечает на вопрос «для
каких приёмов годится блюдо», и генератор по нему отсеивает кандидатов
(`_pick_for_role`). Импорт say7 помечал `dessert: ["snack"]` и
`bakery: ["breakfast", "snack"]` — а роли «десерт» и «выпечка» существуют ТОЛЬКО
в обеде, перекус же берёт блюда с `dish_type='snack'`, а не десерты. Блюдо
объявлено годным туда, куда попасть не может, и негодным туда, где его
единственный слот.

Замер на проде (недостижимых / всего):

    dessert   40 / 45      bakery  33 / 35
    snack      5 / 30      main     4 / 170
    salad      4 / 57      breakfast_dish  4 / 54     soup  0 / 19

Первая гипотеза («нет `portion_g`, не проходит коридор калорий») проверена и НЕ
подтвердилась: годных десертов 44 из 45.

Почему пятёрка вылезала ровно в 100 % прогонов: в отборе есть подстраховка —
если фильтр по `suitable_for` не оставил кандидатов, он снимается. За семь дней
слот десерта срабатывает ~7 раз, достижимая пятёрка расходуется, и остальные
сорок появляются только по запасному пути. Отсюда длинный хвост на 5–15 %.

Сделано (chat-83):

* `manage.py mg_fix_suitable_for` — дописывает недостающие приёмы, ничего не
  удаляя; пустой `suitable_for` не трогает (для генератора это «годится везде»).
  По умолчанию сухой прогон, запись с `--apply`. Таблица «роль → приёмы»
  ВЫВОДИТСЯ из `MEAL_COMPONENTS`/`MEAL_TYPE_DB`, а не переписана рядом: копия
  разошлась бы с оригиналом ровно так же, как разошлась разметка импорта.
* `import_say7_recipes.SUITABLE_BY_DISH`: `dessert` → `["lunch", "snack"]`,
  `bakery` → `["breakfast", "lunch", "snack"]`, чтобы не приехало со следующей
  выгрузкой.
* Тест `test_suitable_for_fix.py`, в т. ч. проверка, что словарь импорта
  согласован с ролями генератора.

Осталось: прогнать на проде (`mg_fix_suitable_for` → `--apply`) и перемерить
`mg_analyze_s1_repeats`.

**Побочный эффект, который заметят:** `suitable_for` используется и фильтром
«приём пищи» в каталоге (`apps/recipes/filters.py`). После правки десерты и
выпечка появятся в выдаче по фильтру «обед». По смыслу верно, но выдача
изменится.

### T-20 — 14 рецептов say7 без веса порции · severity: low · OPEN (chat-83)
Из 134 неопубликованных say7-рецептов с фото опубликовано 120; эти четырнадцать
придержаны:

6729, 6751, 6757, 6760, 6767, 6772, 6785, 6794, 6799, 6803, 6808, 6828, 6851, 6861

У всех пусто `portion_g` и `kcal` (на 100 г КБЖУ есть). Без веса порции рецепт
не попадает ни в коридор калорий, ни в «Тарелку»: в каталоге он был бы виден, а
генератор не взял бы его никогда, и в карточке не было бы КБЖУ на порцию.

У шести известно число порций (6760 — 40, 6767 — 3, 6803 — 5, 6808 — 70,
6828 — 40, плюс проверить остальные), у восьми нет и его.

Отдельно: **6803 «Фруктовый салат» — 600 ккал на 100 г**. Для фруктов это
невозможно; ошибка в исходных данных, публиковать нельзя даже после заполнения
веса, пока не пересчитано.

Варианты: проставить вес руками там, где известны порции; либо прикинуть по
составу (граммы в составе есть), помня, что это вес СЫРЫХ продуктов и у выпечки
оценка завышена процентов на десять.

## Новые задачи (chat-82)

### T-19 — продажа подписки за пределами России · severity: low · OPEN (chat-82)
Пока приложение раздаётся только в России, делать нечего: требование продавать
цифровые товары через биллинг Google **не действует для платежей от
пользователей из России** (исключение от 02.08.2022, введено потому, что Google
сам остановил там свой биллинг). ЮKassa законна, конфликта нет.

Задача всплывает в один момент — когда захочется открыть хотя бы одну страну
кроме России. Тогда без биллинга Google нельзя, а он упирается НЕ в код:

* с 26.12.2024 Google приостановил услуги продавца для разработчиков со счётом
  для выплат в России — покупки и продления через биллинг Google у них просто
  не проходят. То есть сначала платёжный профиль и счёт вне России, и только
  потом библиотека;
* правила продаж мимо биллинга с 09.12.2025 ослаблены, но идут через
  оформленные программы (внешние ссылки, альтернативный биллинг) со своими
  отчислениями — в Великобритании, например, 10 % на подписки в пределах
  первого миллиона долларов.

Как встроить, чтобы ЮKassa не нарушала правил (решение принято, не проверено):

1. Развилка по СТРАНЕ АККАУНТА Play, а не по языку и не по IP: библиотека
   биллинга отдаёт её через `getBillingConfig().countryCode`. `RU` — ЮKassa,
   всё остальное — покупка через Google. Пользователь видит ровно один способ
   оплаты и не выбирает между ними: нарушать нечего, если второго способа для
   него не существует.
2. Подписка остаётся на нашем сервере (`apps/payments`) — единственный источник
   правды. Оба канала только продлевают срок, остальная логика не меняется.
3. Покупки Google подтверждает СЕРВЕР через Play Developer API по уведомлениям
   о покупках и продлениях. Чеку, пришедшему от клиента, верить нельзя.
4. Никаких упоминаний другого способа оплаты там, где он не разрешён: ни серым
   текстом под кнопкой, ни ссылкой «на сайте дешевле». Это первое, на чём ловят.

Оценка: не неделя работы. Платёжный профиль в другой юрисдикции + серверная
проверка покупок + вторая ветка оплаты в приложении + комиссия 10–30 % сверху.
Браться только после того, как появится подтверждённый спрос из-за рубежа.

## Новые задачи (chat-81)

### T-18 — импорт справочника: код в другом написании плодит дубль · severity: low · OPEN (chat-81)
`import_barcode_catalog._load` ищет существующую запись по всем написаниям кода
(`lookup_q` — UPC-A с ведущим нулём и без), а перезаписывает по точному:
`Product.objects.update_or_create(barcode=barcode, ...)`. Если запись лежит как
`0011210000032`, а в выгрузке `011210000032`, и её источник заменяемый
(`retail`/`off_bulk`/`ai`), то ветка «обновить» не срабатывает — заводится вторая
строка на тот же товар. Заведена до MG_BARCODEOFF, не им.

Практикой пока не подтверждено: на импорте OFF (24.08) добавлено ровно столько,
сколько ожидалось (prod 21843, dev 21844), массовых дублей нет. Всплывёт на
выгрузке, где написание кодов разойдётся с уже загруженным.

Патч: обновлять найденную запись (`existing`), а не звать `update_or_create` по
точному коду; создавать — только когда `existing is None`. Тест: запись с
`0011210000032` + строка выгрузки `011210000032` → одна строка, не две.

## Новые задачи (chat-80)

### T-17 — s1: дополнить пулы рецептов salad/snack/bakery · severity: medium · OPEN (chat-80)
После импорта tati_cooks (MG_TGIMPORT) и удаления напитков (MG_DRINK) `mg_analyze_s1_repeats` показывает: алгоритм здоров, проблема — нехватка пула по 3 ролям. Формула N ≥ d/T (min=1×d, good=4×d, great=10×d где d = слотов/нед):
- **salad**: пул 32, спрос 14/нед → need 56 (good). Дефицит: **+24**. Топ повторяемости — 100% (3 рецепта), ≥80% — 27.
- **snack**: пул 26, спрос 14/нед → need 56 (good). Дефицит: **+30**.
- **bakery**: пул 27, спрос 7/нед → need 28 (good). Дефицит: **+1** (почти ок).
- main/breakfast_dish/dessert/soup — уже green (good или отлично).

Что нужно: найти источник рецептов с КБЖУ (per-portion!) для салатов и перекусов; написать парсер/импорт по образцу `import_telegram_recipes`; после импорта прогнать `mg_seed_plate --apply` → `mg_backfill_recipe_products` → `mg_analyze_s1_repeats --runs 20 --days 7`.

Команды диагностики: `python manage.py mg_analyze_s1_repeats --runs 20 --days 7 [--role salad]`.

**Замер chat-83, после публикации 120 рецептов say7 (см. T-20).** Салаты и выпечка
закрыты, перекусы остались:

| роль | было (chat-80) | стало | need (good) | статус |
|---|---|---|---|---|
| salad | 32 | **57** | 56 | 🟢 закрыто |
| bakery | 27 | **35** | 28 | ⚠️ см. ниже |
| snack | 26 | **30** | 56 | 🟡 дефицит 26 |
| soup | — | **19** | 28 | 🟡 дефицит 9 |

Про soup: в chat-80 он был записан как green, сейчас показывает 🟡 при пуле 19.
Что именно изменилось — не проверено; возможно, прежняя запись была неточной.
Считать регрессом без проверки нельзя, но при следующем заходе на пулы это стоит
посмотреть первым делом.

**Поправка (chat-83, после разбора T-21): выпечка НЕ закрыта.** Пул 35, но
достижимых из них 2 — остальные 33 помечены приёмами, в которых роль «выпечка»
не встречается. Та же беда у десертов (5 из 45). Пока не выполнен
`mg_fix_suitable_for --apply` на проде, цифры пулов в этой таблице завышены для
выпечки и десертов, а по остальным ролям верны (недостижимых 0–5).

Остаток задачи — перекусы (+26). Но браться за добор рецептов имеет смысл ТОЛЬКО
после T-21: новые попадут под тот же отсев, и добор снова не даст эффекта.

### T-15 (s1-часть) — s1 повторяемость рецептов · severity: medium · 🟡 IN_PROGRESS (chat-80)
Диагностика создана и запущена (MG_S1ANALYZE). Корень найден: не алгоритмический баг, а нехватка пула рецептов. Частично закрыто:
- ✅ **MG_S1ANALYZE** — `mg_analyze_s1_repeats` diagnostic command (синтетический тест N меню + таблица спроса N≥d/T)
- ✅ **MG_DRINK** — напитки убраны из `MEAL_COMPONENTS` s1 (пул 4 → 100%-повторы, пожирал калорийный бюджет завтрака)
- ✅ **MG_TGIMPORT** — `import_telegram_recipes`: парсинг tati_cooks Telegram-экспорта; импортировано ~24 рецепта (salad 20→32)
- 🟡 **Остаток** → **T-17** (salad +24, snack +30)

## Новые задачи (chat-79)

### T-15 — s3 «Тарелка»: наполнение базы простыми моно-компонентами (data) · severity: medium · OPEN (chat-79→80)
s3 технически работает (форма 25/25/50 по массам, калории в точку, ключ уникален), но тарелка собирается из 3 **составных** блюд → «насыщенно» (напр. «Кальмары с овощами и рисом» + «Спагетти с фрикадельками» + «Салат-закуска из свёклы»). Корень — в базе почти нет моно-компонентных рецептов: плейт-пулы (protein 90 / carb 47 / veg 36) состоят из `dish_type=main` с медианой ~7 ингредиентов; `side`-гарниров (простой рис/гречка) — **0**. Метод тарелки требует компонентов из 1–2 продуктов.
Решение (пользователь, data): добавить ~150 простых рецептов + ~20 гарниров. Для попадания в пулы s3 у новых рецептов: `is_published=true`, `portion_g>0`, раскладка `kcal_per_100g`; `food_group` = protein/grain/vegetable; `dish_type` в whitelist `{main, side, salad, breakfast_dish, snack}` (для гарниров — **`side`**). Затем `mg_seed_plate --apply` (авто-сид подхватит новые) или ручная разметка `plate_component`. Код s3 НЕ меняется.
Примечание chat-80: пересечение с T-17 — источник рецептов tati_cooks (MG_TGIMPORT) добавил ~24 рецепта, часть попадёт и в s3-пулы после `mg_seed_plate`. Моно-компонентная нехватка (side=0) остаётся.

### T-16 — s2 качество доборов · severity: low · OPEN (chat-79)
Добор роли `carb` к завтраку взял десерт («Апельсиновый пирог») — формально углевод, но как «добор углеводов» спорно. Отбор доборов (`_pick_role_addon_s2`) можно сузить по `dish_type`/исключению desserts. На запись/коллизии не влияет.

## Новые задачи (chat-78)

### T-14 — Стратегии генерации меню (s1/s2/s3) · severity: medium · IN_PROGRESS (MG_STRAT*/MG_STRAT2_ROLE/MG_STRAT3*, chat-78→79)
Введены 3 стратегии генерации, выбираемые пользователем. Бэкенд + UI (web/mobile) готовы и проверены; качество s3 ждёт наполнения базы (T-15).

**Сделано (бэкенд, chat-78):**
- **Payload `strategy`** (`"1"|"2"|"3"`, default `"1"`) в `GenerateMenuSerializer`; проброс в `filters` (`views.py`); ветвление в `MenuGenerator.generate()` (для s2/s3 — путь per_member, family пока не поддержан).
- **MG_STRAT_PLATE:** `Recipe.plate_component` (`protein|carb|veg`, nullable) + миграция `recipes/0016_recipe_plate_component` + admin-fieldset; новый `apps/menu/macro_roles.py` — `MACRO_ROLES` (slug категории продукта → набор макро-ролей: protein/fat/carb_complex/carb_simple/fiber) + `recipe_roles()/recipe_has_role()/recipe_has_carb()` (presence по `product_links` → `product.category_fk.slug`). Маппинг: meat/fish/eggs=protein; cheese/sausages/dairy={protein,fat}; grains/bakery=carb_complex; sweets=carb_simple; oils=fat; vegetables/fruits=fiber; canned/frozen/ready/sauces/condiments/drinks/other/household/hygiene/pets=без роли.
- **s1** — без изменений (выбор `meal_plan_type` 3/5 остаётся).
- **s2** (состав приёма по макро-ролям, presence): завтрак `protein+fat+carb(любой)+fiber`; обед `protein+carb_complex+fiber`; ужин `protein+fiber` (+carb_complex-гарнир, только если его не было в обед того же дня). Основной рецепт приёма — `_pick_for_role`, недостающие роли добираются `_pick_role_addon_s2`; `raise EmptyRolePoolError` при непокрытии. Перекусы-добор по дневному КБЖУ ±5% (`_fill_snacks_s2`, безусловно при `calorie_target`). `meal_plan_type` игнор; **MG-304 off** для s2.
- **s3** (тарелка 25/25/50) — первоначальная версия chat-78 (форма «искалась», `MG_STRAT3_PICK2` сэмплинг) — **переработана в chat-79** (см. ниже).

**Обновление chat-79 (разметка + переработка s3 + фикс записи s2/s3 + UI):**
- **D-07 закрыт:** `Recipe.plate_component` размечен management-командой **`mg_seed_plate`** (food_group + dish_type whitelist `{main,side,salad,breakfast_dish,snack}`: protein→protein, grain→carb, vegetable/fruit→veg; идемпотентно по `NULL`; `--dry-run`/`--apply`). Размечено protein/carb/veg = **90/47/36** (173 рецепта). Команда — в репо (`apps/recipes/management/commands/mg_seed_plate.py`).
- **s3 переработан (MG_STRAT3_PLATEFORM/SELECT/CLEAN):** прежний подход «искал» тройки, у которых сырые `portion_g` уже в пропорции 25/25/50 — на реальной базе давал **0 троек** (равные массы → veg-доля ~0.33 при цели 0.50). Теперь форма **ЗАДАЁТСЯ** масштабом каждого компонента под массу тарелки `M` (M из целевых калорий приёма; при отсутствии — 400 г), per-item `quantity = доля·M/portion_g`, кламп `[0.25..3.0]`; выбор лучшей тройки **сэмплингом K=30** по `(форма + относит. отклонение калорий)`. Verify: форма 25/25/50 (±2%) **0 нарушений/300**, калории ±10% **300/300** (разброс 698–702). Удалён мёртвый код прежнего подхода (`_plate_form_ok`, `PLATE_RATIO_TOL`, `PLATE_SCALE_MIN/MAX`).
- **IntegrityError записи (unique_together `menu,member,day,meal_slot,component_role`):** проявлялся только на ЗАПИСИ (in-memory `generate()` не писал → не воспроизводился; вешалось 500 на реальном API). Корень — несколько рецептов приёма с одинаковым `component_role=dish_type`. Фикс: **s3** — `component_role` из `plate_component` (protein→main/carb→side/veg→salad, **MG_STRAT3_ROLE**); **s2** — `component_role` уникален внутри приёма (якорь=`dish_type`, доборы=макро-роль protein/fat/carb/carb_complex/fiber, **MG_STRAT2_ROLE**; снеки уже в отдельных слотах `snack{n}`). Smoke через реальный API: s3 menu#69, s2 menu#74 → **201**, MenuItem без дублей ролей.
- **Web-селектор (MG_STRAT_WEB):** блок «Стратегия меню» (Стандарт / По составу / Тарелка 25/25/50); `meal_plan_type` (3/5) скрыт для s2/s3, в payload только для s1; `strategy` в payload всегда. `tsc --noEmit`✓ / build✓ / выложено в web-dist + nginx reload.
- **Mobile-селектор (MG_STRAT_MOBILE):** `strategy` в `MenuGenerateRequested` + `body` (bloc: `meal_plan_type` только при s1); селектор `_strategyTile` в bottom-sheet, блок 3/5 обёрнут `if (_strategy=='1')`. Flutter CI ✓ (APK собран; device-verify pending — D-02).
- **Коммиты chat-79:** `1884398` (generator.py s3 + mg_seed_plate.py), `241d41a` (generator.py s2-fix + web api/menu.ts + GenerateMenuForm.tsx + mobile event/bloc/bottom-sheet). CHANGELOG — отдельным коммитом.

**Открытые хвосты T-14:**
- ✅ Разметка `plate_component` — закрыт (D-07, mg_seed_plate).
- ✅ Web/mobile селектор `strategy` + скрытие `meal_plan_type` для s2/s3.
- ✅ Фикс записи s2/s3 (IntegrityError unique_together).
- **s3 наполнение базы простыми компонентами** → **T-15** (иначе тарелка «насыщенная»); + перекусы-опция в s3 (payload-параметр + UI) — после наполнения.
- **Тесты pytest** на ветки s2/s3 (по аналогии с MG-301).
- **family-режим** для s2/s3 (сейчас per_member).
- **Вынос `macro_roles` в админку** — D-08.
- **Качество доборов s2** → T-16.

## Новые задачи (chat-76)

### T-13 — Mobile: офлайн-кэш списков покупок (просмотр + работа без сети) · severity: medium · CLOSED (MG_CACHE/MG_CACHE2, chat-76)
Раньше в офлайне списки/детализация показывали `cloud_off` — данные не кэшировались, без сети работал только тоггл через `OfflineToggleQueue`.
Решение (MG_CACHE): `ShoppingCache` (`lib/core/cache/shopping_cache.dart`) — write-through кэш в `shared_preferences` (TTL 7 дней; успешный онлайн-GET затирает запись). `ShoppingBloc._reloadLists`/`_onDetail` пишут сырой JSON ответа в кэш; в офлайне `_onLists`/`_onDetail` отдают данные из кэша (фолбэк по `_isOffline`), офлайн-тоггл «куплено» пишется в кэш (`patchDetailItemPurchased`) и переживает уход с экрана. Wiring: `main.dart` (`SharedPreferences.getInstance()` + `RepositoryProvider<ShoppingCache>.value`), провайдер в `shopping_list_screen.dart`. Экраны не менялись — офлайн теперь эмитит Loaded из кэша, `cloud_off` остаётся фолбэком при пустом кэше.
Баг после первой проверки → MG_CACHE2 (reconnect-гонка): при возврате сети «зависала синхронизация» + откат вычеркнутого товара. Корень: `flush()` срабатывал на фронте `connectivity online` до реальной готовности сети → PATCH падал, `break` без ретрая → очередь не пустела; затем успешный GET затирал оптимистичный тоггл. Решение: (1) ретрай `flush()` по таймеру 3 с пока очередь не пуста и онлайн; (2) `OfflineToggleQueue.pendingForList()` + `_applyPending()` в `_onDetail` — переналожение незасинканных тогглов поверх ответа сервера. Файлы: `offline_toggle_queue.dart`, `shopping_bloc.dart`.
Verify (chat-76): пользователь подтвердил на APK — офлайн просмотр списков/детализации из кэша, офлайн-тоггл сохраняется при уходе с экрана, после возврата сети индикатор гаснет за ~3 с и значение не откатывается ✓.

## Новые задачи (chat-75)

### T-09 — Mobile: индикатор соединения под системной строкой Android · severity: low · CLOSED (MG_T09 #1, chat-75)
`SyncIndicator` был первым ребёнком `Scaffold.body Column` без `SafeArea` → рисовался под статус-баром.
Решение: `body` обёрнут в `SafeArea(bottom: false)` (верхний инсет применяется к индикатору/баннерам; bottom-nav не трогается). Файл: `main_shell.dart`.
Verify (chat-75): APK на устройстве — индикатор «Нет сети» ниже системной строки ✓.

### T-10 — Счётчики списков в падах Активные/Ожидают/Архив/История · severity: low · CLOSED (MG_T09 #3, chat-75, web+mobile+backend)
В падах раздела «Покупки» не отображалось количество списков.
Решение: новый backend-эндпоинт `GET /shopping/counts/` (`ShoppingCountsView` → `{active, pending, archived, history}`; active/archived = own|accepted-shared по `is_archived`, pending = shared+PENDING, history = `PurchaseHistoryEntry` семьи). Web `shoppingApi.counts()` + счётчики в лейблах табов (refresh на смене таба и после create/delete/archive). Mobile `_loadCounts()` + суффикс `(n)` в `SegmentedButton`. Файлы: `backend/apps/shopping/views.py`,`urls.py`; web `api/shopping.ts`,`ShoppingPage.tsx`; mobile `shopping_list_screen.dart`.
Verify (chat-75): backend `{"active":2,"pending":0,"archived":1,"history":18}` ✓; web build ✓; APK ✓ (пользователь подтвердил «все вопросы работают»).

### T-11 — Фильтр «только некупленные» в списке · severity: low · CLOSED (MG_T09 #4, chat-75, web+mobile)
Клиентский фильтр view-mode. Web: кнопка-тогл «☐/☑ Только некупленные» в шапке + фильтрация в `grouped` (`!editMode && onlyUnpurchased`), пустое состояние «Все товары куплены». Mobile: иконка `filter_alt(_outlined)` в AppBar детализации + фильтрация `d.items` перед `_grouped`, пустое состояние «Все товары куплены». Файлы: web `ShoppingPage.tsx`; mobile `shopping_detail_screen.dart`.
Verify (chat-75): web ✓; APK ✓.

### T-12 — Mobile: сырые сетевые ошибки в офлайне → только баннер · severity: medium · CLOSED (MG_T10/MG_T10b, chat-75)
В офлайне экраны показывали сырой Dio-текст «The connection errored: Connection failed…» (и в теле экрана, и в snackbar).
Корень: `DioApiClient._throw` при отсутствии HTTP-ответа ставил `message = e.message` (английская строка Dio).
Решение: (a) сетевая ошибка (нет ответа) → `message = 'Нет подключения к интернету'` (`dio_api_client.dart`); (b) оранжевый баннер → «Офлайн режим, функционал ограничен. Вернитесь в сеть :)» (`connectivity_banner.dart`, `Flexible`+центрирование); (c) при офлайне (ключ `ConnectivityCubit`) скрыты тело-ошибки и error-snackbar на вкладках fridge/menu/recipes/diary и в Покупках (список+детализация) — вместо текста тихий `Icon(cloud_off)`, snackbar не показывается. Файлы: `dio_api_client.dart`, `connectivity_banner.dart`, `fridge_screen.dart`, `menu_screen.dart`, `recipes_screen.dart`, `diary_screen.dart`, `shopping_list_screen.dart`, `shopping_detail_screen.dart`.
Verify (chat-75): патчи применены; финальная проверка на APK — pending (следующий чат после CI).

## Новые баги (chat-68)

### B-06 — Пикер меню: имя+даты вместо #id · severity: low · CLOSED (web, MG_MENULABEL chat-68 → фактически MG_B09 chat-69)
Dropdown меню при создании списка (источники «из меню» / «из меню-минус-холодильник») показывал `#id`.
Решение: лейбл `{creator_name} DD.MM–DD.MM`. `MenuListSerializer.creator_name` (`creator_id`→`User.name`). Web `ShoppingPage.tsx` `<option>` + TS-тип.
⚠️ В chat-68 правка MG_MENULABEL по факту НЕ была подключена: web `<option>` читал несуществующий `m.title`, а backend сериализатор не отдавал `creator_name`. Реально заработало только в **MG_B09 (chat-69)** — см. B-09. Verify (chat-69): web ✓ после деплоя+`Ctrl+Shift+R`.

### B-07 — Веб: нельзя добавить товар при редактировании списка · severity: medium · CLOSED (MG_SHOPADDEDIT/2/3, chat-68)
`ItemAutocomplete` рендерился только вне edit-mode (`&& !editMode`) → в режиме «✎ Редактировать» поля/каталога нет.
Решение: add-bar (поле + Каталог + единственная «✓ Готово») закреплён над списком при `caps?.manage && editMode`; зоны списка в edit-mode скроллятся внутри `max-h-[60vh] overflow-y-auto` (sticky не сработал: `AppLayout main` = `overflow-auto` + `min-h-screen` → скроллит окно, sticky липнет к нескроллящемуся main). Шапка вне edit показывает только `✎ Редактировать`. Verify (chat-68): ✓.

### B-08 — Mobile: повторить логику B-07 в детализации списка · severity: low · CLOSED (MG_B08, chat-71)
Реплика B-07 на мобайле. Корень: add-bar `ShoppingAddItem` был гейтнут `caps.manage && !_editMode` → в edit-mode добавить товар нельзя.
Решение: гейт → `caps.manage` (add-bar виден и в edit-mode). Внутренний скролл из web не нужен — список уже скроллится в `Expanded > ListView`; «Готово» = check-иконка в AppBar; print/people/popup уже скрыты в edit-mode. Файл: `shopping_detail_screen.dart`. Verify (chat-71): APK ✓.

### B-09 (M1) — Mobile: в пикере «из меню» только даты, без имени · severity: low · CLOSED (MG_B09, chat-69)
Корень оказался шире (3 уровня): backend `MenuListSerializer.fields` НЕ содержал `creator_name` (метода `get_creator_name` не было) → `/menu/` имя не отдавал вовсе; web `<option>` и mobile dropdown читали несуществующий `m.title`/`m['title']` → fallback `Меню #id`. Правка MG_MENULABEL (chat-68) фактически не работала ни на одном клиенте.
Решение (MG_B09): backend `creator_name = SerializerMethodField` (`creator_id`→`User.name`, `''` если нет) + в `fields`; web `<option>` → `{creator_name} DD.MM–DD.MM` (ISO через `slice`, TZ-safe, fallback `Меню #id`) + `Menu.creator_name?`; mobile `_menuLabel()` (ISO через `substring`, TZ-safe, en-dash, fallback). Заодно восстановлен B-06 (web).
Verify (chat-69→71): backend `/menu/` → `creator_name 'Игорь Рязанов'` ✓; web ✓; mobile свежий APK — имя+даты ✓.

### B-10 (M2) — Mobile: после создания списка экран пуст до переключения вкладок · severity: medium · CLOSED (MG_B10, chat-71)
После create список не появлялся до переключения вкладок. Корень: `_onCreate` эмитил `ShoppingDetailLoaded` (у экрана списков нет ветки под него → пустой `SizedBox`), а параллельный `_openCreate`→`_selectTab(0)` гнал ещё один `ShoppingListsRequested` (гонка stale-GET).
Решение: `_onCreate` → `_archived=false` + `_reloadLists`; `_openCreate` → `setState(_tab=0)` без второго reload. Файлы: `shopping_bloc.dart`, `shopping_list_screen.dart`. Verify (chat-71): APK ✓.

### B-11 (M3) — Mobile: «покупка» товара сбрасывает скролл списка наверх · severity: low · CLOSED (MG_B11, chat-71)
При toggle is_purchased `_onToggle` делал `add(ShoppingDetailRequested)` → `ShoppingLoading` (полноэкранный спиннер) → ListView пересоздавался с нуля → скролл в начало.
Решение: после успешного PATCH обновлять item in-place через `copyWith` и эмитить `ShoppingDetailLoaded` без `ShoppingLoading`. Добавлены `copyWith` в `ShoppingItem`/`ShoppingListDetail`. Файлы: `shopping_bloc.dart`, `shopping_models.dart`. Verify (chat-71): APK ✓.

## Новые баги (chat-66/67)

### B-01 — Дедупликация «Яйца» · CLOSED (MG_PRODALIAS, chat-66)
`ProductAlias` + `normalize_alias` + `resolve_product`; дубль «Яйца куриные C1»→41.

### B-02 — Веб: категория при add-fridge · CLOSED (MG_B02CAT, chat-67)
`fridgeApi.create` шлёт `category_slug`, оба call-site.

### B-03 — Нет редактирования продуктов в холодильнике · severity: medium · CLOSED (MG_B03, chat-71, backend+web+mobile)
Нельзя было изменить категорию/кол-во/единицу/срок уже добавленного продукта.
Корень backend: `FridgeItemWriteSerializer` имел только `create` (с `_resolve_product`), без `update` → дефолтный DRF-`update` не пере-резолвил `Product`, и смена `category_slug` не меняла категорию (она на `product.category_fk`).
Решение:
- backend: `FridgeItemWriteSerializer.update()` — зеркало `create()`; при наличии `category_slug` пере-резолвит/обновляет `Product`. Эндпоинт `PATCH /fridge/{id}/` (`FridgeItemDetailView`).
- web: `fridgeApi.update`, `EditFridgeItemModal.tsx`, кнопка ✎ в карточке `FridgePage`.
- mobile: `edit_fridge_item_sheet.dart`, ✎ в AppBar `fridge_item_detail_screen`, reload списка по возврату (`fridge_screen` onTap → `FridgeLoadRequested`).
Verify (chat-71): web ✓; mobile — финальная проверка APK ✓ на устройстве (chat-72). Caveat per-item категории закрыт в **T-07** (chat-72).

### B-04 — Алиасы Фета/Куриное филе · CLOSED (MG_ALIASDEDUP, chat-67)

### B-05 — Убрать импорт ai_text/csv из создания списка · CLOSED (MG_NOIMPORT, chat-67)

## Открытые хвосты

### T-01 — Дубли товаров в рубрикаторе · severity: high · CLOSED (MG_T01_MAYO, chat-72)
Аудит дублей `Product` по `normalize_alias`: единственная коллизия — «Майонез» (id=44 `oils` / id=122 `sauces`); «Сметана 6 vs 77» как коллизия не воспроизвелась.
Решение (data-миграция `fridge/0011_merge_mayo_seed_alias.py`, паритет с 0009): канон id=122 (`sauces`), репойнт FK (`FridgeItem`/`ShoppingListItem`/`RecipeProduct.name_canonical`/`ProductAlias`) с id=44 → удаление id=44 → seed `ProductAlias 'майонез'→122`. Backward no-op, идемпотентно.
Verify (chat-72): products 192→191, alias-коллизий 0, `resolve_product('Майонез')→122`, дубль удалён.

### T-07 — Смена категории мутирует общий `Product` · severity: medium · CLOSED (MG_T07, chat-72, из B-03)
`_resolve_product` при смене категории товара переписывал `category_fk` у общего `Product` → переезжали и другие его вхождения.
Решение (подход A, бэкенд-онли): новое поле `FridgeItem.category_fk` (nullable FK → `ProductCategory`) + property `effective_category` (item-override → иначе `product.category_fk`); миграция `fridge/0012_fridgeitem_category_fk.py`. `FridgeItemSerializer.product_category_*` читают `effective_category.*` (имена ключей те же → web/mobile не трогаются). `_resolve_product` стал fill-only (`existing.category_fk_id is None`) — не перезаписывает категорию существующего общего `Product`. `create()`/`update()`: `category_slug` → `FridgeItem.category_fk` (через `_cat_from_slug`); пустой slug в `update` очищает override.
Verify (chat-72, транзакция с откатом): override отражается в сериализаторе (`slug=cheese/name=Сыры/id=15`), общий `Product` не тронут (`dairy`), drift нет.

### T-04 — Канонизатор RecipeProduct · severity: medium · CLOSED (MG_T04RELINK + MG_T04SEED + MG_T04C, chat-73)
Связность `RecipeProduct.linked_to_product` поднята **51.9% → 82.9%** (2109/2543). Все шаги идемпотентны, скриптами через `manage.py shell`.
- `MG_T04RELINK` — релинк 57 NULL-строк через `product_ref_index` (ставит только `product_id`; `name_canonical` не трогает, чтобы бренд #172 не протёк в рецепт). 51.9%→54.1%.
- `MG_T04SEED` — наполнение рубрикатора по выверенному воркшиту (порог freq≥3): создано **83 `Product`** (с категориями), **11 `ProductAlias`** (порядок слов: `Масло оливковое`→#43 и т.п.), **9 FOLD** (внутр. дубли: `Яичные белки`→`Яичный белок`, `Маслины`→`Оливки`, `Замороженный шпинат`→`Шпинат`, `Тыква запечённая`→`Тыква`, `Казеин`/`Протеин`→`Протеин сывороточный`), затем релинк **732** строк. Политики (консервы — отдельно, специи — свод к базе, крахмалы — раздельно) согласованы. 54.1%→82.9%.
- `MG_T04C` (**вариант C**, новые рецепты): поле `Product.source` (`manual|auto|import`, миграция `fridge/0013_product_source`); `rebuild_recipe_links(create_missing)` + guard `_is_seedable` (длина≥2, не мусор/число, валидная категория) + инлайн `get_or_create(Product, source='auto')`; `backfill()` с `create_missing=True` (покрывает bulk-импорт, минующий `post_save`); `signals.post_save` → `create_missing=True`. Известные варианты не дублируются (резолв через `product_ref_index` со seed-алиасами/фолдами). Ревизия: `mg_t04c_report.sh` (`source='auto'`).
Вторая часть (post_save на bulk) разобрана: `bulk_create` в legacy `migrate_recipes_db.py` минует `post_save` → покрыто `backfill(create_missing=True)`.
Verify (chat-73): linked 82.9%; NULL 434 (хвост freq<3 + 5 SKIP); `--verify` PASS; auto-товаров 0 (новых рецептов не сохраняли).

### T-05 — Несогласованность словаря единиц (упаковка/упак) · severity: low · CLOSED (MG_T05 + MG_T05CLEAN, chat-73)
Единицы-синонимы расщепляли размерности (`упак`≠`упаковка`, мн. формы кусочков), числовой мусор `'5'` в `unit`.
Решение: единый рантайм-нормализатор `_mg_norm_unit` (`apps/shopping/services.py`) — lower/trim/ё→е/схлоп пробелов + словарь написаний `_MG_UNIT_SYN` (`упак`→`упаковка`, `ломтика`→`ломтик`, `дольки`→`долька`, ложки/стакан/штука/грамм) + числовой мусор→'' + `зубчик`→`шт`; `_fr_base`/`_fr_unit_factor` прогоняются через него. Разные счётные единицы (`шт`/`упаковка`/`пучок`/`долька`) между собой НЕ сводятся; приблизительные (`щепотка`/`горсть`/`пучок`) изолированы и не вычитаются. `synonyms.yaml` рантайм не использует (только оффлайн-скрипты). `MG_T05CLEAN`: 2 строки `RecipeProduct` `unit='5'`→''.
Verify (chat-73): `--verify` PASS (11 кейсов норм + `_fr_base`); чистка применена.

### T-06 — Stale unlinked egg-строки в RecipeProduct · severity: low · CLOSED (chat-73)
Остаток после `MG_T06RELINK` (chat-72) проверен: unlinked egg-canon = **0**, целевой канон `#41 Яйца куриные` на месте. Доп. действий не требуется.

### T-02 — Бренд/составные имена холодильника не матчатся · severity: medium · CLOSED (не воспроизводится, chat-73)
Диагностика: `FridgeItem` без `product_id` = 5, нерезолвимых = 0; `normalize_alias` уже срезает бренд/кавычки (рецептный «Мёд» резолвится к #172 `Мед "Карельское разнотравье"`). Баг матчинга не воспроизводится. Остаток — брендовый `Product #172` — перенесён в **D-06** (data-quality).

### T-03 — Несовместимые единицы при вычитании (шт vs г) · severity: low · CLOSED (не воспроизводится/латентно, chat-73)
Диагностика: продуктов холодильника с рецептными линками = 4, конфликтов размерностей = 0 → на живых данных не воспроизводится. T-05 убрал ложные несовпадения по написаниям. Настоящий фикс `г`↔`шт` потребует таблицы «вес штуки на продукт» — зафиксировано как латентное (отдельный пункт при необходимости).

### T-08 — Обработка ошибок офлайн + синхронизация списков покупок · severity: medium · CLOSED (MG_T08 chat-74 + MG_T09 #2 chat-75)

**Фаза 1 (toggle «куплено/не куплено», LWW «последнее действие приоритет»):**
- **Backend — ✅ done/verified (chat-74).** `ShoppingItemToggleView.patch` идемпотентен (`MG_T08_idempotent`): `target==prev` → ранний возврат без побочек → безопасный реплей очереди. `ShoppingListItem` без `updated_at` → LWW на клиенте (дедуп по `listId:itemId`).
- **Web — ✅ done/verified (chat-74).** `hooks/useOnlineStatus.ts`, `utils/syncQueue.ts` (localStorage `mg_sync_queue_v1`, LWW по ts), `components/layout/SyncIndicator.tsx` (🟢/🟡/🔴), патчи `AppLayout.tsx` + `ShoppingPage.tsx`.
- **Mobile — ✅ ИСПРАВЛЕНО в chat-75 (MG_T09 #2).** Плохой результат chat-74 (`d1d8733`): очередь и connectivity-листенер жили в `ShoppingBloc` (per-tab) → при уходе с вкладки `close()` отменял подписку и терял in-memory очередь → возврат сети флашить нечем. Корень подтверждён вводом пользователя («уходил на другую вкладку»). Решение: вынесено в глобальный app-lifetime `OfflineToggleQueue` (`core/sync/offline_toggle_queue.dart`) — держит очередь + слушает `ConnectivityCubit` на уровне `main.dart`; `ConnectivityCubit`/`PendingSyncCubit` подняты в `main()` и провайдятся `.value`, очередь — `RepositoryProvider.value`. `ShoppingBloc` только enqueue’ит (офлайн/`isNetwork`) и ресинкает открытый список по `flushedListIds`. Файлы: `offline_toggle_queue.dart`(new), `main.dart`, `shopping_bloc.dart`, `shopping_list_screen.dart`.
  Verify (chat-75): пользователь подтвердил — офлайн-тоггл общего списка синхронизируется после ухода с вкладки и возврата сети ✓.

**Фаза 2 (частично закрыта, scope):** read-кэш списков/детализации реализован в **T-13 (MG_CACHE, chat-76)** — офлайн-просмотр + работа с открытым списком; reconnect-гонка устранена в MG_CACHE2. Остаётся: офлайн create/add-item; backend push/pull (sync-app пуст: `urls=[]`, `views`/`serializers` пустые, `SyncLog` мигрирован); приоритет специалиста (User↔Specialist); **персистентная очередь записи, переживающая kill приложения** (drift `SyncQueue` определена, но `AppDatabase`/`SyncService` — заглушки; текущая `OfflineToggleQueue` in-memory). TZ §5/§11.6/§15.3.

## Технический долг / инфраструктура

### D-01 — Backend CI (red) · OPEN — предсуществующий со времён MG_208; CI всегда red, не блокирует деплой. chat-79: `generator.py` тоже во flake8-долге (E501 на длинных строках `MG_STRAT2_ROLE`-вызовов `_place_s2(... component_role=...)`, F841 `fridge_ids` в `_generate_strategy3`). chat-80: добавились `import_telegram_recipes.py` и `mg_analyze_s1_repeats.py` — не проверялись flake8. Только стиль, на работу не влияет. Чинить — отдельной задачей (autopep8/black по всему backend ИЛИ смягчить flake8-правило, чтобы не падать на E2xx/W3xx/E501).
### D-02 — Mobile APK последнего green-run не верифицирован полностью · OPEN. chat-79: APK из Flutter CI `27622984567 ✓` собран; на устройстве НЕ проверены — селектор «Стратегия меню», скрытие 3/5 для s2/s3, генерация s2 (201) и s3.
### D-03 — Уборка бэкапов на сервере · severity: low · OPEN — `*.bak.MG_*`. chat-80 добавил: `*.bak.MG_DRINK.*`, `*.bak.MG_S1ANALYZE.*`, `*.bak.MG_TGIMPORT.*`. chat-79 добавил: `*.bak.MG_STRAT3_PLATEFORM.*`, `*.bak.MG_STRAT3_SELECT.*`, `*.bak.MG_STRAT3_CLEAN.*`, `*.bak.MG_STRAT3_ROLE.*`, `*.bak.MG_STRAT2_ROLE.*`, `*.bak.MG_STRAT_WEB.*`, `*.bak.MG_STRAT_MOBILE.*`. chat-78: `*.bak.MG_STRAT_PLATE.*`,`*.bak.MG_STRAT.*`,`*.bak.MG_STRAT3.*`,`*.bak.MG_STRAT3_PICK2.*`; chat-76: `*.bak.MG_CACHE.*`/`*.bak.MG_CACHE2.*`; ранее: `*.bak.MG_T09.*`(удалены)/`*.bak.MG_T10.*`,`*.bak.MG_T08*`,`*.bak.MG_T05.*`,`*.bak.MG_T04C.*`,`*.bak.MG_T07.*`,`*.bak.MG_B03.*`,`*.bak.MG_B10B11.*`,`*.bak.MG_B08.*`,`*.bak.MG_B09.*`, `web-dist.bak.*`. В chat-78 в `.gitignore` добавлен паттерн `*.bak.MG_*`.
### D-04 — Мусор/длинные имена в `Recipe.ingredients` · severity: low · OPEN.
### D-05 — DRF warnings DecimalField min/max · severity: trivial · OPEN — фонит в выводе `manage.py` (не влияет на работу).
### D-06 — Мусорные/брендовые имена в рубрикаторе (Product) · severity: low · OPEN — напр. #172 `Мед "Карельское разнотравье"`, #179 `масло растительное` (нижний регистр), #183 `какао в магазине на рынке`; свести к чистым канонам/алиасам при ревизии. Для авто-товаров (`source='auto'`) — `mg_t04c_report.sh`.
### D-07 — Разметка `Recipe.plate_component` · severity: medium · CLOSED (mg_seed_plate, chat-79) — авто-сид `food_group` + `dish_type` whitelist `{main,side,salad,breakfast_dish,snack}` → protein/carb/veg = **90/47/36** (173 рецепта); команда `manage.py mg_seed_plate --dry-run/--apply`, идемпотентно по `NULL`, в репо. Качество компонентов (составные блюда) → **T-15**.
### D-09 — Таблица символов нативного кода для Play · severity: low · OPEN (chat-82)
При загрузке бандла Play предупреждает: «объект содержит нативный код,
рекомендуем загрузить файл с отладочными символами». Публикацию не блокирует, но
без символов отчёты о нативных падениях в консоли показывают голые адреса вместо
названий функций. Включается в `mobile/menugen_app/android/app/build.gradle`
строкой `ndk { debugSymbolLevel = "SYMBOL_TABLE" }` в `defaultConfig`. Цена —
размер бандла. Сделать вместе со следующим релизом, отдельную сборку ради этого
не гонять.

### D-10 — Устаревший `pubspec.lock` мобильного приложения · severity: low · OPEN (chat-82)
Лок в репозитории есть и по замыслу (см. `.gitignore`) должен фиксировать версии
пакетов, но отстал: в нём `mobile_scanner 5.2.3` и вовсе нет
`flutter_local_notifications`. Сборкам это пока не мешает — при несовпадении с
`pubspec.yaml` pub переразрешает зависимости сам и переписывает лок у себя, — но
свою работу лок в таком виде не делает: он фиксирует не то, что собирается.
Заодно комментарий в `flutter_ci.yml` утверждает, что лок НЕ хранится в
репозитории; это неправда, и одно из двух мест надо поправить.
Решение принято: обновить вместе со следующим релизом (`flutter pub get` на
машине с Flutter, лок закоммитить, комментарий в workflow исправить).

### D-08 — Вынос `macro_roles` (категория→роль) в админку · severity: low · OPEN (chat-78) — сейчас Python-константа `apps/menu/macro_roles.py`; кандидат — поле `ProductCategory.macro_roles` (`ArrayField`/CSV) для редактирования без деплоя. + точечные product-override (горький шоколад=жир, молоко и т.п.).

## Закрытые
- **D-07** — разметка `Recipe.plate_component` через `mg_seed_plate` (food_group+dish_type whitelist → 90/47/36) (chat-79).
- **T-13** — Mobile офлайн-кэш списков покупок: `ShoppingCache` (shared_preferences, write-through, TTL 7д) + фикс reconnect-гонки (ретрай flush + overlay pending в `_onDetail`) (MG_CACHE/MG_CACHE2, chat-76).
- **T-12** — Mobile офлайн-UX: дружелюбный текст сетевой ошибки + переформулирован баннер + скрытие тело-ошибки/snackbar при офлайне на вкладках и в Покупках (MG_T10/MG_T10b, chat-75).
- **T-11** — Фильтр «только некупленные» в списке, web+mobile (MG_T09 #4, chat-75).
- **T-10** — Счётчики списков в падах + backend `GET /shopping/counts/`, web+mobile+backend (MG_T09 #3, chat-75).
- **T-09** — Mobile: индикатор соединения под статус-баром (SafeArea) (MG_T09 #1, chat-75).
- **T-08** — Офлайн-синхронизация тоггла списков: backend идемпотентность + web localStorage-очередь (chat-74) + mobile глобальная `OfflineToggleQueue` (MG_T08/MG_T09 #2, chat-74→75).
- **T-04** — Канонизатор RecipeProduct: relink 57 + seed 83 товаров/11 алиасов/9 фолдов + вариант C (Product.source, inline `create_missing`, миграция fridge 0013); 51.9%→82.9% (MG_T04RELINK/MG_T04SEED/MG_T04C, chat-73).
- **T-05** — Единый рантайм-нормализатор единиц (`_mg_norm_unit`+`_MG_UNIT_SYN`) + чистка числового мусора в `unit` (MG_T05/MG_T05CLEAN, chat-73).
- **T-06** — Остаток egg-строк проверен = 0, действий не требуется (chat-73).
- **T-02** — Не воспроизводится; брендовый остаток #172 → D-06 (chat-73).
- **T-03** — Не воспроизводится/латентно; настоящий фикс г↔шт = таблица «вес штуки» (chat-73).
- **T-07** — Per-item категория холодильника без мутации общего `Product` (FridgeItem.category_fk + effective_category, fill-only resolve, миграция 0012) (MG_T07, chat-72).
- **T-01** — Слияние дубля Product «Майонез» (id=44→122) + seed alias, миграция fridge 0011 (MG_T01_MAYO, chat-72).
- **B-03** — Редактирование продуктов холодильника: backend `update()` + web `EditFridgeItemModal` + mobile `edit_fridge_item_sheet` (MG_B03, chat-71); APK подтверждён на устройстве (chat-72).
- **B-08** — Mobile: add-bar добавления товара в edit-mode детализации списка (MG_B08, chat-71).
- **B-10** — Mobile: список появляется сразу после создания (reload в `_onCreate`) (MG_B10, chat-71).
- **B-11** — Mobile: toggle «покупка» не сбрасывает скролл (in-place update) (MG_B11, chat-71).
- **B-09** — Пикер меню: реально подключён лейбл `{creator_name} DD.MM–DD.MM` (backend `creator_name` + web/mobile), восстановлен B-06 (MG_B09, chat-69).
- **B-07** — Веб: добавление товара в edit-mode + закреплённый add-bar + внутренний скролл + один «Готово» (MG_SHOPADDEDIT/2/3, chat-68).
- **B-06** — Пикер меню → `{creator_name} DD.MM–DD.MM`, web (MG_MENULABEL chat-68 номинально / MG_B09 chat-69 фактически).
- **B-05** — Убран импорт ai_text/csv (MG_NOIMPORT, chat-67).
- **B-04** — Алиасы Фета/Куриное филе (MG_ALIASDEDUP, chat-67).
- **B-02** — Категория при add-fridge (MG_B02CAT, chat-67).
- **B-01** — Дедупликация «Яйца» (MG_PRODALIAS, chat-66).
