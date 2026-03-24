# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — Дневник + Подписки + Платежи ✅

---

## Что сделано

### Шаг 1: Скаффолдинг ✅
### Шаг 2: Модели и миграции ✅
### Шаг 3: API авторизации ✅
### Шаг 4: API рецептов + скрипт миграции ✅
### Шаг 5: API семьи + холодильника ✅
### Шаг 6: Генератор меню ✅
### Шаг 7: Дневник питания + Подписки + Платежи (ЮKassa) ✅

**Diary:**
- `apps/diary/serializers.py` — Entry / Write / Stats / WaterLog
- `apps/diary/views.py` — List/Create, Detail, Stats, WaterLog
- `apps/diary/tests/test_diary.py` — 9 тест-кейсов

**Subscriptions:**
- `apps/subscriptions/serializers.py` — Plan / Subscription / Subscribe
- `apps/subscriptions/views.py` — PlanList, Current, Subscribe, Cancel
- `apps/subscriptions/tests/test_subscriptions.py` — 6 тест-кейсов

**Payments:**
- `apps/payments/yookassa_client.py` — обёртка над ЮKassa SDK (create_payment, get_payment)
- `apps/payments/views.py` — PaymentHistory, YookassaWebhookView (HMAC-SHA256)
- `apps/payments/tests/test_webhook.py` — 2 тест-кейса (succeeded + invalid sig)

**Эндпоинты:**
| Метод | URL | Описание |
|---|---|---|
| GET/POST | /api/v1/diary/ | Записи дневника (?date=) |
| GET/DELETE | /api/v1/diary/{id}/ | Запись |
| GET | /api/v1/diary/stats/ | КБЖУ за период (?from=&to=) |
| GET/POST | /api/v1/diary/water/ | Трекер воды |
| GET | /api/v1/subscriptions/plans/ | Список тарифов (публичный) |
| GET | /api/v1/subscriptions/current/ | Текущая подписка |
| POST | /api/v1/subscriptions/subscribe/ | Оформить → URL оплаты |
| POST | /api/v1/subscriptions/cancel/ | Отключить автопродление |
| GET | /api/v1/payments/history/ | История платежей |
| POST | /api/v1/payments/webhook/yookassa/ | Вебхук ЮKassa |

**Ключевые решения:**
- Вебхук проверяет подпись HMAC-SHA256 (X-Yookassa-Signature)
- payment.succeeded → создаёт Subscription + Payment атомарно
- WaterLog — upsert по (member, date), не дублируется
- Дневник: автокопирование nutrition из рецепта при создании

---

## Следующий шаг

**Этап 1, шаг 8 — Финал бэкенда: admin, Celery-задачи, Swagger, покрытие тестами**

- Django admin для всех моделей
- Celery tasks: напоминания об истекающих продуктах, автоистечение подписок
- Swagger UI — проверка всех эндпоинтов
- Запуск полного набора тестов, покрытие >70%

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек
- Python 3.11 + Django 4.2 + DRF + JWT + drf-spectacular
- PostgreSQL 15 + Redis 7 + Celery
- ЮKassa (yookassa SDK)
- Docker + GitHub Actions CI
