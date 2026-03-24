# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — Скаффолдинг бэкенда ✅

---

## Что сделано

### Структура проекта создана (`menugen/`)

```
menugen/
├── backend/
│   ├── apps/               # 12 Django-приложений (заготовки)
│   │   ├── users/          # urls/ разделён на auth.py и users.py
│   │   ├── recipes/
│   │   ├── family/
│   │   ├── fridge/
│   │   ├── menu/
│   │   ├── diary/
│   │   ├── specialists/
│   │   ├── subscriptions/
│   │   ├── payments/
│   │   ├── notifications/
│   │   ├── social/
│   │   └── sync/
│   ├── config/
│   │   ├── settings.py     # Полный конфиг (PostgreSQL, Redis, JWT, Celery, DRF, Spectacular)
│   │   ├── urls.py         # Все маршруты подключены
│   │   ├── celery.py
│   │   └── wsgi.py
│   ├── manage.py
│   ├── requirements.txt    # Django 4.2, DRF, JWT, Celery, drf-spectacular, psycopg2...
│   ├── Dockerfile
│   ├── pytest.ini
│   ├── .flake8
│   └── pyproject.toml      # black + isort config
├── .github/workflows/ci.yml  # GitHub Actions: lint + test (PostgreSQL + Redis в сервисах)
├── docker-compose.yml        # db, redis, backend, celery, celery-beat
├── Makefile                  # up, down, build, migrate, test, lint, format, shell
├── scripts/setup.sh          # Первичная настройка dev-окружения
├── .env.example              # Все переменные без значений
├── .gitignore
└── README.md
```

### Ключевые решения
- `AUTH_USER_MODEL = "users.User"` — кастомная модель (ещё не написана)
- Все apps зарегистрированы в `INSTALLED_APPS`
- JWT: access 15 мин, refresh 30 дней, ротация включена
- Rate limiting: 100 req/min для user, 20 для anon
- Логирование настроено (без ПДн)

---

## Следующий шаг

**Этап 1, шаг 2 — Модели и миграции**

Порядок: `users` → `subscriptions` → `family` → `recipes` → `fridge` → `menu` → `diary` → `specialists` → `sync` → остальные

Начать с `apps/users/models.py`:
- Кастомный `User` (email/phone/vk_id, user_type, allergies, disliked_products)
- `Profile` (birth_year, gender, height, weight, activity_level, goal)

---

## Репозиторий
GitHub: (указать URL при пуше)
Ветка: `main` / `develop`

## Стек
- Python 3.11 + Django 4.2 + DRF
- PostgreSQL 15 + Redis 7
- Celery + celery-beat
- JWT (simplejwt) + drf-spectacular (Swagger)
- Docker + GitHub Actions CI
