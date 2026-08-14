# EMAIL: отправка писем (подтверждение e-mail)

Статус на 30.07.2026: **отправка писем ещё не включена** — ждём, пока домену
`menugen.ru` исполнится 30 дней (ограничение Unisender Go). До этого момента
ссылка подтверждения **пишется в лог бэкенда** и флоу работает вручную.

## ⚠️ Unisender и Unisender Go — разные сервисы

Легко перепутать, и ошибка обнаруживается только на этапе отправки:

| | Кабинет | Что это |
|---|---|---|
| **Unisender** | `app.unisender.com` | классические маркетинговые рассылки |
| **Unisender Go** | `go1.unisender.ru` / `go2.unisender.ru` | транзакционные письма — **нам нужен он** |

Аккаунты, API-ключи и DNS-записи у них **свои**. Ключ от первого во втором даёт:

```
401 Unauthorized, code 114
"User with id '…' not found"
```

Формулировка обманчива: ключ структурно валиден, идентификатор из него
разбирается — просто такого пользователя нет в базе Go. Смена дата-центра
(`go1` ↔ `go2`) в этом случае не помогает: ни в одном его нет.

Наступали на это 14.08.2026: домен и записи настроили в `app.unisender.com`,
хотя код ходит в API Go. DKIM-селектор и SPF-include у продуктов тоже разные —
записи пришлось переделывать.

Дата-центр (`go1` или `go2`) определяется по адресу кабинета, в котором заведён
аккаунт, и должен совпадать с `UNISENDER_GO_API_URL`.

## Почему не SMTP

Обычный SMTP на этой инфраструктуре невозможен — проверено:

| Проверка | Результат |
|---|---|
| `smtp.yandex.ru:465` напрямую с сервера | `[Errno 101] Network is unreachable` |
| `smtp.yandex.ru:465` через SOCKS5 (Xray) | TCP есть, но TLS handshake timeout |
| `smtp.yandex.ru:587` через SOCKS5 (Xray) | timeout |

Исходящие SMTP-порты режет и хостинг, и VPS за прокси (стандартная антиспам-мера).
Поэтому письма отправляются **по HTTP API провайдера** (порт 443 открыт — через
него работают git/npm). Реализовано через `django-anymail`.

Код поддержки SMTP-через-прокси остался (`apps/common/email_backend.py`) — он
пригодится, если провайдер когда-нибудь откроет порты.

## Архитектура приёма/отправки

```
Отправка:  Django ──HTTPS/443──► Unisender Go ──► ящик получателя
Приём:     письмо на *@menugen.ru ──► Cloudflare Email Routing ──► menugen@yandex.com
```

Своего почтового сервера нет и не нужно: Cloudflare принимает и пересылает,
Unisender отправляет. Адрес `noreply@menugen.ru` существует только как
отправитель (ящика под ним нет — это нормально).

## Что уже сделано ✅

- Cloudflare: домен `menugen.ru` переведён на NS Cloudflare, **Active**.
- Cloudflare **Email Routing** включён, MX + SPF записи добавлены.
- Destination `menugen@yandex.com` — **Verified**.
- Адрес `noreply@menugen.ru` создан, пересылка проверена (письмо доходит).
  Повторно проверено 14.08.2026 после возврата NS: `noreply@menugen.ru` →
  `menugen@yandex.com` доходит.
- Бэкенд: `django-anymail` в requirements, `ANYMAIL`-настройки читаются из env,
  `email_enabled()` определяет настроенность по бэкенду (а не по `EMAIL_HOST`).

## Что осталось — после 30 дней с регистрации домена ⏳

Unisender Go отказывает: «Домен menugen.ru был зарегистрирован меньше 30 дней
назад». Обойти нельзя, только ждать. Когда срок пройдёт:

1. **Unisender Go → обратный адрес**: добавить `noreply@menugen.ru`, получить
   проверочное письмо (придёт через Cloudflare на Яндекс), перейти по ссылке.
2. **SPF — не создавать вторую запись!** Cloudflare уже добавил:
   ```
   v=spf1 include:_spf.mx.cloudflare.net ~all
   ```
   Две SPF-записи ломают и приём, и доставку. Нужно **отредактировать**
   существующую TXT-запись, добавив include от Unisender:
   ```
   v=spf1 include:_spf.mx.cloudflare.net include:<из кабинета Unisender> ~all
   ```
3. **DKIM** от Unisender — добавить как отдельную TXT-запись (уникальный
   селектор вида `mailer._domainkey`), с SPF не конфликтует.
4. **Включить отправку** на сервере:
   ```bash
   cd /opt/menugen
   cat >> .env <<'ENV'
   EMAIL_BACKEND=anymail.backends.unisender_go.EmailBackend
   UNISENDER_GO_API_KEY=<ключ из кабинета>
   UNISENDER_GO_API_URL=https://go1.unisender.ru/ru/transactional/api/v1
   ENV
   sed -i 's/^DEFAULT_FROM_EMAIL=.*/DEFAULT_FROM_EMAIL=noreply@menugen.ru/' .env
   docker compose up -d --build backend
   ```
   `UNISENDER_GO_API_URL`: дата-центр аккаунта — `go1` или `go2`, см. кабинет.
5. **Проверить**:
   ```bash
   docker compose exec backend python manage.py send_test_email menugen@yandex.com
   ```
   Ожидается `Письмо отправлено ✅`.

## ⚠️ NS домена нельзя уводить от Cloudflare

Приём почты держится на том, что зона обслуживается Cloudflare. Если перевести
NS домена обратно на регистратора, Cloudflare помечает зону как **Moved** и
**выключает Email Routing**. Записи и правила при этом остаются на месте и
выглядят рабочими, а MX начинают отбивать всё подряд:

```
550 5.1.1 Domain does not exist
```

Ошибка обманчивая: она не про DNS. NS и MX резолвятся, письмо доезжает до
`routeN.mx.cloudflare.net` — просто почтовая служба не считает домен своим,
пока зона не в статусе Active.

Наступали на это 14.08.2026: NS увели к регистратору из-за медленной работы
Cloudflare для российских пользователей, приём почты умер. Лечение — вернуть NS
и нажать **Re-check now** в Overview зоны; статус переходит в Active за минуты,
ждать сутки не нужно. Правила и подтверждённый адрес назначения сохраняются.

**Если Cloudflare тормозит — дело не в DNS, а в проксировании.** Это разные
переключатели:

| | Что делает | Влияние на скорость | Нужно для почты |
|---|---|---|---|
| NS у Cloudflare | обслуживает зону | нет | **да** |
| Оранжевое облако на A-записях | весь HTTP через Cloudflare | да, заметное | нет |

Правильное решение: NS оставить у Cloudflare, а A-записи `menugen.ru` и `www`
переключить в **DNS only** (серое облако). Трафик пойдёт напрямую на сервер,
почта продолжит работать. Перед переключением убедиться, что сертификат отдаёт
свой nginx, иначе сайт станет недоступен по HTTPS:

```bash
certbot certificates
curl -skI --resolve menugen.ru:443:158.255.5.166 https://menugen.ru/ | head -3
```

## Пока писем нет: как получить ссылку подтверждения

```bash
docker compose logs backend | grep "verify link"
```
В `DEBUG=True` ссылка также возвращается в ответе API (`verify_link`).

## Смена провайдера

Провайдер не «зашит» — меняется одной строкой в `.env`, ключи уже
предусмотрены в `settings.ANYMAIL`:

| Провайдер | EMAIL_BACKEND | Ключ |
|---|---|---|
| Unisender Go | `anymail.backends.unisender_go.EmailBackend` | `UNISENDER_GO_API_KEY` |
| Mailgun | `anymail.backends.mailgun.EmailBackend` | `MAILGUN_API_KEY` |
| Resend | `anymail.backends.resend.EmailBackend` | `RESEND_API_KEY` |

Особенность Mailgun: домен подтверждается **только DNS-записями** (SPF+DKIM),
проверочное письмо и ящик не требуются — вариант, если ограничение 30 дней
окажется критичным. Минус: зарубежный сервис (оплата картой).

## Подводные камни

| Грабли | Как избежать |
|---|---|
| Две SPF-записи | Одна TXT-запись с несколькими `include:` |
| Письмо не приходит на домен | В Cloudflare включить **catch-all** (сервисы пишут на `postmaster@`/`admin@`) |
| Привязка сайта к домену позже | A-запись в режиме **DNS only** (серая тучка), иначе прокси Cloudflare вмешается в TLS/API |
| Отправка через Cloudflare | Невозможна — он только принимает/пересылает |
| Письма молча не уходят | Проверить `email_enabled()`: для SMTP нужен `EMAIL_HOST`, для HTTP API — ключ провайдера |
