# MenuGen — Резюме сессии

**Дата:** Март 2026
**Статус:** Этап 1 — API семьи + холодильника ✅

---

## Что сделано

### Шаг 1: Скаффолдинг ✅
### Шаг 2: Модели и миграции ✅
### Шаг 3: API авторизации ✅
### Шаг 4: API рецептов + скрипт миграции ✅
### Шаг 5: API семьи + холодильника ✅

**Family:**
- `apps/family/serializers.py` — FamilySerializer, FamilyMemberSerializer, InviteMemberSerializer
- `apps/family/views.py` — FamilyDetailView, FamilyInviteView, FamilyRemoveMemberView
- `apps/family/permissions.py` — IsFamilyHead
- `apps/family/tests/test_family.py` — 11 тест-кейсов

**Fridge:**
- `apps/fridge/serializers.py` — FridgeItemSerializer, FridgeItemWriteSerializer, BarcodeLookupSerializer
- `apps/fridge/views.py` — FridgeListCreateView, FridgeItemDetailView, BarcodeLookupView, ProductSearchView
- `apps/fridge/tests/test_fridge.py` — 12 тест-кейсов

**Эндпоинты:**
| Метод | URL | Описание |
|---|---|---|
| GET | /api/v1/family/ | Состав семьи |
| PATCH | /api/v1/family/ | Переименовать семью |
| POST | /api/v1/family/invite/ | Пригласить по email/phone |
| DELETE | /api/v1/family/members/{id}/ | Удалить участника |
| GET | /api/v1/fridge/ | Список продуктов |
| POST | /api/v1/fridge/ | Добавить продукт |
| GET/PATCH/DELETE | /api/v1/fridge/{id}/ | Управление продуктом |
| POST | /api/v1/fridge/scan/ | Поиск по штрихкоду |
| GET | /api/v1/fridge/products/search/ | Поиск продуктов (?q=) |

**Ключевые решения:**
- Приглашение проверяет лимит участников по тарифу (SubscriptionPlan.max_family_members)
- Мягкое удаление продуктов (is_deleted=True, не физическое удаление)
- Фильтр ?expiring_days=N показывает продукты с истекающим сроком
- Поиск продуктов возвращает пустой список при запросе < 2 символов

---

## Следующий шаг

**Этап 1, шаг 6 — Генератор меню**

- `POST /api/v1/menu/generate/` — сгенерировать меню на N дней
- `GET /api/v1/menu/` — список меню семьи
- `GET /api/v1/menu/{id}/` — детальное меню
- `PATCH /api/v1/menu/{id}/items/{item_id}/` — поменять рецепт в слоте
- `GET /api/v1/menu/{id}/shopping-list/` — список покупок по меню

---

## Репозиторий
GitHub: (указать URL при пуше)

## Стек
- Python 3.11 + Django 4.2 + DRF + JWT + drf-spectacular
- PostgreSQL 15 + Redis 7 + Celery
- Docker + GitHub Actions CI
