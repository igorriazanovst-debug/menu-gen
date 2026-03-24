# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — Модели и миграции ✅

---

## Что сделано

### Шаг 1: Скаффолдинг ✅
- docker-compose, Makefile, CI, .env.example, README, структура папок

### Шаг 2: Модели и миграции ✅

Все модели написаны и миграции созданы (33 файла, `check` — 0 ошибок).

| App | Модели |
|---|---|
| users | User (кастомный AbstractBaseUser), Profile |
| family | Family, FamilyMember |
| subscriptions | SubscriptionPlan, Subscription |
| recipes | Recipe, RecipeAuthor |
| fridge | Product, FridgeItem |
| menu | Menu, MenuItem, ShoppingList, ShoppingItem |
| diary | DiaryEntry, WaterLog |
| specialists | Specialist, SpecialistAssignment, Recommendation, DocumentArchive, DocumentAccessLog |
| payments | Payment |
| notifications | Notification |
| social | SocialLink |
| sync | SyncLog, AuditLog |

### Ключевые решения
- AUTH_USER_MODEL = "users.User" — email/phone/vk_id, все уникальные nullable
- allergies / disliked_products — JSONField на User
- Recipe.legacy_id — для связи с recipes.db (SQLite → PostgreSQL)
- DocumentArchive.encrypted_data — BinaryField
- SyncLog — entity_type + entity_id + conflict_data

---

## Следующий шаг

**Этап 1, шаг 3 — API авторизации**

Реализовать в `apps/users/`:
- `POST /api/v1/auth/email/register` — регистрация (создаёт User + Profile + Family + Subscription[Free])
- `POST /api/v1/auth/login` — email+пароль → access+refresh JWT
- `POST /api/v1/auth/refresh` — обновление токена
- `POST /api/v1/auth/logout` — инвалидация refresh
- `GET/PUT /api/v1/users/me` — профиль текущего пользователя

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек
- Python 3.11 + Django 4.2 + DRF + JWT + drf-spectacular
- PostgreSQL 15 + Redis 7 + Celery
- Docker + GitHub Actions CI
