# MenuGen — Резюме для нового чата

**Проект:** Генератор меню (MenuGen)
**Дата:** Апрель 2026
**Репозиторий:** https://github.com/igorriazanovst-debug/menu-gen

---

## Правила работы

1. Диалог на русском языке
2. Если непонятно — задавай вопрос
3. Исправления через скрипт где возможно
4. Файлы проекта в Project Knowledge (GitHub)
5. Не объясняй. Не извиняйся. Только код.
6. НИКОГДА не хардкодь URL, токены, пароли
7. Резюме для нового чата — в виде файла
8. В начале нового чата: резюме → файлы проекта → вопрос если нужен

---

## Статус этапов

| Этап | Описание | Статус |
|---|---|---|
| 1 | Бэкенд (Django + PostgreSQL) | ✅ |
| 2 | Flutter мобильное приложение | ✅ |
| 3 | React веб-приложение | ✅ |
| 3.5 | Локальный стенд Windows 11 | ✅ |
| 4 | Интеграции (VK, FCM, доставка) | ⏳ |
| 5 | Кабинет специалиста (React) | ✅ |
| 6 | Тестирование и релиз | 🔄 |

---

## Локальный стенд Windows 11

**Путь проекта:** `C:\Temp\2026\menu-gen\menu-gen`

### Запуск докера
```powershell
cd C:\Temp\2026\menu-gen\menu-gen
docker compose up -d
cd web\menugen-web
npm start
```

### Сервисы
| Сервис | URL |
|---|---|
| Swagger | http://localhost:8000/api/v1/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| React web | http://localhost:3000 |

### ⚠️ IP меняется после рестарта (DHCP)
После каждого рестарта нужно:
1. Узнать новый IP: `ipconfig | findstr "192.168"`
2. Обновить `.env`: `ALLOWED_HOSTS=localhost,127.0.0.1,<новый_IP>`
3. Перезапустить: `docker compose down` затем `docker compose up -d`
4. Пересобрать APK: `flutter build apk --debug --dart-define=API_BASE_URL=http://<новый_IP>:8000/api/v1`

### ⚠️ ALLOWED_HOSTS — важно
`docker compose restart backend` НЕ подхватывает изменения `.env`.
Всегда использовать `docker compose down` затем `docker compose up -d`.

### ⚠️ PowerShell
- `&&` не работает в PowerShell — использовать отдельные команды
- Скрипты с кириллицей в dart-файлах — создавать файл-артефакт и копировать вручную

---

## Дебаг аккаунт

```
Email:    admin@dev.local
Password: Admin1234!
```
Работает везде: веб, Django Admin, мобильное приложение.

---

## Сборка APK

```powershell
cd C:\Temp\2026\menu-gen\menu-gen\mobile\menugen_app
flutter build apk --debug --dart-define=API_BASE_URL=http://<IP>:8000/api/v1
```
APK: `mobile\menugen_app\build\app\outputs\flutter-apk\app-debug.apk`

### Конфиг URL в Flutter
`lib/core/config/app_config.dart` — читает `API_BASE_URL` из `dart-define`

---

## Сделано в этом чате

### 1. Импорт 400 блюд из xlsx
- Скрипт: `import_dishes.py`
- Запуск внутри контейнера через `manage.py shell`
- Результат: 377 создано, 23 обновлено

### 2. Редактор блюд в веб-интерфейсе
Файлы изменены:
- `web/menugen-web/src/pages/Recipes/RecipesPage.tsx` — кнопка ✏️ для admin (при наведении на карточку и в модальном окне)
- `web/menugen-web/src/components/recipes/RecipeEditModal.tsx` — редактор с 4 вкладками: Основное, КБЖУ, Ингредиенты, Шаги
- `web/menugen-web/src/api/recipes.ts` — добавлен `uploadMedia`
- `web/menugen-web/src/types/index.ts` — добавлены `fiber` и `weight` в `Nutrition`

### 3. Загрузка медиафайлов для рецептов
- `backend/apps/recipes/media_upload.py` — endpoint `POST /api/v1/recipes/upload-media/`
- `backend/apps/recipes/urls.py` — зарегистрирован новый endpoint
- Изображения: JPEG/PNG/WebP/GIF до 10 МБ → `media/recipes/images/`
- Видео: MP4/WebM/MOV до 200 МБ → `media/recipes/videos/`
- URL сохраняется в `image_url` / `video_url` рецепта

### 4. Исправление сортировки рецептов
**Проблема:** `OrderingFilter` глобально перехватывал сортировку, игнорируя `get_queryset`  
**Решение:** в `RecipeViewSet` убран `ordering`, добавлен явный `filter_backends` без `OrderingFilter`, `get_queryset` возвращает рецепты с изображениями первыми (`-has_image, -created_at`)

Файл изменён: `backend/apps/recipes/views.py`

---

## Известные особенности

- `django compose restart backend` НЕ перезапускает код — нужен `down` + `up -d`
- Изменения в контейнере через `docker cp` + python скрипт — синхронизировать обратно через `docker cp container:/app/file local_path`
- Redis кеш сбрасывать: `docker compose exec redis redis-cli FLUSHALL`
- Удалить pyc кеш: `docker compose exec backend bash -c "find /app -name '__pycache__' -type d | xargs rm -rf"`
