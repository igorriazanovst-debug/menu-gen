# DEPLOY: web frontend (CRA → nginx)

⚠️ **КРИТИЧЕСКИ ВАЖНО** — фиксируется навечно во ВСЕ следующие резюме.

## Структура

| Что | Путь |
|---|---|
| Исходники CRA | `/opt/menugen/web/menugen-web/` |
| Локальная сборка CRA | `/opt/menugen/web/menugen-web/build/` |
| **Куда смотрит nginx (раздаёт)** | **`/opt/menugen/web-dist/`** |
| nginx конфиг | `/etc/nginx/sites-enabled/menugen-debug` |
| URL фронта | `http://31.192.110.121:8081/` |
| API (proxy на Django) | `http://31.192.110.121:8081/api/` → `127.0.0.1:8003` |

## Полный цикл деплоя web после изменений в src/

```bash
cd /opt/menugen/web/menugen-web

# 1. Проверка типов (опционально, но желательно)
npx tsc --noEmit

# 2. Сборка (CI=false, чтобы CRA не падал на eslint warnings)
CI=false npm run build

# 3. Копируем build → web-dist (то, что реально раздаёт nginx)
rm -rf /opt/menugen/web-dist
mkdir -p /opt/menugen/web-dist
cp -a /opt/menugen/web/menugen-web/build/. /opt/menugen/web-dist/

# 4. Reload nginx (опционально, статика не требует, но не помешает)
nginx -t && nginx -s reload

# 5. В браузере: Ctrl+Shift+R (hard reload)
```

## Бэкап перед деплоем

```bash
TS=$(date +%Y%m%d_%H%M%S)
tar -C /opt/menugen -czf /opt/menugen/backups/web-dist.tar.gz.bak_${TS} web-dist/
```

## Откат

```bash
rm -rf /opt/menugen/web-dist
tar -C /opt/menugen -xzf /opt/menugen/backups/web-dist.tar.gz.bak_<TS>
```

## Типичная ошибка (диагностика)

Если изменения в коде не видны в браузере **даже после Ctrl+Shift+R**:

1. Проверить, что отдаёт nginx:
   ```bash
   curl -sH 'Cache-Control: no-cache' "http://31.192.110.121:8081/?nocache=$(date +%s)" \
     | grep -oE 'src="[^"]*\.js[^"]*"'
   ```
2. Сравнить с `/opt/menugen/web/menugen-web/build/index.html`:
   ```bash
   grep -oE 'src="[^"]*\.js[^"]*"' /opt/menugen/web/menugen-web/build/index.html
   ```
3. Если хеши `main.<HASH>.js` отличаются — **забыли скопировать build → web-dist** (см. шаг 3 выше).

## Вспомогательный скрипт-шаблон для деплоя

`/opt/menugen/backend/scripts/mg_204_deploy.sh` — рабочий пример, можно использовать как заготовку для будущих задач (поменяв `mg_204` на нужный ID).
