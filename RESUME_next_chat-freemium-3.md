# RESUME — следующая сессия (freemium-3: дневник во freemium + каталог КБЖУ)

Дата: 2026-06-26
Рабочая ветка: `claude/clever-goodall-dov0ly` (всё слито в `main` fast-forward)
HEAD: `416b9e3` (он же `origin/main`)

---

## 0. ⚠️ ЧИТАЙ ПЕРВЫМ — за что справедливо материли в этой сессии (НЕ ПОВТОРЯТЬ)

1. **«ТЫ МОЖЕШЬ ДЕРГАТЬ FLUTTER САМА!»**
   APK собирается через GitHub Actions, workflow **`Flutter CI`** (`.github/workflows/flutter_ci.yml`).
   Триггер — **push в `main`** (или `develop`), фильтр путей `mobile/**`. Значит чтобы
   собрать APK — **просто `git push` в `main`** (я это умею и должен делать сам).
   - `workflow_dispatch` ассистенту НЕ доступен: дисптач отдаёт **403 Resource not
     accessible by integration**. Не уводить юзера в «запусти вручную в UI» — пушить в main.
   - Читать логи/статусы/артефакты CI через `mcp__github__actions_*` я МОГУ (read works).
   - Два job'а: `flutter-test` (`flutter test`) → затем `build-apk` (`flutter build apk --debug`,
     компилирует ВСЁ приложение → ловит любую ошибку Dart) → артефакт `menugen-debug-apk-<run_number>`.
   - Flutter pin **3.22.0**. Локально `flutter analyze` НЕ гонять (Flutter в окружении нет,
     версия другая) — проверка только через CI/сборку APK.

2. **«Твой анализ ситуации — хуйня»** (поиск продуктов ничего не находил).
   Реальная причина была НЕ в формах слова, а в **пагинации DRF**: `ProductSearchView`
   (ListAPIView) отдаёт `{count,next,previous,results:[...]}`, а фронт ждал голый массив →
   выпадашка всегда пустая. **Урок: сначала проверь фактическую форму ответа (пагинация!),
   а не теоретизируй.** Фикс — распаковка `results` в `fridgeApi.searchProducts`.

3. **Дедуп/синонимы НЕ должны схлопывать разные продукты.**
   Юзер (справедливо) забраковал слияния: «Фарш говяжий»→«Фарш», «Телятина»→«Говядина»,
   а также авто-синоним «Мука пшеничная»→«Мука». Принцип навечно:
   **синоним = только истинный эквивалент** (ед./мн. число, порядок слов, сокращения,
   опечатки). РАЗНЫЕ виды/жирности (виды фарша/муки/орехов/грибов; телятина≠говядина;
   Творог 5%≠9%) — отдельные продукты с разным КБЖУ. Дедуп использует только выверенные
   синонимы (`ProductAlias.source != 'auto'`), авто-синонимы — НЕ для слияния.

4. **«пункт повис»** — длинные AI-прогоны (десятки чанков по 20) идут МИНУТЫ и без вывода
   выглядят зависшими. Решение применено: печать прогресса по чанкам + flush. AI-команды
   идемпотентны и сохраняют по ходу — Ctrl+C безопасен, повторный запуск догоняет остаток.

5. **Не уводить в ручные шаги, если можешь сделать сам** (коммит/пуш/CI/чтение логов).

---

## 1. Что сделано в этой сессии (всё в `main`, 10 коммитов)

Тема: **включить Дневник питания во freemium** (web + mobile) + навести порядок в
каталоге продуктов (КБЖУ, поиск, дедупликация).

| Commit | Что |
|--------|-----|
| `75dd080` | **Web:** дневник открыт free + 3-вкладочное добавление (Рецепт/Продукт/Вручную) |
| `e395c1c` | `seed_product_kbju` — КБЖУ сид-продуктам (справочник) |
| `1d9f7dd` | **Фикс поиска продуктов** (пагинация) + расширение каталога + синонимы-поиск |
| `aaf0f13` | `dedup_products` — детерминированное слияние дублей |
| `2197258` | Убраны ошибочные синонимы/слияния (фарш/телятина/мука), дедуп игнорит auto-алиасы |
| `988dae6` | `fill_kbju_ai` — GPT-заполнение КБЖУ для хвоста |
| `8da42a8` | `fill_kbju_ai` — прогресс по чанкам |
| `6179b65` | `dedup_products_ai` — GPT-дедуп вариантов названий (порядок слов/сокращения) |
| `7665099` | dedup_products_ai — выживает курируемый сид-продукт, а не AI-форма |
| `416b9e3` | **Mobile:** дневник во freemium + те же 3 вкладки добавления |

### 1.1 Backend — открытие дневника (freemium)
- `apps/diary/views.py` — снят `IsFamilyPremiumOrReadOnly` с 6 view'ов (List/Create, Detail,
  Stats, ImportFromMenu, WaterLog, Copy); осталось `IsAuthenticated` (+ `IsDiaryEntryOwner`
  на Detail). Реальная авторизация владельца/HEAD не тронута.
- `apps/fridge/views.py` — `ProductSearchView` открыт free (`IsAuthenticated`), т.к. это общий
  каталог КБЖУ для дневника, а не данные холодильника. Плюс поиск **по синонимам**:
  матч `Q(name__icontains=q) | Q(aliases__alias_norm__icontains=normalize_alias(q))`.
- `apps/recipes/serializers.py` — в API рецепта добавлены НАДЁЖНЫЕ числовые поля
  `NUTRITION_NUMERIC_FIELDS` = `portion_g, kcal, proteins, fats, carbs, *_per_100g`
  (в List/Detail/Write). Нужны для пересчёта в граммы (в обход рассогласованного `nutrition` JSON).
- Тесты переписаны под freemium: `apps/diary/tests/test_mg_606b_premium_or_readonly.py`,
  `apps/diary/tests/test_mg_605c_permissions.py` (класс TestFreemiumAccess),
  `apps/fridge/tests/test_mg_606c_premium_gate.py` (product-search 403→200).

### 1.2 Web (`web/menugen-web`, React CRA)
- `hooks/usePremium.ts` — `/diary` убран из `PREMIUM_PATHS` (остался `/dashboard`, `/fridge`).
- `App.tsx` — `diary` больше не `PremiumRoute`. `Sidebar.tsx` — «Дневник» `premium:false`.
  `Sidebar.test.tsx` — обновлён под free-навигацию (Главная/Холодильник скрыты для free).
- `components/diary/AddDiaryEntryModal.tsx` — переписан в **3 вкладки**:
  - **Рецепт**: поиск `/recipes/?search=` (дебаунс), КБЖУ из `*_per_100g` по граммам;
    нет `kcal_per_100g` → fallback на порции (на порцию × N).
  - **Продукт**: поиск `/fridge/products/search/?q=` (распаковка `results`!), КБЖУ из
    `calories_per_100g` + `nutrition` по граммам.
  - **Вручную**: прежнее поведение.
  Хранение: итоговые КБЖУ как `{value,unit}` + `quantity:1`, имя = «<название>, N г/порц.».
- `api/fridge.ts` — `searchProducts(q)` распаковывает пагинацию (`results`). **(КЛЮЧЕВОЙ ФИКС)**
- `api/recipes.ts` — `list({search, page_size})` уже был.
- `types/index.ts` — в `Recipe` добавлены числовые КБЖУ-поля + `portion_g`.
- `components/recipes/RecipeEditModal.tsx` — поле «Вес порции, г» (`portion_g`) в редактор.

### 1.3 Mobile (`mobile/menugen_app`, Flutter 3.22)
- `core/widgets/main_shell.dart` и `core/router/app_router.dart` — `/diary` убран из
  `_premiumOnlyPaths` (остался `/fridge`). Дневник виден в нижней навигации и не редиректит на `/paywall`.
- `features/diary/screens/diary_screen.dart` — `_AddManualDialog` переделан в **3 вкладки**
  (Рецепт/Продукт/Вручную, `TabController`). Поиск через `bloc.apiClient` (дженерик
  `apiClient.get('/recipes/?search=')` / `'/fridge/products/search/?q='`, распаковка `results`).
  Возвращает тот же `_ManualEntry` (итоговые КБЖУ + quantity:1) → существующий конвейер
  `DiaryAddManualRequested` не менялся. Добавлен `import 'dart:async'`.
- APK собран CI: **`menugen-debug-apk-119`** (run 28249656342). build-apk = success
  (приложение скомпилировалось). ⏳ Юзер ещё не подтвердил проверку на устройстве.

### 1.4 Данные на ПРОДЕ — что РЕАЛЬНО применено (всё выполнено вручную на сервере)
Команды прогнаны на проде в этой сессии:
- `seed_product_kbju` — справочник **203 позиции** (136 базовых + 67 доп.), проставил КБЖУ
  сид-продуктам + создал недостающие + завёл синонимы (после фикса — без ошибочных).
- `fill_kbju_ai --apply` — GPT-заполнение хвоста (несколько прогонов, идемпотентно).
- `dedup_products --apply` — детерминированное слияние (Огурец→Огурцы и т.п.).
- `dedup_products_ai --apply` — GPT-дедуп: **удалено 62 дубля**, перепривязано 292 ссылки
  в рецептах + 34 в покупках.
- **Итоговое состояние каталога: всего 1284 продукта, с КБЖУ 1046 (~81%), без — 238**
  (остаток — несъедобное + мусорные фразы-ингредиенты).

---

## 2. Management-команды (apps/fridge/management/commands) — справочник
Все идемпотентны, по умолчанию безопасны. Логика слияния вынесена в `apps/fridge/dedup.py`
(`merge_product_into`, `has_kbju`).

- **`seed_product_kbju`** [`--dry-run`] [`--force`]
  Проставляет КБЖУ (плоский `nutrition` на 100 г: calories/proteins/fats/carbs) + `calories_per_100g`
  по выверенному справочнику (`KBJU` 136 + `NEW_PRODUCTS` 67). Создаёт недостающие базовые
  продукты. Заводит синонимы (`ALIASES`) и УДАЛЯЕТ ошибочные (`REMOVE_ALIASES`). По умолчанию
  не трогает продукты с уже непустым `nutrition` (не затирает OFF-данные); `--force` перезапишет.
- **`fill_kbju_ai`** [`--apply`] [`--limit N`] [`--batch N`]
  GPT-оценка КБЖУ для продуктов с пустым `nutrition`. Несъедобное (`food:false`) пропускает,
  значения валидирует (ккал 0..1000, Б/Ж/У 0..100). Прогресс по чанкам. Зависит от env
  `AI_PROVIDER/AI_API_KEY/AI_FOLDER_ID` (на проде настроено — тот же клиент, что канонизация ингредиентов).
- **`dedup_products`** [`--apply`]
  Детерминированный дедуп: канон через `ProductAlias` (source != auto) + совпадение
  нормализованного имени. Приоритет канона: есть КБЖУ > is_seed > min id. По умолчанию dry-run.
- **`dedup_products_ai`** [`--apply`] [`--limit N`] [`--batch N`] [`--show N`]
  GPT-дедуп вариантов названий (порядок слов/сокращения/опечатки). AI приводит к канон-форме,
  СОХРАНЯЯ различающие признаки (жирность/вид/сорт). Группа сливается тем же `merge_product_into`.
  Выживает курируемый сид-продукт (is_seed > есть КБЖУ > имя==канон > id). По умолчанию dry-run,
  **всегда смотреть план перед `--apply`**.

---

## 3. Что осталось / возможные следующие задачи
- ⏳ **Проверить APK `menugen-debug-apk-119`** на free-юзере: вкладка «Дневник» видна,
  заходит без paywall; «Добавить» → 3 вкладки с поиском и авто-КБЖУ.
- ⏳ **GC мусорных «продуктов»-фраз** из ингредиентов рецептов («В пакете», «Выкладываются в
  формы…», «Других фруктов», «Салатный», «курица целая у веры разделанная на куски»). Отдельная
  команда по паттернам (длинные фразы, глаголы, служебные слова). Договорились — позже.
- ⏳ Остаток ~238 продуктов без КБЖУ — преимущественно несъедобное/мусор; добивать смысла мало.
- Хвосты из прошлых RESUME (не делалось): дружелюбный текст лимита членов семьи на странице Family.

---

## 4. ПАМЯТКА — сервер/деплой/CI (актуально)
```
Сервер:        /opt/menugen  (ssh у ассистента НЕТ — команды деплоя выполняет юзер вручную)
Backend:       Docker (docker compose), на хосте :8003 (8003->8000)
Публичный:     http://31.192.110.121:8081/  (host-nginx, /api/ -> :8003)
Web:           НЕ в Docker. CRA -> /opt/menugen/web-dist/ -> host-nginx.
               .env (gitignored): web/menugen-web/.env, REACT_APP_API_BASE_URL=http://31.192.110.121:8081/api/v1
Тестовый free: free@menugen.test / 1234!

Деплой backend (миграций в этой ветке НЕТ):
  cd /opt/menugen; BR=claude/clever-goodall-dov0ly; git fetch origin "$BR"
  git show origin/$BR:scripts/deploy_backend.sh > /tmp/deploy_backend.sh
  sed -i 's/\r$//' /tmp/deploy_backend.sh
  BRANCH=$BR ASSUME_YES=1 bash /tmp/deploy_backend.sh
Деплой web:  аналогично scripts/deploy_web.sh (BRANCH=$BR bash ...), потом Ctrl+Shift+R в браузере.
  (health-check GET /api/v1/ -> 404 — это НОРМА для nginx, бэк жив на :8003.)

APK: push в main -> Flutter CI -> артефакт menugen-debug-apk-<run_number>.
  Скачать: gh run download <RUN_ID> -n menugen-debug-apk-<N>

Стек: Django 4.2/DRF/PG15/Redis+Celery; React CRA; Flutter 3.22.
CI бэка: flake8 max-line-length=120 (.flake8: ignore E203,W503), black -l 120, isort --profile black.
  ВАЖНО: flake8 считает СИМВОЛЫ, не байты — кириллица/box-drawing раздувают `awk length`;
  проверяй длину через python len(), а не awk.
```

### Грабли из прошлых RESUME (по-прежнему в силе)
- Линтер/хук на `claude/*` ветке может откатить файлы к HEAD — проверяй `git status` после правок
  (в этой сессии не мешал, но помни).
- `REACT_APP_API_BASE_URL`: без `.env` в бандл вшивается localhost:8000 → логин ломается.
  Всегда собирать через `scripts/deploy_web.sh` (он проверяет вшитый URL).
- Кэш `index.html` → после web-деплоя жёсткий refresh / инкогнито (есть `scripts/nginx_no_cache_index.sh`).
- **КБЖУ рецептов в БД рассогласованы** между импортёрами (telegram: на порцию, вложенный
  protein/fat; xlsx: на 100 г, плоский). Поэтому для граммовки берём числовые колонки
  `*_per_100g` / per-порционные, а НЕ `nutrition` JSON.
- Модель идентификатора (claude-opus-4-8) НЕ писать в коммиты/PR/код — только в чат.

---

## 5. Как ПРАВИЛЬНО стартовать новую сессию
```bash
git fetch origin
git checkout claude/clever-goodall-dov0ly
git pull origin claude/clever-goodall-dov0ly
git log --oneline -3   # ожидаемый HEAD: 416b9e3 (или новее)
```
Затем прочитать ЭТОТ файл (`RESUME_next_chat-freemium-3.md`) и при необходимости предыдущие
(`RESUME_next_chat-freemium-2.md`, `RESUME_next_chat-freemium.md`).
Первым делом уточнить у пользователя: проверен ли APK `menugen-debug-apk-119` на устройстве,
и какую из задач §3 берём.

Запуск тестов бэка (на сервере):
  docker compose exec -T backend pytest apps/fridge/tests/ apps/diary/tests/ -q
```
