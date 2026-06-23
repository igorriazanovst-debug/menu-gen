# RESUME — Freemium-сессия (handoff для следующего чата)

> Цель сессии: ввести **freemium** (бесплатный тариф с квотой на генерацию меню),
> доработать веб + мобилку, собрать APK, развернуть на сервере.
> Всё слито в `main`. Веб/бэкенд деплоятся скриптами из `scripts/`.

---

## 0. ⚠️ ЧИТАЙ ПЕРВЫМ — мои косяки прошлых сессий (НЕ ПОВТОРЯТЬ)

Пользователь (справедливо) бомбил за амнезию. Зафиксировано навечно:

1. **APK СОБИРАЕТСЯ ЧЕРЕЗ GITHUB ACTIONS, А НЕ ЛОКАЛЬНО.**
   Триггер — **пуш в `main`** (workflow `Flutter CI`, `.github/workflows/flutter_ci.yml`).
   Артефакт: `menugen-debug-apk-<run_number>`. Локально APK НЕ собрать —
   `dl.google.com` (Android SDK / Android Gradle Plugin) в этом окружении даёт
   **403**, git-прокси пускает только whitelisted-репо. **Не пытайся ставить
   Android SDK / Flutter и билдить APK руками — это тупик.** Просто
   `git commit` + `git push origin main` → CI соберёт APK.

2. **«ТЫ МОЖЕШЬ ДЕЛАТЬ КОММИТ И ПУШ»** — не тормози и не уводи в ручные шаги.
   Коммит+пуш в `main` — это и есть штатный способ запустить сборку.

3. **Ветка.** В этой сессии рабочая ветка пользователя была
   `claude/nifty-rubin-h90pfg`, я сначала ошибочно работал в
   `claude/awesome-brown-gdrxsw`. Итог: **всё уехало в `main`** (см. ниже).
   Дефолтная ветка репо = `main`, разработка реально идёт на ней.

4. **Репо клонируется SHALLOW.** `git merge`/`merge-base` ругались
   «refusing to merge unrelated histories», пока не сделал
   `git fetch --unshallow origin`. После этого `main` оказался предком рабочей
   линии (чистый fast-forward).

5. **Сервер-подписант коммитов иногда отдаёт 503** — ретраить
   `git cherry-pick --continue` / commit несколько раз.

6. **Веб НЕ в Docker.** CRA собирается на хосте → кладётся в
   `/opt/menugen/web-dist/` → раздаёт **host-nginx**. Деплой backend в Docker,
   web — нет. (Долго путался.)

7. **`REACT_APP_API_BASE_URL`.** Без `.env` при сборке в бандл вшивается
   `http://localhost:8000/api/v1` → логин из браузера не доходит, «Неверные
   учётные данные». Всегда собирай через `scripts/deploy_web.sh` /
   `redeploy_web.sh` — они копируют `.env` и проверяют, что вшит правильный URL.

8. **Кэш `index.html`.** После деплоя браузер тянул старый `index.html` →
   ссылку на удалённый `main.<hash>.js` → 404 → «тёмный экран» (в инкогнито ок).
   Лечится `scripts/nginx_no_cache_index.sh` (no-store для index.html).

9. **Минифицированный JS экранирует кириллицу в `\uXXXX`.** Проверять наличие
   строк в сборке надо по `*.js.map`, а не по `*.js` (иначе ложный «не найдено»).

10. **Всё приложение исторически premium-only.** Freemium потребовал фронт-гейта
    (см. §4) — без него free-юзер падал на premium-дашборде.

---

## 1. Что сделано (зафиксированные решения)

**Freemium-правила:**
- Бесплатно: **4 генерации меню / календарный месяц**, сброс 1-го числа.
- Free-семья: **1 участник**.
- Заведён видимый план `code='free'` (price=0, `features={"menu_generations_per_month":4}`).
- **Premium-only остаются: дневник, холодильник, уведомления** (+ часть menu-подэндпоинтов: swap/shopping-list/quarantine).
- **Free открыто: генерация+просмотр меню (с квотой), рецепты, семья (1), покупки, тарифы, профиль.**

**Тестовый юзер:** `free@menugen.test` / `1234!` (management-команда
`create_test_free_user`, см. §3).

---

## 2. Реализация по слоям

### Backend (`apps/subscriptions`, `apps/menu`, `apps/family`, `apps/users`)
- Модель `MenuGenerationCounter(OneToOne→Family)` + миграция
  `0002_menugenerationcounter`.
- Data-миграция `0003_create_free_plan` — создаёт план `free`.
- `apps/subscriptions/quota.py` — хелперы: `menu_quota_limit/used`,
  `can_generate_menu`, `try_consume_menu_generation` (row-lock, premium=∞),
  `menu_quota_summary`, `free_max_family_members`.
- `apps/menu/views.py` — `MenuGenerateView`: квота вместо жёсткого premium-гейта
  (403 `menu_quota_exceeded` + `reset_at` при превышении); list/detail открыты free.
- `apps/family/views.py` — `_member_limit_info`: лимит участников применяется и
  без подписки (free=1).
- `apps/users/serializers.py` — `subscription_status.menu_quota` (used/limit/reset_at) в `/users/me`.
- `create_test_free_user` — management-команда.
- Тесты: `apps/subscriptions/tests/test_menu_quota.py` + обновлены premium-gate тесты.
  (Прогон: 312 passed; предсуществующие падения — shopping-toggle и fridge-barcode,
  не связаны с freemium.)

### Web (`web/menugen-web`, React CRA)
- `types/index.ts` — `SubscriptionStatus`/`MenuQuota` в `User`.
- `GenerateMenuForm.tsx` — баннер «осталось N из 4», блок кнопки при исчерпании,
  после генерации `dispatch(initAuth())` (обновить остаток).
- `SubscriptionsPage.tsx` — строка лимита генераций в тарифах.
- **Freemium-гейт страниц:** `hooks/usePremium.ts`
  (`PREMIUM_PATHS=['/dashboard','/diary','/fridge']`, `useIsPremium`),
  `App.tsx` (`PremiumRoute`→редирект на `/subscriptions`, `HomeRedirect`:
  free→`/menu`, premium→`/dashboard`), `Sidebar.tsx` (premium-пункты скрыты для free).
- `components/ErrorBoundary.tsx` — падение страницы не сносит всё приложение.

### Mobile (`mobile/menugen_app`, Flutter — таргет 3.22.0!)
- `generate_menu_bottom_sheet.dart` — парсит `menu_quota` из `/users/me`,
  баннер остатка, блок кнопки.
- `dio_api_client.dart` — читает `code` из тела ошибки;
  `api_exception.dart` — `isQuotaExceeded`.
- ⚠️ Локально `flutter analyze` НЕ гонял: проект на старом Flutter (3.22),
  у меня был 3.44 → каскад конфликтов версий. Проверка — через `Flutter CI`.

---

## 3. ПАМЯТКА — сервер, контейнеры, адреса (MEMO_connections)

```
Сервер:        /opt/menugen
Compose:       docker compose -f /opt/menugen/docker-compose.yml
Сервисы:       backend (Django, /app=backend/), db (PG15), redis (7), celery, celery-beat
                web-сервис фронта в compose НЕТ — это host-nginx (см. ниже)

Порты / адреса:
  backend напрямую на хосте:  http://127.0.0.1:8003  (8003->8000)
  публичный фронт+API:        http://31.192.110.121:8081/    (nginx)
                              /api/ → проксирует на 127.0.0.1:8003
  nginx на 80/8080 на /api/v1 может давать 404 — ходить на :8003
  Swagger (локально):         http://localhost:8000/api/v1/docs/

Web-деплой (КРИТИЧНО):
  исходники:  /opt/menugen/web/menugen-web/
  nginx раздаёт: /opt/menugen/web-dist/   <-- сюда копируется build/
  nginx конфиг:  /etc/nginx/sites-enabled/menugen-debug
  .env (gitignored): web/menugen-web/.env  с REACT_APP_API_BASE_URL=
                     http://31.192.110.121:8081/api/v1
  бэкапы БД/кода/web-dist: /opt/menugen/backups/

БД-креды: /opt/menugen/.env (DB_NAME/DB_USER/DB_PASSWORD), gitignored — git не трогает.

APK: GitHub Actions → workflow «Flutter CI», триггер push в main,
     артефакт menugen-debug-apk-<N>; качать `gh run download <RUN_ID> -n ...`.

Стек: Python3.11 / Django4.2 / DRF / PG15 / Redis7+Celery / JWT(simplejwt) /
      drf-spectacular. CI: flake8 max-line-length=120, black -l 120, isort --profile black.
```

---

## 4. Готовые скрипты (в `scripts/`, запускать на сервере)

Паттерн запуска (без CRLF-сюрпризов):
```bash
cd /opt/menugen && git fetch origin main
git show origin/main:scripts/<имя>.sh > /tmp/<имя>.sh
sed -i 's/\r$//' /tmp/<имя>.sh
bash /tmp/<имя>.sh
```

- `deploy_backend.sh` — бэкап БД+кода → rsync backend/ из ветки в worktree →
  миграции → рестарт контейнеров → health-check. `BRANCH=main ASSUME_YES=1`.
  **Не трогает локальный git/.env/web-dist.**
- `setup_free_test_user.sh` — создаёт `free@menugen.test/1234!` + проверка квоты через API.
- `deploy_web.sh` / `redeploy_web.sh` — чистая сборка веба из ветки в worktree,
  копирует `.env`, проверяет вшитый API-URL (стоп на localhost:8000), публикует
  в web-dist, reload nginx, печатает реально отдаваемый хэш бандла.
  (Проверка наличия фикса — по `.js.map`, не по `.js`.)
- `nginx_no_cache_index.sh` — безопасно (бэкап+`nginx -t`+откат) ставит
  `Cache-Control: no-store` для index.html и immutable для /static/.

---

## 5. Статус / что осталось проверить в следующей сессии

- ✅ Backend на сервере: миграции `0002/0003` применены, план `free` создан.
- ✅ Тестовый юзер создан, логин на бэке работает (curl на :8003 отдаёт токены).
- ✅ APK собран в Actions (был run #114, `menugen-debug-apk-114`).
- 🔄 **Веб-деплой на сервере**: последний `redeploy_web.sh` (исправленный,
  коммит `74ee0df`) пользователь перезапускал — **подтвердить, что web-dist
  обновился и хэш в браузере совпал**; при необходимости — `nginx_no_cache_index.sh`.
- 🔄 Проверить free-UX в браузере: старт на «Меню», в сайдбаре нет
  Главной/Дневника/Холодильника, прямой URL `/diary`→`/subscriptions`,
  4 генерации → 5-я «Лимит исчерпан».
- ⏳ Возможный полиш: дружелюбный текст вместо сырого «Лимит участников для
  тарифа „Бесплатный“ исчерпан (1)» на странице Семьи (для free).
- ⏳ Mobile: прогнать реальную проверку квоты в APK против сервера.

## 6. Ветки/коммиты
- Всё в `main` (последний: `74ee0df`). Линия freemium:
  `b62bf30` (backend) → `1f889a6` (web/mobile UI + тест-юзер) →
  `39eee44` (setup script) → `0733340` (web-гейт+ErrorBoundary) →
  `583a120`/`74ee0df` (deploy-скрипты).
- Ветка `claude/nifty-rubin-h90pfg` содержит то же (cherry-pick); локальные
  серверные правки сохранены в `backup/server-*` ветке/стэше при деплое.
