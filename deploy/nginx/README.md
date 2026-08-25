# Конфиги nginx

Здесь лежат конфиги обоих серверов. **Оба** — чтобы их можно было сравнить
диффом: расхождение между ними уже стоило нам одной поломки.

| Файл | Сервер | Что раздаёт |
|---|---|---|
| `menugen.ru.conf` | прод, `158.255.5.166` | TLS, фронт, `/api/`, `/admin/`, `/media/`, `/apk/`, статика Django |
| `dev-8081.conf` | dev, `31.192.110.121:8081` | то же без TLS, плюс проксирование медиа на прод |

Файлы в репозитории — **копия того, что стоит на сервере**, а не источник
истины: nginx читает `/etc/nginx/sites-available/…`. Поменяли на сервере —
обновите копию здесь, иначе смысл теряется.

Быстрая сверка, что серверы не разъехались:

```bash
grep -o 'location [^ ]*' deploy/nginx/menugen.ru.conf | sort > /tmp/prod.loc
grep -o 'location [^ ]*' deploy/nginx/dev-8081.conf   | sort > /tmp/dev.loc
diff /tmp/prod.loc /tmp/dev.loc
```

Разница по TLS и `@prod_media` законна — dev без сертификата и берёт чужие
картинки. Разница по `/static/…` и `/api/`, `/admin/`, `/media/`, `/apk/` —
нет.

## Правило, ради которого всё это заведено

`/static/` делят между собой фронт и Django, и порядок тут не помогает:
nginx выбирает **самое длинное** совпадение префикса.

```
/static/js, /static/css, /static/media          → web-dist   (сборка CRA)
/static/admin/, /static/rest_framework/         → staticfiles (collectstatic)
```

Если правил для `/static/admin/` нет, запрос за стилями админки попадает в
SPA-фолбэк (`location /`) и получает **index.html фронта**: ответ 200, тип
`text/html`, браузер молча не применяет это как CSS. Админка открывается
голым HTML, и по виду страницы причину не угадать — выглядит как «слетела
тема».

Ровно так и было на dev: правил не завели ни разу, и статика админки там не
работала никогда — просто в админку долго не заходили. На проде правила были
с самого начала.

## Если админка вдруг без стилей

```bash
# 1. Что реально приходит вместо CSS
curl -sI http://<адрес>/static/admin/css/base.css | head -3
```

* `Content-Type: text/html` → нет правила `location /static/admin/`, добавьте
  блоки из соседнего конфига;
* `404` → правило есть, но каталога нет: соберите статику
  `docker compose exec -T backend python manage.py collectstatic --noinput`;
* `text/css` → nginx ни при чём, смотрите кэш браузера (Ctrl+Shift+R).

Деплой бэкенда теперь проверяет и то и другое сам: файл на диске — всегда, а
раздачу через nginx — если передать `STATIC_CHECK_URL`:

```bash
STATIC_CHECK_URL=http://127.0.0.1:8081/static/admin/css/base.css \
  BRANCH=main /tmp/deploy_backend.sh
```

## Почему статика не в git

`backend/staticfiles/` собирается из пакетов Django и приложений, поэтому
лежит в `.gitignore`. Из-за этого её однажды сносила синхронизация кода
(`rsync --delete` не знал про исключение) — теперь каталог исключён наравне с
`media/`, а `collectstatic` встроен в деплой.
