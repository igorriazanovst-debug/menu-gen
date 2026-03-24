# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — API авторизации ✅

---

## Что сделано

### Шаг 1: Скаффолдинг ✅
### Шаг 2: Модели и миграции ✅
### Шаг 3: API авторизации ✅

**Файлы:**
- `apps/users/serializers.py` — RegisterSerializer, LoginSerializer, UserMeSerializer, UserMeUpdateSerializer
- `apps/users/views.py` — RegisterView, LoginView, LogoutView, UserMeView
- `apps/users/urls/auth.py` — маршруты /auth/
- `apps/users/urls/users.py` — маршруты /users/
- `apps/users/tests/test_auth.py` — 12 тест-кейсов

**Эндпоинты:**
| Метод | URL | Описание |
|---|---|---|
| POST | /api/v1/auth/email/register/ | Регистрация → access+refresh JWT |
| POST | /api/v1/auth/login/ | Вход → access+refresh JWT |
| POST | /api/v1/auth/refresh/ | Обновление access токена |
| POST | /api/v1/auth/logout/ | Инвалидация refresh (blacklist) |
| GET | /api/v1/users/me/ | Профиль текущего пользователя |
| PUT/PATCH | /api/v1/users/me/ | Обновление профиля |

**Ключевые решения:**
- При регистрации атомарно создаётся User + Profile + Family + FamilyMember(HEAD) + Subscription(free, если план существует)
- Logout через simplejwt TokenBlacklist
- `rest_framework_simplejwt.token_blacklist` добавлен в INSTALLED_APPS

---

## Следующий шаг

**Этап 1, шаг 4 — API рецептов + скрипт миграции recipes.db**

- `GET /api/v1/recipes/` — список с фильтрацией/поиском/пагинацией
- `GET /api/v1/recipes/{id}/` — детальная карточка
- `POST /api/v1/recipes/` — создание (тариф Basic+)
- `PUT/PATCH /api/v1/recipes/{id}/` — редактирование (автор/admin)
- `DELETE /api/v1/recipes/{id}/` — удаление (автор/admin)
- `POST /api/v1/recipes/{id}/favorite/` — добавить в избранное
- `scripts/migrate_recipes_db.py` — SQLite recipes.db → PostgreSQL

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек
- Python 3.11 + Django 4.2 + DRF + JWT + drf-spectacular
- PostgreSQL 15 + Redis 7 + Celery
- Docker + GitHub Actions CI
