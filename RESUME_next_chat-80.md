# RESUME — chat-80 → следующий чат (фокус: UI web + mobile)

**Проект:** menugen (GitHub `igorriazanovst-debug/menu-gen`)
**Ветка этой работы:** `claude/nifty-rubin-h90pfg` (НЕ `main`! см. ниже).
**Репо на сервере:** `/opt/menugen` (рабочая копия git; деплой отсюда).

---

## ⚠️ ГЛАВНОЕ ДЛЯ СТАРТА СЛЕДУЮЩЕГО ЧАТА
1. **Тема: UI веб и мобильной версии.** Конкретную задачу пользователь назовёт — дождаться. Ниже карта UI-кода и пайплайн деплоя, чтобы стартовать без разогрева.
2. **Ветка.** Вся работа chat-80 ушла в `claude/nifty-rubin-h90pfg` (push в неё, НЕ в `main`). Сервер `/opt/menugen` обычно на `main` — перед UI-работой проверить, на какой ветке сервер, и согласовать с пользователем (мержить в main / работать в feature-ветке).
3. **Проверить git:** `git -C /opt/menugen status --short` чисто; `git log --oneline -5`. Последние коммиты chat-80: `9d4c064` (settings), `e5f33cd` (BACKLOG.md), `69d7276` (changelog+xlsx), `59375af`/`d3a041a`/`9e3b687`/`7f602cd`/`c074315` (T-15: import + drink-removal + analyze).
4. **BACKLOG.md теперь В РЕПО** (`/home/user/menu-gen/BACKLOG.md`, раньше был только локально у пользователя). xlsx (`MenuGen_Backlog.xlsx`) — **legacy, не использовать**. Вести задачи в `BACKLOG.md`.

---

## Что сделано в chat-80 (T-15: повторяемость рецептов s1 — DATA, не UI)
Контекст для понимания, UI это не трогает:
- **MG_S1ANALYZE** — `mg_analyze_s1_repeats` диагностика повторов (синтетика N меню in-memory + таблица спроса N≥d/T).
- **MG_DRINK** — напитки убраны из `MEAL_COMPONENTS` s1 (`backend/apps/menu/generator.py`).
- **MG_TGIMPORT** — `import_telegram_recipes`: импорт рецептов tati_cooks; salad-пул 20→32.
- Открытый хвост → **T-17** (дополнить пулы salad +24 / snack +30 / bakery +1; нужен источник рецептов с КБЖУ). Это DATA, к UI-чату отношения не имеет.

---

## 🎯 КАРТА UI-КОДА (для следующего чата)

### Web (`/opt/menugen/web/menugen-web`, Create React App + TypeScript)
- **Страницы:** `src/pages/<Feature>/...` — `Shopping/ShoppingPage.tsx`, `Fridge/FridgePage.tsx`, `Recipes/`, меню — `GenerateMenuForm.tsx` (селектор стратегии MG_STRAT_WEB).
- **API-клиенты:** `src/api/*.ts` (`menu.ts`, `shopping.ts`, `fridge.ts`).
- **Типы:** `src/types/index.ts`.
- **Layout/навигация:** `src/components/layout/` (`AppLayout.tsx`, `Sidebar.tsx`, `SyncIndicator.tsx`), роутинг — `src/App.tsx`.
- **Стилизация:** Tailwind-классы инлайн в TSX.

### Mobile (`/opt/menugen/mobile/menugen_app`, Flutter + BLoC)
- **Фичи:** `lib/features/<feature>/` со структурой `screens/`, `bloc/`, `models/`.
  - меню: `features/menu/.../generate_menu_bottom_sheet.dart` (селектор стратегии MG_STRAT_MOBILE), `menu_bloc.dart`, `menu_event.dart`.
  - покупки: `features/shopping/screens/`, `bloc/shopping_bloc.dart`, `models/shopping_models.dart`.
  - холодильник: `features/fridge/screens/`.
- **Оболочка/навигация:** `lib/main.dart`, `main_shell.dart` (bottom-nav, SafeArea, баннеры).
- **Сеть:** `lib/core/network/dio_api_client.dart`; коннективность — `core/sync/`, `connectivity_banner.dart`.

### Открытые UI-хвосты из BACKLOG (кандидаты)
- **D-02** — APK последнего green-run НЕ верифицирован на устройстве: селектор «Стратегия меню», скрытие 3/5 для s2/s3, генерация s2/s3. (mobile)
- **T-16** — качество доборов s2 (UI не обязателен, но связан с отображением меню).
- s3 перекусы-опция: payload-параметр + UI-тогл — после наполнения базы.
- Прочее по запросу пользователя.

---

## Пайплайн сборки/деплоя UI

### Web (CRA, **rsync НЕТ**)
```bash
cd /opt/menugen/web/menugen-web
npx tsc --noEmit          # проверка типов
CI=false npm run build    # сборка в build/
# выложить build/ → /opt/menugen/web-dist/ через tar (rsync отсутствует):
find /opt/menugen/web-dist -mindepth 1 -maxdepth 1 -exec rm -rf {} + \
  && tar -C build -cf - . | tar -C /opt/menugen/web-dist -xf -
nginx -s reload
# в браузере: Ctrl+Shift+R (сброс кеша)
```

### Mobile (Flutter — НЕ на сервере)
- `flutter`/`flutter analyze` локально недоступны. Проверка — через **GitHub Actions** (push → workflow `Flutter CI`).
- Статусы ранов: `gh run list --limit 5`. Лог упавшего: `gh run view <ID> --log-failed | tail -60`.
- APK-артефакт: `gh run download <ID> -D /opt/menugen/apk_out` (скрипт `mg_apk_fetch.sh`).
- Санити Dart без flutter — баланс скобок (`mg_mobile_sanity.sh`).

---

## Правила работы (напоминание)
- Русский; по делу, без лишних рассуждений/извинений.
- Никогда не хардкодить URL/токены/пароли (file-пути в скриптах допустимы).
- Порядок: данные/диагностика → вывод пользователя → патч. **Никаких догадок.**
- Патчи: бэкап `.bak.MG_*.<TS>` + дословный `str.replace` (`count==1`) + маркер идемпотентности. **Отступы критичны.**
- **Урок chat-79:** литеральный якорь по строкам рядом с кириллицей часто НЕ совпадает (невидимые пробелы/ё). Надёжнее regex с толерантным отступом `^([ \t]*)<ascii-якорь>[ \t]*$` (re.M). В TSX/Dart отступ косметический — можно фикс-отступом.
- Все шаги мультифайловых патчей — **идемпотентны** (`if marker not in src`).
- Кириллица/тире — через `python3` heredoc (UTF-8) или `cat > файл`. `perl -i`/`sed` с кириллицей НЕ использовать.
- **Резюме / CHANGELOG / BACKLOG / commit — только по явной отмашке пользователя.**
- **Ветка для пуша: согласовать с пользователем** (chat-80 = `claude/nifty-rubin-h90pfg`).

## Окружение
- **Backend:** docker compose, сервис `backend` (`menugen-backend-1`), bind-mount `./backend:/app` + autoreload. Restart: `docker compose -f /opt/menugen/docker-compose.yml restart backend`. Порт хоста `8003`→`:8000`. API `/api/v1/...`. Тест-аккаунт **admin@dev.local** (premium + семья «Debug Admin», member id=3). На сервере `python` (в контейнере), хост — `python3`. Команды: `docker compose exec backend python manage.py ...`.
- ⚠️ Запись в БД через `manage.py shell` по stdin **ВИСНЕТ** (bind-mount/autoreload). Для записи — management-команда (in-process) или реальный API. Чтение — `... shell -T < /tmp/script.py` ок.
- **CHANGELOG:** `/opt/menugen/CHANGELOG.md`, helper `scripts/add_changelog.py` (anchor `<!-- CHANGELOG_AUTO_ANCHOR`).

## Git auth (для пуша)
- repo-local `credential.helper = store`; `~/.git-credentials` может протухать.
- Восстановление без хардкода: `read -rsp 'PAT: ' GH_PAT; echo` → `printf '%s' "$GH_PAT" | gh auth login -h github.com -p https --with-token` → `gh auth setup-git` → push → `unset GH_PAT`.
- Пуш: `git push -u origin <branch>`; при сетевых сбоях — ретраи с backoff 2/4/8/16с.
