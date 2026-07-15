# Перенос MenuGen на новый сервер (menugen.ru)

Документ — единый источник правды по миграции. Держим его в репозитории, чтобы
шаги были воспроизводимы и обратимы.

- **Старый сервер:** `31.192.110.121` (HTTP, backend наружу на `:8081`/`:8003`).
- **Новый сервер:** `158.255.5.166`, Ubuntu, чистая система.
- **Домен:** `menugen.ru` (+`www`) → после cutover A-запись на `158.255.5.166`.
- **Целевая архитектура:** один домен, HTTPS (Let's Encrypt), nginx-прокси;
  backend (docker) слушает только `127.0.0.1:8003`; веб-фронт и API на одном
  origin (`/api/v1` — относительный путь).

> Пароли root в переписке — временные. Сразу после переноса перейти на
> SSH-ключи и сменить пароли. В репозитории и скриптах паролей нет.

---

## Принцип: подготовить приёмник заранее, паузу — минимальную

Сначала на новом сервере поднимаем всю инфраструктуру и **структуру** БД
(пустую), настраиваем DNS/TLS. Только в короткое maintenance-окно снимаем
актуальные данные со старого сервера и накатываем в готовые структуры нового.
Так простой сводится к времени `pg_dump | restore` + `rsync media` дельты.

---

## Фазы

| Фаза | Что | Простой |
|------|-----|---------|
| A | Развязка в репозитории (домен/HTTPS через env) | нет |
| B | Bootstrap нового сервера: docker, код, пустая БД со структурой, nginx | нет |
| C | DNS: A-запись `menugen.ru`, низкий TTL; TLS-сертификат | нет |
| D | **Maintenance-окно:** экспорт данных со старого → импорт в новый | да, короткий |
| E | Пересборка мобильного APK на домен + переключение | нет |
| F | Финализация: HSTS, бэкапы, автопродление cert, вывод старого | нет |

---

## Фаза A — развязка в репозитории ✅ (в этом коммите)

Изменения обратно совместимы: на старом сервере при передеплое ничего не
ломается (все новые настройки по умолчанию выключены).

- `backend/config/settings.py`: env-driven `CSRF_TRUSTED_ORIGINS`,
  `USE_X_FORWARDED_PROTO`→`SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, HSTS.
- `docker-compose.yml`: убран устаревший `version:`; порт backend'а
  параметризован — `${BACKEND_BIND:-0.0.0.0}:${BACKEND_HOST_PORT:-8003}:8000`.
- `.env.example` (корень) и `web/menugen-web/.env.example`: профили СТАРЫЙ/НОВЫЙ.
- `deploy/nginx/menugen.ru.conf`: шаблон nginx (один домен, HTTPS, SPA + прокси).
- `.github/workflows/flutter_ci.yml`: дефолтный API-URL — `https://menugen.ru/api/v1`.
- `deploy/migrate/collect_facts.sh`: сбор фактов о старом сервере (только чтение).

**Действие пользователя (перед Фазой B):** запустить `collect_facts.sh` на старом
сервере (см. шапку скрипта) и прислать вывод. Нужны: версия Postgres, размер БД и
media, полный `nginx -T`, VK OAuth / платёжные callback-URL.

---

## Фаза B — bootstrap нового сервера (без простоя)

На `158.255.5.166` (root). Скрипты финализируем после `collect_facts`.

1. Базовая система: `apt update && apt -y upgrade`, установить `docker`,
   `docker compose`, `nginx`, `certbot`, `python3-certbot-nginx`, `rsync`, `git`,
   `ufw`. Открыть `ufw`: 22, 80, 443.
2. Развернуть код: `git clone` репозитория в `/opt/menugen`, ветка `main`.
3. Создать `/opt/menugen/.env` из `.env.example`, профиль **НОВЫЙ**:
   - `BACKEND_BIND=127.0.0.1`
   - `ALLOWED_HOSTS=menugen.ru,www.menugen.ru,127.0.0.1,localhost`
   - `CSRF_TRUSTED_ORIGINS=https://menugen.ru,https://www.menugen.ru`
   - `USE_X_FORWARDED_PROTO=True`, `USE_X_FORWARDED_HOST=True`
   - `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
   - `SECRET_KEY`, `DB_*`, `REDIS_URL`, `CELERY_*`, AI-ключи — **перенести со
     старого сервера** (взять из его `.env`; те же значения, чтобы JWT/сессии и
     внешние интеграции продолжили работать).
4. Поднять инфраструктуру: `docker compose up -d db redis`.
5. Структура БД (пустая): `docker compose up -d backend` затем
   `docker compose exec backend python manage.py migrate` и
   `python manage.py collectstatic --noinput`.
6. Веб-фронт: собрать CRA с `REACT_APP_API_BASE_URL=/api/v1` в `/opt/menugen/web-dist`
   (можно `BRANCH=main ./scripts/deploy_web.sh` — заранее положив
   `web/menugen-web/.env` c `/api/v1`).
7. nginx: положить `deploy/nginx/menugen.ru.conf` в `sites-available`, слинковать
   в `sites-enabled` (сначала только `:80`-блок — до выпуска cert).

На этом этапе новый сервер работает по IP на пустой БД — можно проверить
`/admin/` и `/api/v1/` через `curl --resolve menugen.ru:443:158.255.5.166` (после cert).

---

## Фаза C — DNS + TLS (без простоя)

1. **Заранее** снизить TTL A-записи `menugen.ru` (напр. до 300 c) у регистратора.
2. Выпустить сертификат на новом сервере (пока A-запись ещё на старом IP —
   использовать DNS-01 или временно webroot после переключения; проще: сначала
   переключить A-запись в Фазе D, потом `certbot --nginx`). Рекомендация: в
   Фазе C держать A-запись на СТАРОМ сервере, cert выпустить в начале Фазы D
   сразу после переключения DNS.

---

## Фаза D — maintenance-окно: перенос данных (короткий простой)

Порядок — чтобы не потерять данные, записанные между дампом и переключением:

1. **Объявить окно.** На старом сервере остановить приём записи: проще всего
   остановить `backend`/`celery` (`docker compose stop backend celery celery-beat`)
   — API отдаёт 502, мобилка уходит в offline-кэш (это ожидаемо и безопасно).
2. **Экспорт со старого** (`deploy/migrate/export_old.sh` — финализируем после facts):
   - `docker compose exec -T db pg_dump -U <user> -Fc <db> > /tmp/menugen.dump`
   - `rsync -a /var/lib/docker/volumes/menugen_media_files/_data/ → new:/opt/menugen/media/`
     (или через промежуточный tar; путь volume берём из `collect_facts`).
3. **Импорт в новый** (`deploy/migrate/import_new.sh`):
   - остановить backend на новом, `pg_restore --clean --if-exists` в готовую БД,
   - `rsync` media на место (см. монтирование volume/alias в nginx),
   - `docker compose up -d`, `migrate` (no-op, структура уже есть),
     `collectstatic`.
4. **Переключить DNS:** A-запись `menugen.ru` (+`www`) → `158.255.5.166`.
5. **TLS:** `certbot --nginx -d menugen.ru -d www.menugen.ru`, включить `:443`-блок,
   `nginx -t && systemctl reload nginx`.
6. **Смоук-тест:** логин в веб, генерация меню, открытие рецепта, загрузка фото
   «я приготовил», `/admin/`. Проверить, что backend наружу закрыт
   (`curl http://158.255.5.166:8003/` — должно не отвечать снаружи).

**Откат Фазы D:** вернуть A-запись на `31.192.110.121`, поднять backend на старом
(`docker compose start backend celery celery-beat`). Старый сервер не трогаем до
подтверждения, что новый стабилен ≥ несколько дней.

---

## Фаза E — мобильное приложение

CI уже собирает APK с `https://menugen.ru/api/v1` (Фаза A). После cutover:
- собрать релизный APK (workflow `flutter_ci` / `workflow_dispatch`),
- раздать пользователям. Старые APK, зашитые на IP `31.192.110.121:8081`,
  продолжат работать, пока жив старый сервер, — поэтому старый гасим не сразу.

---

## Фаза F — финализация

- Включить HSTS в `.env` нового сервера (`SECURE_HSTS_SECONDS=31536000`, …).
- Автопродление cert: `systemctl status certbot.timer` (ставится с пакетом).
- Регулярные бэкапы БД (cron `pg_dump | gzip` в `/opt/menugen/backups`).
- Поднять TTL DNS обратно (напр. 3600 c).
- Перейти на SSH-ключи, сменить root-пароли обоих серверов.
- Через несколько дней стабильной работы — вывести старый сервер.

---

## Что понадобится от пользователя

1. Вывод `deploy/migrate/collect_facts.sh` со старого сервера.
2. Доступ к DNS-панели домена `menugen.ru` (сменить A-запись, TTL).
3. Подтверждение начала maintenance-окна (Фаза D).
4. Значения секретов из `.env` старого сервера для переноса в новый
   (`SECRET_KEY`, `DB_*`, AI-ключи, VK/платёжные) — их переносим как есть.
