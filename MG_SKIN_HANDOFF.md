# MG_SKIN — Handoff (резюме для следующей сессии)

**Дата:** 2026-06-22
**Ветка разработки:** `claude/nifty-rubin-h90pfg`
**Последний коммит:** `de90bfc`
**Следующая сессия:** логика работы **Дневника** и **Дашборда** (см. раздел в конце).

---

## 🔴 ГЛАВНОЕ ПРАВИЛО РАБОТЫ (рабочее соглашение)

**ВЕСЬ КОДИНГ — ТОЛЬКО ПО ЯВНОЙ ОТМАШКЕ ПОЛЬЗОВАТЕЛЯ.**

- Картинка/макет/описание = **ориентир для обсуждения**, а НЕ команда «иди верстай».
- Перед любыми правками кода: исследуй → предложи план/развилки → **дождись «делай»/«поехали»/«го»**.
- Сначала точечно проговорить, **что меняем, а что оставляем**. Только потом — код.
- Исключение, которое НЕ требует отдельной отмашки: правки, которые пользователь
  явно попросил в текущем сообщении (например «сделай X», «поправь Y»).
- Коммит и пуш — после выполнения согласованной задачи (workflow ниже).

---

## 🚀 Как правильно начать новую сессию (чек-лист)

1. **Прочитать этот файл целиком** (`MG_SKIN_HANDOFF.md`) — он канон.
2. Убедиться в ветке и подтянуть свежее:
   ```
   git checkout claude/nifty-rubin-h90pfg
   git pull origin claude/nifty-rubin-h90pfg
   ```
   (облачное рабочее дерево — на этой ветке; см. инварианты деплоя ниже).
3. **Не начинать кодить.** Дождаться вводных пользователя (макет/комментарии)
   и явной отмашки. Сначала — исследование кода + обсуждение развилок.
4. Помнить про ограничения окружения (Flutter SDK нет, CI триггерится вручную).

Если пользователь кидает изображение экрана — это «обсудим, что делаем», а не ТЗ
на немедленную вёрстку.

---

## 🧱 Инфраструктура скинов (фундамент, готов — НЕ переизобретать)

- **Веб — токены:** `web/menugen-web/src/index.css` (CSS-переменные `--c-*`,
  RGB-каналы для альфы). Скины `:root[data-skin='main']` и `[data-skin='second']`.
- **Веб — Tailwind:** `tailwind.config.js` маппит токены в утилиты
  (`bg-surface`, `text-muted`, `border-border`, `bg-primary`, `stroke-primary`…).
  Legacy-алиасы: `tomato→primary`, `rice→bg`, `chocolate→text`.
- **Веб — переключение:** `src/theme/skins.ts`, `components/ui/SkinSwitcher.tsx`.
- **Веб — UI-примитивы:** `components/ui/` — `Card`, `Button`, `Input`, **`Ring`**
  (круговой прогресс, токен-driven, новый в этой сессии).
- **Мобайл (Flutter):** `mobile/menugen_app/lib/core/theme/` —
  `app_theme.dart` (палитры `kMainPalette`/`kSecondPalette`, `AppTokens`),
  `app_skin.dart`, `skin_selector.dart`, `theme_cubit.dart`.
  Доступ из виджетов: `context.cs` (ColorScheme), `context.tokens`
  (`surfaceAlt`, `textSecondary`, `border`, `accent`).
- **Правило редизайна:** только токены (`bg-surface`/`context.tokens`…),
  никаких литералов цвета — тогда оба скина работают автоматически.

---

## ⚙️ Инварианты окружения и деплоя (важно, выстрадано — НЕ нарушать)

### Топология сервера (`/opt/menugen`)
| Что | Где |
|---|---|
| Веб-фронт (раздаёт nginx) | **`/opt/menugen/web-dist/`** — статика, не зависит от ветки |
| Исходники веба | `/opt/menugen/web/menugen-web/` |
| Backend | живёт в `/opt/menugen` (Docker volume `./backend:/app`, `runserver`) на ветке **`main`** |
| URL фронта / API | `http://31.192.110.121:8081/` , API `…/api/v1` |

### Деплой веба (`scripts/deploy_web.sh`) — **worktree, backend не трогаем**
- Раньше деплой делал `git checkout <ветка-фронта>` всей репы → подменял и backend
  (модель `ui_skin`/миграция 0006 расходятся с БД на `main`) → **ломался вход**.
- Сейчас скрипт собирает фронт из `origin/<branch>` в **изолированном git worktree**
  (`/tmp/mg-web-build`), основное дерево остаётся на `main` (backend цел).
- **`.env` фронта в `.gitignore`** → скрипт копирует его из основного дерева в worktree
  (без него CRA берёт `localhost:8000` и вход ломается). Плюс пост-проверка: если в
  бандле остался `localhost:8000` — деплой падает ДО касания `web-dist`.
- **Запуск (не переключая ветку основного дерева):**
  ```
  cd /opt/menugen
  git fetch origin claude/nifty-rubin-h90pfg
  git show origin/claude/nifty-rubin-h90pfg:scripts/deploy_web.sh > /tmp/deploy_web.sh
  chmod +x /tmp/deploy_web.sh
  /tmp/deploy_web.sh
  ```
- **Откат фронта:** бэкапы в `/opt/menugen/backups/web-dist.tar.gz.bak_*`.
- **CRLF-грабля:** если скрипт ругается `env: 'bash\r'` — `sed -i 's/\r$//' файл`.

### Деплой backend (`scripts/deploy_backend.sh`) — **аддитивно, обратимо** ✅ ОБКАТАН
- Та же философия, что у web: код берётся из ветки в изолированном worktree и
  **синкается ТОЛЬКО `backend/`** (через `rsync`, а если его нет — fallback на
  `tar`; `media/` сохраняется). Основное дерево на `main` не переключается.
- Перед изменениями: **бэкап БД** (`pg_dump`→`backups/db.sql.gz.bak_*`) и
  **кода** (`backups/backend.tar.gz.bak_*`). Печатает `migrate --plan`, спрашивает
  подтверждение, мигрирует, рестартит `backend`+`celery`+`celery-beat`,
  health-check `GET /api/v1/` с ретраями (~40с).
- **Запуск:**
  ```
  cd /opt/menugen
  git show origin/claude/nifty-rubin-h90pfg:scripts/deploy_backend.sh > /tmp/deploy_backend.sh
  sed -i 's/\r$//' /tmp/deploy_backend.sh; chmod +x /tmp/deploy_backend.sh
  /tmp/deploy_backend.sh
  ```
- **Грабли (выстраданы):** на сервере **нет `rsync`** (есть tar-fallback);
  `runserver` поднимается дольше пары секунд → ранний health-check давал **ложный
  502** (исправлено ретраями). При деплое прод впервые догнал миграции ветки
  (`users.0006 ui_skin`, `users.0007 is_managed`, `fridge.0014`).
- **Порядок выката:** СНАЧАЛА backend (эндпоинты/миграции), ПОТОМ web — иначе
  новые web-кнопки получают 404. См. `DEPLOY_backend.md`.

### Mobile (Flutter)
- **Flutter SDK в облачном окружении НЕТ** → `flutter analyze`/`test`/`build`
  локально не прогнать. Код вычитывается вручную; финальная валидация — сборка APK.
- **Flutter CI** (`.github/workflows/flutter_ci.yml`) триггерится только на
  `main`/`develop` или **вручную** (`workflow_dispatch`). На фичеветку авто-запуска нет.
- Запуск из интеграции (MCP) **запрещён (403)** → APK собирает **пользователь вручную**:
  GitHub → Actions → «Flutter CI» → Run workflow → ветка `claude/nifty-rubin-h90pfg`.
  Артефакт `menugen-debug-apk-<n>` (API_BASE_URL зашит в workflow — вход работает).

### Git / процесс
- Разработка и пуш только в `claude/nifty-rubin-h90pfg` (`git push -u origin <branch>`).
- PR не создавать без явной просьбы.
- Бэкенд-долг: **CI / Backend Lint** на ветке падает независимо (предсуществующий
  долг), на наши web/mobile коммиты не реагировать. Web CI и Flutter CI — зелёные.

---

## ✅ Сделано в сессии «логика» (коммиты `bf6a0a2` → `de90bfc`) — В ПРОДЕ

Backend и web **задеплоены в прод** (`deploy_backend.sh` + `deploy_web.sh`).
Mobile-части едут со следующим APK (Flutter CI запускается по `pull_request`
автоматически — из ветки открыт PR; ручной `workflow_dispatch` запрещён 403, но и
не нужен).

1. **Sharing/инвайт — email регистронезависимо** (`bf6a0a2`, backend): поиск
   пользователя по `email__iexact` (+strip) в `shopping/serializers.py`
   (`resolve_user`) и `family/views.py` (инвайт). `I.User@…` == `i.user@…`.
   ⚠️ **Логин остался регистрозависимым** (см. бэклог B — отдельная задача).
2. **Дневник — импорт из меню дропдауном** (`62c2af3`, **mobile**): в
   `diary_screen.dart` `_ImportMenuDialog` вместо ввода «ID меню» — загрузка
   `/menu/` + `DropdownButtonFormField` (как в `shopping_create_sheet.dart`).
   Web это уже умел (`ImportMenuModal.tsx`).
3. **Списки покупок → холодильник** (`e8af641`, backend+web+mobile): явное
   действие «❄ В холодильник». `FridgeItem.source_shopping_item` (FK→
   `shopping.ShoppingListItem`, миграция `fridge.0014`). Эндпоинт
   **`POST /shopping/lists/<id>/add-to-fridge/`** (body `item_ids?`, идемпотентно).
   Toggle uncheck позиции «в холодильнике» отдаёт **409** пока не передан
   `remove_from_fridge=true` (тогда удаляет связанный `FridgeItem`). Сериализатор
   отдаёт **`in_fridge`**.
4. **Непищевое НЕ в холодильник** (`6726267`, backend+web+mobile): категории
   `pets` (корма), `household` (быт.химия), `hygiene` (гигиена) исключены.
   `shopping/services.py`: `NON_FOOD_CATEGORY_SLUGS` + `is_fridge_eligible()`.
   Сериализатор отдаёт **`fridge_eligible`**; кнопка показывается только при
   наличии купленной пищевой позиции не в холодильнике.
5. **Член семьи без приглашения (managed)** (`a0aa39a`, backend+web+mobile):
   для детей без устройств / тех, кого ведёт специалист. **`User.is_managed`**
   (миграция `users.0007`). **`POST /family/members/create-managed/`** (глава/
   admin): создаёт User без логина (email/phone пусты, unusable password) +
   Profile + членство, с лимитом тарифа. **`POST /family/members/<id>/
   attach-account/`**: добавляет email/phone (+пароль), снимает `is_managed` →
   появляется вход. Сериализатор отдаёт **`is_managed`**. UI: режим «Пригласить /
   Без приглашения», метка «без входа», действие-ключ для привязки логина.
6. **Деплой** (`2c3bad8`→`d554582`→`de90bfc`): `scripts/deploy_backend.sh` +
   `DEPLOY_backend.md` (см. инварианты выше).

## ✅ Что сделано в сессии вёрстки (коммиты `3382f2d` → `727da30`)

### Веб
- **Дашборд-редизайн** (`3382f2d`): health-tracker сетка 2/3 + 1/3 на токенах —
  шапка с поиском, промо-карточка, недельный sparkline активности, БЖУ-итог,
  приёмы из дневника, недельный календарь, кольцо «бюджет калорий», питьевой режим.
  Новый примитив `components/ui/Ring.tsx`. Канва расширена до `max-w-7xl`
  (`AppLayout.tsx`). Источники: профиль (цели), `diary.stats`/`diary.list`/вода.
- **Деплой-скрипт** (`923aa44`→`a210aa3`→`207e57d`→`7206bac`): см. инварианты выше.

### Мобайл — Меню (`menu_screen.dart`, `menu_matrix.dart`, `menu_summary_card.dart`)
- **Матрица «приёмы × дни»** (`99fce3c`, `123cec9`): слева липкая колонка приёмов
  (строки по типу плана 3/5), горизонтально-скроллящиеся колонки-дни (липкая строка
  дат сверху), ячейка = крупное фото + бейдж `+N`, тап → лист приёма (карусель).
  Сводка КБЖУ за выбранный день. Компактный AppBar (44). «Сгенерировать» —
  перетаскиваемая кнопка. Пустых слотов нет (бэкенд add/remove не нужен).

### Мобайл — Списки покупок (`shopping_list_screen.dart`)
- (`bb1cbfe`): AppBar 44; вкладки — горизонтальные чипы (слова целиком, не
  переносятся) со счётчиками в закрашенных кружочках; карточки списков в рамке;
  понятный статус (зелёная галочка «Всё куплено» / «Осталось купить N товаров» /
  «Пока пусто»; убрали путающее «Пустой»).

### Мобайл — Детали списка (`shopping_detail_screen.dart`)
- (`7113356`): **сворачиваемые товарные группы**. По умолчанию всё свёрнуто;
  состояние per-list персистится через **SharedPreferences** (`shopping.expanded.<listId>`).
  В заголовке группы: бейдж количества + «куплено N · осталось M» / «Всё куплено».
  Счётчики из полного списка (корректны при фильтре «только некупленные»).

### Мобайл — Дневник (`diary_screen.dart`, `diary_stats_card.dart`, bloc, model)
- (`c42b370`): AppBar 44; вода сворачивается в строчку; календарь на русском
  (`locale: 'ru'`), минимальная недельная лента, выбор месяца/недели/даты в модалке
  по кнопке «Календарь»; КБЖУ-карточка втрое ниже (две строки План/Факт);
  «+Добавить» — перетаскиваемая (новый общий виджет
  `core/widgets/draggable_action_button.dart`).
- (`9559eba`): **«План» как дерево по приёмам** — мастер-чекбокс (весь план) +
  трёх-состояточные чекбоксы веток + сворачивание; листья со своим чекбоксом и
  свайп-удалением. **КБЖУ-карточка «прилеплена»** (фикс-хедер над скроллом).
  **Позиция списка сохраняется при check/uncheck** (отметка обновляет статистику
  на месте, без `DiaryLoading`; у списка `PageStorageKey`). Добавлены событие
  `DiaryMarkManyEatenRequested` и `DiaryEntry.copyWith`.
- (`727da30`): **устойчивость к 429** (DRF троттлинг). `ApiException.isThrottled`;
  `_patchEaten` ретраит на 429 (бэкофф, до 4 попыток); батч разносит запросы ~150мс.

---

## ⏳ Открытые вопросы / бэклог

0. **Задача B — регистронезависимый ЛОГИН** (системно). Сейчас починен только
   поиск пользователя при sharing/инвайте (`email__iexact`). Сам вход по-прежнему
   регистрозависим: `LoginSerializer`→`authenticate(username=email)` →
   `ModelBackend` ищет `email=` точно; `RegisterSerializer.create` пишет email
   «как ввели» (без `normalize_email`). Корневой фикс: нормализовать email при
   регистрации в нижний регистр + регистронезависимый вход + миграция данных с
   разбором возможных дублей (уникальность email в БД регистрозависимая). Требует
   деплоя backend. Согласовано отложить отдельной задачей.
1. **Backend throttle `user: 100/min`** (`backend/config/settings.py`) — низковато
   для интерактива. Правильно поднять до ~`600/min`. Теперь есть
   `scripts/deploy_backend.sh` → можно выкатить точечно. Сейчас закрыто клиентским
   ретраем.
2. **Персист свёрнутости** где ещё не сделан: дневник (вода, ветки приёмов), меню.
   Паттерн — SharedPreferences (как в покупках). Делать по запросу.
3. **Дефолт свёрнутости** веток дневника сейчас «развёрнуто» — обсудить.
4. **Second-скин** — рабочее приближение, нужна точная подгонка под референс.
5. **Логотип** — ассета нет; слоты размечены (web-сайдбар, web-логин, mobile-логин).
6. **`DraggableActionButton`** — общий виджет; экран «Меню» пока использует свою
   приватную копию (можно мигрировать на общий по случаю).

---

## 🔧 Проверки перед коммитом

**Веб** (есть локально, прогонять):
```
cd web/menugen-web
node_modules/.bin/tsc --noEmit                                     # типы → 0
CI=false npm run build                                             # сборка → 0
CI=true npx react-scripts test --watchAll=false --passWithNoTests  # тесты
```
(зависимости: `npm ci --legacy-peer-deps` — флаг обязателен из-за конфликта
`@hookform/resolvers`).

**Мобайл:** локально не собрать (нет Flutter SDK). Перед коммитом — ручная вычитка
+ баланс скобок; финальная валидация на **Flutter CI** (запускается по PR авто).

**Backend:** полный тест-стек/БД в облаке не развёрнут → перед коммитом
`python -m py_compile` изменённых файлов + вычитка; финальная валидация — на
сервере при деплое (`migrate --plan` показывает план до подтверждения).

---

## 🎯 СЛЕДУЮЩАЯ СЕССИЯ — логика Дневника и Дашборда

**Правило прежнее:** сначала исследовать → предложить план/развилки → дождаться
«делай». Картинка/описание = повод для обсуждения, не команда верстать.

Тема: **логика работы** (не вёрстка) экранов **Дневник** и **Дашборд**. Вёрстка
обоих уже была сделана ранее (дашборд — `3382f2d`; дневник mobile — `c42b370`/
`9559eba`). Теперь — поведение/данные.

**Карта кода (откуда стартовать):**
- Backend дневник: `backend/apps/diary/` — `views.py` (`DiaryStatsView`,
  `DiaryImportFromMenuView`, `DiaryCopyView`, `WaterLogView`), `models.py`
  (`DiaryEntry`: `is_planned`/`is_eaten`/`planned_menu_item`, `WaterLog`),
  `serializers.py`. Логика planned/actual/total — в `DiaryStatsView`.
- Web: `pages/Diary/DiaryPage.tsx` + `components/diary/*`
  (`AddDiaryEntryModal`, `CopyFromDayModal`, `ImportMenuModal`, `PrintDiaryModal`);
  дашборд — `pages/Dashboard/` (источники: профиль-цели, `diary.stats`/`diary.list`,
  вода), примитив `components/ui/Ring.tsx`.
- Mobile: `features/diary/` (`diary_screen.dart`, `widgets/diary_stats_card.dart`,
  bloc/model). Дашборд на mobile отдельного экрана нет (свериться при старте).

**Уже известные зацепки по логике (из этой сессии):**
- В `DiaryStatsView`: `planned` = записи с `is_planned`/`planned_menu_item`;
  `actual`/`total` = `is_eaten` ИЛИ запись без плана (manual). КБЖУ считается
  `_entry_nutrition` с учётом `quantity` (поддержка flat/строка/`{value}`).
- Throttle `user:100/min` низкий для интерактива (бэклог №1) — может влиять на
  частые отметки в дневнике; есть клиентский ретрай 429.
- Открытые из бэклога, относящиеся к дневнику: персист свёрнутости (вода/ветки),
  дефолт свёрнутости веток (№2/№3).

**Команда старта следующей сессии (выдать ассистенту):**
> Прочитай `MG_SKIN_HANDOFF.md` в корне. Продолжаем на ветке
> `claude/nifty-rubin-h90pfg`. Занимаемся **логикой работы Дневника и Дашборда**.
> Правило: весь кодинг только по моей явной отмашке — сначала исследуй и предложи
> план, дождись «делай». Не начинай верстать/править по картинке сам.
