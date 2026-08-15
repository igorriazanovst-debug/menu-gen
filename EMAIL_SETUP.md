# EMAIL: отправка писем (подтверждение e-mail)

Статус на 15.08.2026: провайдер — **Resend**, отправка с прод-сервера проходит
(`send_test_email` → `Письмо отправлено ✅`). До этого полтора месяца ушло на
Unisender Go, который на бесплатном тарифе не даёт слать на чужие домены —
разбор в разделе «История: почему не Unisender Go».

`EMAIL_VERIFICATION_REQUIRED` включаем только после того, как убедились, что
письмо реально **доходит** до внешнего ящика (не «отправлено», а лежит во
входящих). Иначе регистрация ломается для всех сразу.

## Архитектура приёма/отправки

```
Отправка:  Django ──HTTPS/443──► Resend ──► ящик получателя
Приём:     письмо на *@menugen.ru ──► Cloudflare Email Routing ──► menugen@yandex.com
```

Своего почтового сервера нет и не нужно: Cloudflare принимает и пересылает,
Resend отправляет. Адрес `noreply@menugen.ru` существует только как отправитель
(ящика под ним нет — это нормально).

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

Это же закрывает вопрос «а купить хостинг с почтовым сервером у reg.ru и т.п.»:
почтовый хостинг отдаёт только SMTP, HTTP-API у него нет — ящик будет рабочим,
но бэкенд до него не дотянется. Проверять такой вариант нужно **до** оплаты,
тестом на доступность порта с самого сервера.

Код поддержки SMTP-через-прокси остался (`apps/common/email_backend.py`) — он
пригодится, если провайдер когда-нибудь откроет порты.

## Настройка Resend

Порядок, которым это реально было сделано 15.08.2026.

### 0. Убедиться, что сервер дотянется до API

```bash
docker compose exec backend python -c "
import requests; r = requests.get('https://api.resend.com/domains', timeout=10)
print(r.status_code, r.reason)"
```

`401 Unauthorized` — успех (без ключа так и должно быть): хост доступен, TLS
проходит. `Timeout`/`ConnectionError` — провайдер не подходит, дальше не идём.

### 1. Кабинет

resend.com → Sign up (карта не нужна) → **Domains → Add Domain** → `menugen.ru`,
регион **EU (eu-west-1)** — ближе к российским получателям.

### 2. DNS в Cloudflare

Resend выдаёт три записи. Все — **DNS only** (серое облако):

| Тип | Name | Content | Priority |
|---|---|---|---|
| TXT | `resend._domainkey` | `p=MIGfMA0...QIDAQAB` | — |
| MX | `send` | `feedback-smtp.eu-west-1.amazonses.com` | `10` |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | — |

Три вещи, на которых легко сломать **приём** почты:

- **MX идёт на `send`, а не на `@`.** Корневые MX принадлежат Cloudflare Email
  Routing — на них держится вся входящая почта. Заменишь их записями Resend —
  приём умрёт с обманчивым `550 5.1.1 Domain does not exist`.
- **Корневой SPF не трогать.** SPF от Resend живёт на `send.menugen.ru`
  отдельной записью и с корневым не конфликтует.
- **Имена короткие, без домена.** Cloudflare дописывает зону сам: вставленное
  `send.menugen.ru` превратится в `send.menugen.ru.menugen.ru`.

DKIM Resend отдаёт голым `p=…`, без префикса `v=DKIM1; k=rsa;` — так и надо.
Значения в кабинете обрезаны многоточием, копировать только кнопкой.

Проверка перед нажатием **Verify DNS Records**:

```bash
dig +short TXT resend._domainkey.menugen.ru
dig +short MX  send.menugen.ru
dig +short TXT send.menugen.ru
dig +short MX  menugen.ru        # должны остаться routeN.mx.cloudflare.net
```

### 3. Ключ

**API Keys → Create API Key**, permission `Sending access`, домен `menugen.ru`.
Показывается один раз.

### 4. Сервер

```bash
cd /opt/menugen
cp .env .env.bak-$(date +%F)

sed -i 's|^EMAIL_BACKEND=.*|EMAIL_BACKEND=anymail.backends.resend.EmailBackend|' .env
grep -q '^EMAIL_BACKEND=' .env || echo 'EMAIL_BACKEND=anymail.backends.resend.EmailBackend' >> .env

sed -i 's|^RESEND_API_KEY=.*|RESEND_API_KEY=re_КЛЮЧ|' .env
grep -q '^RESEND_API_KEY=' .env || echo 'RESEND_API_KEY=re_КЛЮЧ' >> .env

sed -i 's|^DEFAULT_FROM_EMAIL=.*|DEFAULT_FROM_EMAIL=noreply@menugen.ru|' .env

grep -oE '^[A-Z_]+=' .env | sort | uniq -d   # дубликатов быть не должно
docker compose up -d backend
```

Ключи прошлого провайдера можно оставить — они не мешают и пригодятся при
откате.

### 5. Проверка

```bash
docker compose exec backend python manage.py send_test_email menugen@yandex.com
```

Ожидается `Backend: anymail.backends.resend.EmailBackend` и
`Письмо отправлено ✅`. **Затем открыть ящик** — и «Входящие», и «Спам»: у
нового отправителя первое письмо на Яндекс часто уезжает в спам, это холодная
репутация, а не поломка.

## Смена провайдера

Провайдер не «зашит» — меняется одной строкой в `.env`, ключи уже
предусмотрены в `settings.ANYMAIL`:

| Провайдер | EMAIL_BACKEND | Ключ |
|---|---|---|
| Resend | `anymail.backends.resend.EmailBackend` | `RESEND_API_KEY` |
| Unisender Go | `anymail.backends.unisender_go.EmailBackend` | `UNISENDER_GO_API_KEY` |
| Mailgun | `anymail.backends.mailgun.EmailBackend` | `MAILGUN_API_KEY` |

Anymail 14.0 умеет заметно больше (brevo, mailersend, postmark, amazon_ses и
др.) — чтобы добавить, нужен только новый ключ в `settings.ANYMAIL`.

## История: почему не Unisender Go

Настройка доведена до конца и рабочая, отказались только из-за тарифа. Порядок
ошибок, которые пришлось пройти, — на случай возврата или похожего провайдера.

### Unisender и Unisender Go — разные сервисы

| | Кабинет | Что это |
|---|---|---|
| **Unisender** | `app.unisender.com` | классические маркетинговые рассылки |
| **Unisender Go** | `go1.unisender.ru` / `go2.unisender.ru` | транзакционные письма |

Аккаунты, API-ключи и DNS-записи у них **свои**. Ключ от первого во втором даёт:

```
401 Unauthorized, code 114
"User with id '…' not found"
```

Формулировка обманчива: ключ структурно валиден, идентификатор из него
разбирается — просто такого пользователя нет в базе Go. Смена дата-центра
(`go1` ↔ `go2`) не помогает: ни в одном его нет. Дата-центр определяется
адресом кабинета и должен совпадать с `UNISENDER_GO_API_URL`.

DKIM-селектор и SPF-include у продуктов тоже разные — записи пришлось
переделывать целиком.

### NS-делегирование backend-домена пропускать нельзя

Кроме SPF и DKIM Go выдаёт **NS-записи для служебных поддоменов** (backend- и
tracking-домен, вида `ask.menugen.ru`, по три NS на каждый). Выглядят они
необязательными — это не так:

```
403 Forbidden, code 229
"Custom backend domain or tracking domain required for sending"
```

Записи короткие (`ask`, `test`), три NS на поддомен, **DNS only**.

### Бесплатный тариф не даёт слать на чужие домены

```
403 Forbidden, code 903
"On the 'free_tier' tariff it is allowed to send letters only to the
'checked' domains or 'checked' emails. The request contains external
domain(s) 'yandex.com'."
```

Отправка работает только на собственный подтверждённый домен. Для подтверждения
регистрации это бесполезно: адреса пользователей — произвольные. Снимается
только платным тарифом (~8 £/мес на момент проверки), что для десятков писем в
месяц несоразмерно. Бесплатный тариф Resend такого ограничения не имеет —
поэтому переехали.

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

## Подводные камни

| Грабли | Как избежать |
|---|---|
| Две SPF-записи на одном имени | Одна TXT-запись с несколькими `include:` |
| MX провайдера поверх корневых | MX отправителя живёт на поддомене (`send`), корневые — Cloudflare Email Routing |
| Cloudflare дописывает зону к имени | В поле Name — короткое имя (`send`), иначе выйдет `send.menugen.ru.menugen.ru` |
| Дубли ключей в `.env` | `cat >> .env` дописывает вторую строку к уже существующей; `sed -i 's\|^KEY=.*\|…\|'` затем правит **обе**. Проверять: `grep -oE '^[A-Z_]+=' .env \| sort \| uniq -d` |
| Письмо не приходит на домен | В Cloudflare включить **catch-all** (сервисы пишут на `postmaster@`/`admin@`) |
| Привязка сайта к домену позже | A-запись в режиме **DNS only** (серая тучка), иначе прокси Cloudflare вмешается в TLS/API |
| Отправка через Cloudflare | Невозможна — он только принимает/пересылает |
| Письма молча не уходят | Проверить `email_enabled()`: для SMTP нужен `EMAIL_HOST`, для HTTP API — ключ провайдера |
| «Отправлено» ≠ «доставлено» | Гейт `EMAIL_VERIFICATION_REQUIRED` включать только после письма, реально дошедшего до внешнего ящика |
