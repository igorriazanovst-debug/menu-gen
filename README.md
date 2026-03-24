# MenuGen — Генератор меню

## Быстрый старт (локально)

```bash
git clone <repo-url>
cd menugen
bash scripts/setup.sh
```

Скрипт создаст `.env` из `.env.example`. Заполните значения и запустите снова.

## Команды

| Команда | Описание |
|---|---|
| `make up` | Запустить все сервисы |
| `make down` | Остановить все сервисы |
| `make build` | Пересобрать образы |
| `make logs` | Логи бэкенда |
| `make migrate` | Применить миграции |
| `make makemigrations` | Создать миграции |
| `make test` | Запустить тесты |
| `make lint` | Проверить код |
| `make format` | Форматировать код |
| `make createsuperuser` | Создать admin-пользователя |

## Сервисы (dev)

| Сервис | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/api/v1/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## Структура проекта

```
menugen/
├── backend/
│   ├── apps/
│   │   ├── users/          # Авторизация, профили
│   │   ├── recipes/        # Рецепты
│   │   ├── family/         # Семья и участники
│   │   ├── fridge/         # Холодильник и продукты
│   │   ├── menu/           # Генератор меню
│   │   ├── diary/          # Дневник питания
│   │   ├── specialists/    # Кабинет специалиста
│   │   ├── subscriptions/  # Тарифы и подписки
│   │   ├── payments/       # Платежи (ЮKassa)
│   │   ├── notifications/  # Уведомления
│   │   ├── social/         # VK интеграция
│   │   └── sync/           # Синхронизация офлайн
│   ├── config/             # Django settings, urls, celery
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
├── scripts/
│   └── setup.sh
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── Makefile
├── .env.example
└── .gitignore
```

## Стек

- **Backend:** Python 3.11 + Django 4.2 + DRF
- **БД:** PostgreSQL 15
- **Кеш/Очередь:** Redis 7 + Celery
- **Auth:** JWT (djangorestframework-simplejwt)
- **API Docs:** Swagger (drf-spectacular)
- **CI:** GitHub Actions
