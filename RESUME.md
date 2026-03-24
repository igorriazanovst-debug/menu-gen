# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — БЭКЕНД ЗАВЕРШЁН ✅

---

## Все шаги Этапа 1 выполнены

| # | Шаг | Статус |
|---|---|---|
| 1 | Скаффолдинг (Docker, CI/CD, Makefile) | ✅ |
| 2 | Модели и миграции (12 приложений, 20+ моделей) | ✅ |
| 3 | API авторизации (register/login/refresh/logout/me) | ✅ |
| 4 | API рецептов + скрипт миграции recipes.db | ✅ |
| 5 | API семьи + холодильника | ✅ |
| 6 | Генератор меню + список покупок | ✅ |
| 7 | Дневник питания + Подписки + Платежи (ЮKassa) | ✅ |
| 8 | Django admin + Celery tasks + Swagger + тесты | ✅ |

---

## Итоговая статистика

- **Тестов:** 92 тест-кейса по 9 модулям
- **Эндпоинтов:** ~40 (все задокументированы в Swagger)
- **Celery tasks:** 3 задачи (fridge_expiry, expire_subscriptions, menu_reminder)
- **Admin:** 15 зарегистрированных моделей с actions
- **Swagger:** генерируется без ошибок (`python manage.py spectacular`)

## Celery Beat расписание
| Задача | Расписание |
|---|---|
| check_fridge_expiry | Ежедневно 09:00 |
| expire_subscriptions | Ежедневно 00:05 |
| send_menu_reminder | Каждый понедельник 10:00 |

---

## Следующий этап

**Этап 2 — Мобильное приложение (Flutter)**

Начать с:
1. Создание Flutter-проекта (`flutter create menugen_app`)
2. Настройка Drift (SQLite) + SQLCipher для офлайн-БД
3. Настройка BLoC state management
4. Сетевой слой (Dio + JWT interceptor)
5. Экраны: Вход → Dashboard → Генератор меню

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек бэкенда
- Python 3.11 + Django 4.2 + DRF + JWT + drf-spectacular
- PostgreSQL 15 + Redis 7 + Celery + celery-beat
- ЮKassa SDK
- Docker + GitHub Actions CI
