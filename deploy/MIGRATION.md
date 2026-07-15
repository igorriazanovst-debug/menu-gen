# Перенос MenuGen на новый сервер (menugen.ru)

Единый источник правды по миграции. Шаги воспроизводимы и обратимы.

- **Старый сервер:** `31.192.110.121` (Ubuntu 22.04, HTTP). **Делит хост** с другим
  проектом (kiosk/editor-web на портах 80/8080 и `catalog_db` pgvector на 5433) —
  MenuGen там на nginx-порту **8081**. К MenuGen относятся только контейнеры
  `menugen-*` и volume `menugen_media_files` / `menugen_postgres_data`.
- **Новый сервер:** `158.255.5.166` (Ubuntu, чистая система, **выделен под MenuGen**) →
  занимаем стандартные 80/443.
- **Домен:** `menugen.ru` (+`www`).

## Ключевые факты (из `collect_facts.sh`)

| Параметр | Значение |
|----------|----------|
| Postgres | **15.17** (`postgres:15-alpine`) — на новом тот же образ |
| БД / пользователь | `DB_NAME=menugen`, `DB_USER=menugen_user` |
| Медиа | **1.5 ГБ, 1089 файлов**, volume `menugen_media_files` (`/app/media`) |
| Backend порт | docker `0.0.0.0:8003->8000`, nginx `:8081` проксирует → `127.0.0.1:8003` |
| DEBUG (старый) | `True` (медиа/ошибки отдаёт runserver). На новом ставим **False** |
| AI | `AI_PROVIDER=openai`, `AI_BASE_URL=https://api.aitunnel.ru/v1`, `AI_TEXT_MODEL=gpt-4o-mini` |
| `BACKEND_PUBLIC_URL` | `http://31.192.110.121:8003` → **на новом `https://menugen.ru`** (строит абсолютные URL картинок!) |
| VK / YooKassa | ключи в `.env` **закомментированы** (интеграции неактивны) — перерегистрировать callback'и не нужно |
| TLS | сертификатов нет (сейчас чистый HTTP) |
| APK | nginx отдаёт `/apk/` из `web-dist/apk/` — воспроизводим |

> Пароли root из переписки — временные, нигде не сохранены. После переноса —
> SSH-ключи и смена паролей.

## Целевая архитектура нового сервера

- Один домен `menugen.ru`, HTTPS (Let's Encrypt), nginx-прокси.
- Backend (docker) слушает только `127.0.0.1:8003` (`BACKEND_BIND=127.0.0.1`).
- Веб-фронт и API на одном origin: фронт собран с `REACT_APP_API_BASE_URL=/api/v1`.
- `DEBUG=False`. Раскладка статики без коллизий:
  - `/static/js|css|media` → CRA (`web-dist`);
  - `/static/admin/`, `/static/rest_framework/` → `collectstatic` (`backend/staticfiles`);
  - `/media/` → проксируется в backend (Django отдаёт файлы и при `DEBUG=False` —
    для этого в `config/urls.py` медиа-роут больше не завязан на `DEBUG`).

---

## Фазы и простой

| Фаза | Что | Простой |
|------|-----|---------|
| A | Развязка в репозитории (домен/HTTPS/DEBUG-независимая отдача медиа) | нет |
| B | Bootstrap нового сервера: docker, код, пустая БД со структурой, nginx, web-dist | нет |
| C | DNS: понизить TTL заранее | нет |
| D | **Maintenance-окно:** export_old → перенос → import_new → DNS → TLS | да, короткий |
| E | Пересборка APK на домен | нет |
| F | Финализация: HSTS, бэкапы, автопродление cert, вывод старого | нет |

---

## Фаза A — развязка в репозитории ✅ (в коммитах ветки)

Всё обратно совместимо: на старом сервере при передеплое поведение не меняется.

- `settings.py`: env-driven `CSRF_TRUSTED_ORIGINS`, `USE_X_FORWARDED_PROTO`→
  `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST`, secure-куки, `SECURE_SSL_REDIRECT`, HSTS.
- `config/urls.py`: `/media/` отдаётся и при `DEBUG=False` (serve-роут вместо
  `static()`-хелпера, который при False возвращает `[]`).
- `docker-compose.yml`: убран `version:`; порт backend'а параметризован
  `${BACKEND_BIND:-0.0.0.0}:${BACKEND_HOST_PORT:-8003}:8000`.
- `.env.example` (корень, вкл. `BACKEND_PUBLIC_URL`) и `web/.env.example`.
- `deploy/nginx/menugen.ru.conf`: шаблон nginx (HTTPS, статика, медиа, `/apk/`, SPA).
- `flutter_ci.yml`: дефолтный API-URL → `https://menugen.ru/api/v1`.
- `deploy/migrate/`: `collect_facts.sh`, `bootstrap_new.sh`, `export_old.sh`, `import_new.sh`.

---

## Фаза B — bootstrap нового сервера (без простоя)

На `158.255.5.166` (root):

```bash
apt-get update && apt-get install -y git
git clone <REPO_URL> /opt/menugen && cd /opt/menugen && git checkout main
bash deploy/migrate/bootstrap_new.sh          # поставит docker/nginx/certbot, создаст .env-заготовку
# → заполнить /opt/menugen/.env секретами со старого сервера (профиль НОВЫЙ), затем:
bash deploy/migrate/bootstrap_new.sh          # поднимет db/redis/backend, migrate, collectstatic, web-dist, nginx
```

Секреты, которые переносим со старого `.env` **как есть** (иначе разлогинит всех /
сломает AI): `SECRET_KEY`, `DB_PASSWORD`, `AI_API_KEY` (+`AI_PROVIDER`, `AI_BASE_URL`,
`AI_TEXT_MODEL`), `EMAIL_*` при наличии.

После Фазы B новый сервер работает на **пустой** БД (проверка по IP). Домен и данные — позже.

---

## Фаза C — DNS (без простоя)

Заранее у регистратора `menugen.ru` понизить TTL A-записи (напр. 300 c), чтобы
переключение в Фазе D распространилось быстро. A-запись пока указывает на старый IP.

---

## Фаза D — maintenance-окно: перенос данных (короткий простой)

1. **Экспорт со старого** (останавливает запись):
   ```bash
   # на 31.192.110.121, в /opt/menugen
   git fetch origin main
   git show origin/main:deploy/migrate/export_old.sh > /tmp/export_old.sh && sed -i 's/\r$//' /tmp/export_old.sh
   STOP_WRITES=1 bash /tmp/export_old.sh
   ```
   Создаст `backups/migrate/<TS>/{menugen.dump, media.tar.gz, meta.txt}` и напечатает
   команду переноса.
2. **Перенос на новый** (rsync/scp из вывода export'а), напр.:
   ```bash
   rsync -avz -e ssh /opt/menugen/backups/migrate/<TS>/ root@158.255.5.166:/opt/menugen/backups/migrate/<TS>/
   ```
3. **Импорт в новый:**
   ```bash
   # на 158.255.5.166, в /opt/menugen
   bash deploy/migrate/import_new.sh /opt/menugen/backups/migrate/<TS>
   ```
4. **DNS:** A-запись `menugen.ru` (+`www`) → `158.255.5.166`. Дождаться распространения.
5. **TLS:** `certbot --nginx -d menugen.ru -d www.menugen.ru` → `nginx -t && systemctl reload nginx`.
6. **Смоук-тест:** логин, генерация меню, открытие рецепта, фото «я приготовил», `/admin/`,
   картинки грузятся с `https://menugen.ru/media/...`. Backend снаружи закрыт
   (`curl http://158.255.5.166:8003/` — не должно отвечать).

**Откат Фазы D:** вернуть A-запись на `31.192.110.121` и `docker compose start
backend celery celery-beat` на старом. Старый сервер не гасим до подтверждения.

---

## Фаза E — мобильное приложение

CI уже собирает APK с `https://menugen.ru/api/v1`. После cutover — собрать релизный
APK (`flutter_ci` / `workflow_dispatch`), выложить в `/apk/`. Старые APK (зашитые на
`31.192.110.121:8081`) работают, пока жив старый сервер, — поэтому его не гасим сразу.

---

## Фаза F — финализация

- HSTS в `.env` нового: `SECURE_HSTS_SECONDS=31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`, `SECURE_HSTS_PRELOAD=True`.
- Автопродление cert: `systemctl status certbot.timer`.
- Бэкапы БД: cron `pg_dump | gzip` в `/opt/menugen/backups`.
- Вернуть TTL DNS (напр. 3600 c).
- SSH-ключи, смена root-паролей обоих серверов.
- Через несколько дней стабильной работы — вывести старый сервер.

## Что понадобится от пользователя

1. URL git-репозитория для `git clone` на новом сервере (или деплой-ключ).
2. Доступ к DNS-панели `menugen.ru` (A-запись, TTL).
3. Значения секретов из `.env` старого сервера (перечислены в Фазе B).
4. Подтверждение начала maintenance-окна (Фаза D).
