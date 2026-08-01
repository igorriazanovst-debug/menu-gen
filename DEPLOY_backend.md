# Деплой BACKEND (аддитивный) — `scripts/deploy_backend.sh`

Бэкенд на сервере (`/opt/menugen`) исторически работал с ветки `main`. Этот
скрипт деплоит backend с фичеветки **аддитивно и обратимо**, не переключая
основное рабочее дерево (web-dist и `.env` не трогаются — как в `deploy_web.sh`).

## Что делает скрипт

1. Бэкап БД (`pg_dump` → `backups/db.sql.gz.bak_<TS>`).
2. Бэкап текущего кода (`backups/backend.tar.gz.bak_<TS>`).
3. Чекаут ветки в изолированный worktree (`/tmp/mg-backend-build`).
4. `rsync` только каталога `backend/` в рабочее дерево (без `media/`, `__pycache__`).
5. Печатает `migrate --plan` и **спрашивает подтверждение** (`ASSUME_YES=1` — без вопроса).
6. `migrate --noinput`.
7. Рестарт `backend` + `celery` + `celery-beat`.
8. Health-check `GET /api/v1/`.

## Запуск (на сервере)

```bash
cd /opt/menugen
git fetch origin claude/nifty-rubin-h90pfg
git show origin/claude/nifty-rubin-h90pfg:scripts/deploy_backend.sh > /tmp/deploy_backend.sh
sed -i 's/\r$//' /tmp/deploy_backend.sh   # на случай CRLF (env: 'bash\r')
chmod +x /tmp/deploy_backend.sh
/tmp/deploy_backend.sh
```

## Миграции этой сессии (аддитивные, неразрушающие)

- `users.0007_user_is_managed` — `AddField is_managed BooleanField(default=False)`.
- `fridge.0014_fridgeitem_source_shopping_item` — `AddField` nullable FK
  `source_shopping_item` (SET_NULL) + `AddIndex`.

Обе только добавляют столбцы/индекс с дефолтом/`NULL` — существующие строки не
меняются, откат не требует переписывания данных.

## ⚠️ Важно: дивергенция backend (main → ветка)

Так как backend в проде шёл с `main`, при первом деплое ветки `migrate` применит
**все накопленные с момента расхождения** миграции, а не только две выше —
например `users.0006_mg_skin_user_ui_skin` (поле `ui_skin`, из-за которого ранее
ломался вход при web-деплое со сменой дерева), а также миграции shopping/fridge/
diary, добавленные в ветке. Это и есть корректная синхронизация: код ветки
ожидает эти столбцы.

**Перед применением посмотри вывод `migrate --plan`** (скрипт печатает его до
подтверждения) — там полный список того, что будет применено. Все миграции ветки
ожидаются аддитивными; если в плане встретится `RemoveField`/`DeleteModel`/
`RunPython` с правкой данных — остановись и проверь вручную.

## Откат

```bash
cd /opt/menugen
# код:
tar -C /opt/menugen -xzf backups/backend.tar.gz.bak_<TS>
# БД (полное восстановление дампа):
gunzip -c backups/db.sql.gz.bak_<TS> | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
# перезапуск:
docker compose restart backend celery celery-beat
```

> Примечание: миграции этой сессии безопасно «забыть» и без полного отката БД —
> столбцы можно оставить (они не мешают коду `main`). Полный откат БД нужен лишь
> если применялись неожиданные неаддитивные миграции из дивергенции.

## Перенос рецептов между серверами (MG_RECIPESYNC)

`dumpdata`/`loaddata` для этого не годятся: они переносят записи вместе с `id`, а
на целевом сервере эти id уже заняты своими рецептами и продуктами. Вместо них —
пара команд с натуральными ключами (рецепт ищется по `legacy_id` → `source_url` →
нормализованному названию, связи с продуктами пересобираются по именам продуктов).

**1. На источнике (dev):**

```bash
docker compose exec backend python manage.py export_recipes --output /tmp/recipes.json
docker compose cp backend:/tmp/recipes.json ./recipes.json
```

По умолчанию выгружаются только каталожные рецепты: `is_custom=False`,
без автора, `is_published=True` (флаги `--include-custom`, `--include-unpublished`).

**2. Копируем файл и картинки на целевой сервер:**

```bash
scp recipes.json root@<PROD>:/opt/menugen/
# картинки рецептов (image_url вида /media/...) файлами не переносятся:
rsync -av /opt/menugen/media/ root@<PROD>:/opt/menugen/media/
```

**3. На приёмнике (prod) — сначала дамп БД, потом сухой прогон:**

```bash
docker compose exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > backups/db_before_recipes_$(date +%Y%m%d_%H%M%S).dump
docker compose cp ./recipes.json backend:/tmp/recipes.json
docker compose exec backend python manage.py import_recipes_json /tmp/recipes.json --dry-run
docker compose exec backend python manage.py import_recipes_json /tmp/recipes.json --create-products
```

Импорт идемпотентен: уже существующие рецепты пропускаются, повторный запуск
ничего не дублирует. `--create-products` создаёт недостающие продукты
рубрикатора (без него связь останется без `product`, но текст ингредиента
сохранится). `--update` перезаписывает поля существующих рецептов — применять
осознанно, он затрёт правки, сделанные на приёмнике.

Пересборку связей по `post_save` (`MG_RECIPELINK`, ходит в ИИ) импорт гасит:
переносятся ровно те связи, что были в исходной базе.
